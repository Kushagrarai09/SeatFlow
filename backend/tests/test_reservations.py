"""Reservation lifecycle tests using isolated SQLite state."""

import os
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-that-is-long-enough-for-seatflow")

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Reservation, TicketCategory, User


def make_client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), engine, factory


def register_user(client, factory, email, role="attendee"):
    response = client.post("/api/v1/auth/register", json={
        "email": email, "full_name": "Reservation Tester", "password": "correct-horse-123"
    })
    assert response.status_code == 201, response.text
    with factory() as db:
        user = db.scalar(select(User).where(User.email == email.lower()))
        user.role = role
        db.commit()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "correct-horse-123"})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def create_inventory(client, organizer_headers, factory, quantity=5):
    org = client.post("/api/v1/organizers", headers=organizer_headers, json={
        "name": "Reservation Host", "email": "reservation-host@example.com"
    })
    assert org.status_code == 201, org.text
    venue = client.post("/api/v1/venues", headers=organizer_headers, json={
        "name": "Reservation Venue", "address": "1 Test Road", "city": "Mumbai",
        "country": "India", "capacity": 100
    })
    assert venue.status_code == 201, venue.text
    year = datetime.now(timezone.utc).year + 1
    event = client.post("/api/v1/events", headers=organizer_headers, json={
        "organizer_id": org.json()["id"], "venue_id": venue.json()["id"],
        "title": "Reservation Event", "category": "music",
        "starts_at": f"{year}-06-10T18:00:00Z", "ends_at": f"{year}-06-10T21:00:00Z",
        "price": "250.00", "capacity": 100, "status": "published"
    })
    assert event.status_code == 201, event.text
    category = client.post(f"/api/v1/events/{event.json()['id']}/ticket-categories",
                           headers=organizer_headers, json={
        "name": "General", "price": "250.00", "total_quantity": quantity,
        "min_per_order": 1, "max_per_order": 5, "status": "active"
    })
    assert category.status_code == 201, category.text
    return category.json()["id"]


def cleanup(client, engine):
    client.close()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def reserve(client, headers, category_id, key, quantity=1):
    return client.post("/api/v1/reservations", headers={
        **headers, "Idempotency-Key": key
    }, json={"ticket_category_id": category_id, "quantity": quantity})


def test_idempotency_returns_same_reservation_and_rejects_payload_change():
    client, engine, factory = make_client()
    try:
        host = register_user(client, factory, "host@example.com", "organizer")
        attendee = register_user(client, factory, "attendee@example.com")
        category_id = create_inventory(client, host, factory)
        first = reserve(client, attendee, category_id, "idem-key-0001", 2)
        replay = reserve(client, attendee, category_id, "idem-key-0001", 2)
        assert first.status_code == 201, first.text
        assert replay.status_code == 201, replay.text
        assert first.json()["id"] == replay.json()["id"]
        conflict = reserve(client, attendee, category_id, "idem-key-0001", 3)
        assert conflict.status_code == 409
        with factory() as db:
            category = db.get(TicketCategory, category_id)
            assert category.reserved_quantity == 2
    finally:
        cleanup(client, engine)


def test_cancellation_releases_hold_and_is_idempotent():
    client, engine, factory = make_client()
    try:
        host = register_user(client, factory, "host@example.com", "organizer")
        attendee = register_user(client, factory, "attendee@example.com")
        category_id = create_inventory(client, host, factory, quantity=3)
        created = reserve(client, attendee, category_id, "cancel-key-0001", 2)
        reservation_id = created.json()["id"]
        cancelled = client.post(f"/api/v1/reservations/{reservation_id}/cancel", headers=attendee)
        assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
        replay = client.post(f"/api/v1/reservations/{reservation_id}/cancel", headers=attendee)
        assert replay.status_code == 200 and replay.json()["status"] == "cancelled"
        with factory() as db:
            category = db.get(TicketCategory, category_id)
            assert category.reserved_quantity == 0
    finally:
        cleanup(client, engine)


def test_confirm_moves_reserved_quantity_to_sold_and_is_idempotent():
    client, engine, factory = make_client()
    try:
        host = register_user(client, factory, "host@example.com", "organizer")
        attendee = register_user(client, factory, "attendee@example.com")
        category_id = create_inventory(client, host, factory, quantity=3)
        created = reserve(client, attendee, category_id, "confirm-key-001", 2)
        reservation_id = created.json()["id"]
        confirmed = client.post(f"/api/v1/reservations/{reservation_id}/confirm", headers=attendee)
        assert confirmed.status_code == 200 and confirmed.json()["status"] == "confirmed"
        again = client.post(f"/api/v1/reservations/{reservation_id}/confirm", headers=attendee)
        assert again.status_code == 200 and again.json()["status"] == "confirmed"
        with factory() as db:
            category = db.get(TicketCategory, category_id)
            assert category.reserved_quantity == 0
            assert category.sold_quantity == 2
    finally:
        cleanup(client, engine)


def test_expiry_releases_inventory_and_confirmation_is_denied():
    client, engine, factory = make_client()
    try:
        host = register_user(client, factory, "host@example.com", "organizer")
        attendee = register_user(client, factory, "attendee@example.com")
        admin = register_user(client, factory, "admin@example.com", "admin")
        category_id = create_inventory(client, host, factory, quantity=2)
        created = reserve(client, attendee, category_id, "expiry-key-0001", 2)
        reservation_id = created.json()["id"]
        with factory() as db:
            row = db.get(Reservation, reservation_id)
            row.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
            db.commit()
        sweep = client.post("/api/v1/admin/reservations/expire", headers=admin)
        assert sweep.status_code == 200 and sweep.json()["expired_count"] == 1
        confirm = client.post(f"/api/v1/reservations/{reservation_id}/confirm", headers=attendee)
        assert confirm.status_code == 409
        with factory() as db:
            category = db.get(TicketCategory, category_id)
            row = db.get(Reservation, reservation_id)
            assert category.reserved_quantity == 0
            assert row.status == "expired"
    finally:
        cleanup(client, engine)


def test_insufficient_inventory_does_not_overbook():
    client, engine, factory = make_client()
    try:
        host = register_user(client, factory, "host@example.com", "organizer")
        attendee = register_user(client, factory, "attendee@example.com")
        category_id = create_inventory(client, host, factory, quantity=2)
        first = reserve(client, attendee, category_id, "stock-key-0001", 2)
        assert first.status_code == 201, first.text
        second = reserve(client, attendee, category_id, "stock-key-0002", 1)
        assert second.status_code == 409
        with factory() as db:
            category = db.get(TicketCategory, category_id)
            assert category.reserved_quantity == 2
    finally:
        cleanup(client, engine)


def test_other_attendee_cannot_read_or_cancel_reservation():
    client, engine, factory = make_client()
    try:
        host = register_user(client, factory, "host@example.com", "organizer")
        attendee = register_user(client, factory, "attendee@example.com")
        other = register_user(client, factory, "other@example.com")
        category_id = create_inventory(client, host, factory)
        created = reserve(client, attendee, category_id, "owner-key-0001")
        reservation_id = created.json()["id"]
        assert client.get(f"/api/v1/reservations/{reservation_id}", headers=other).status_code == 404
        assert client.post(f"/api/v1/reservations/{reservation_id}/cancel", headers=other).status_code == 404
    finally:
        cleanup(client, engine)


def test_expiry_sweep_persists_when_cancel_fails_for_expired_reservation():
    client, engine, factory = make_client()
    try:
        host = register_user(client, factory, "host@example.com", "organizer")
        attendee = register_user(client, factory, "attendee@example.com")
        category_id = create_inventory(client, host, factory, quantity=2)
        created = reserve(client, attendee, category_id, "expiry-cancel-key-1", 2)
        reservation_id = created.json()["id"]
        with factory() as db:
            row = db.get(Reservation, reservation_id)
            row.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
            db.commit()
        response = client.post(f"/api/v1/reservations/{reservation_id}/cancel", headers=attendee)
        assert response.status_code == 409
        with factory() as db:
            category = db.get(TicketCategory, category_id)
            row = db.get(Reservation, reservation_id)
            assert category.reserved_quantity == 0
            assert row.status == "expired"
    finally:
        cleanup(client, engine)


def test_confirm_rejects_expired_reservation_and_persists_expiry():
    client, engine, factory = make_client()
    try:
        host = register_user(client, factory, "host@example.com", "organizer")
        attendee = register_user(client, factory, "attendee@example.com")
        category_id = create_inventory(client, host, factory, quantity=2)
        created = reserve(client, attendee, category_id, "confirm-expire-key-1", 2)
        reservation_id = created.json()["id"]
        with factory() as db:
            row = db.get(Reservation, reservation_id)
            row.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
            db.commit()
        response = client.post(f"/api/v1/reservations/{reservation_id}/confirm", headers=attendee)
        assert response.status_code == 409
        with factory() as db:
            category = db.get(TicketCategory, category_id)
            row = db.get(Reservation, reservation_id)
            assert category.reserved_quantity == 0
            assert row.status == "expired"
    finally:
        cleanup(client, engine)
