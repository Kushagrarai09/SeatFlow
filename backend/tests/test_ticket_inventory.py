"""Ticket inventory API tests using isolated SQLite state."""

import os
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-that-is-long-enough-for-seatflow")

from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.database import Base, get_db
from app.main import app
from app.models import User, Venue, Organizer, Event, TicketCategory
from datetime import datetime, timezone
from decimal import Decimal


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
    app.state.test_session_factory = factory
    return TestClient(app), engine, factory


def register_as(client, factory, email, role):
    registered = client.post("/api/v1/auth/register", json={
        "email": email, "full_name": "Ticket Test User", "password": "correct-horse-123"
    })
    assert registered.status_code == 201, registered.text
    with factory() as db:
        user = db.scalar(select(User).where(User.email == email.lower()))
        user.role = role  # trusted provisioning simulation for test setup only
        db.commit()
    tokens = client.post("/api/v1/auth/login", json={
        "email": email, "password": "correct-horse-123"
    })
    assert tokens.status_code == 200, tokens.text
    return {"Authorization": "Bearer " + tokens.json()["access_token"]}


def create_event(client, factory, headers, email="ticket-host@example.com", status="published", capacity=200):
    organizer_response = client.post("/api/v1/organizers", headers=headers, json={
        "name": "Ticket Host " + email, "email": email, "description": "Inventory test host"
    })
    assert organizer_response.status_code == 201, organizer_response.text
    venue_response = client.post("/api/v1/venues", headers=headers, json={
        "name": "Ticket Hall", "address": "1 Test Road", "city": "Mumbai",
        "country": "India", "capacity": capacity
    })
    assert venue_response.status_code == 201, venue_response.text
    now_year = datetime.now(timezone.utc).year + 1
    event_response = client.post("/api/v1/events", headers=headers, json={
        "organizer_id": organizer_response.json()["id"],
        "venue_id": venue_response.json()["id"],
        "title": "Ticket Inventory Event",
        "description": "Test event for general-admission ticket categories",
        "category": "technology",
        "starts_at": f"{now_year}-01-10T18:00:00Z",
        "ends_at": f"{now_year}-01-10T21:00:00Z",
        "price": "0.00",
        "capacity": capacity,
        "status": status,
    })
    assert event_response.status_code == 201, event_response.text
    return event_response.json()["id"]


def ticket_payload(**overrides):
    payload = {
        "name": "General Admission",
        "description": "Standard entry",
        "price": "499.00",
        "total_quantity": 100,
        "min_per_order": 1,
        "max_per_order": 8,
        "status": "active",
    }
    payload.update(overrides)
    return payload


def test_create_list_update_and_delete_ticket_category():
    client, engine, factory = make_client()
    try:
        headers = register_as(client, factory, "host@example.com", "organizer")
        event_id = create_event(client, factory, headers)
        created = client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=headers, json=ticket_payload())
        assert created.status_code == 201, created.text
        category = created.json()
        assert category["available_quantity"] == 100
        assert category["sales_open"] is True

        updated = client.patch(
            f"/api/v1/events/{event_id}/ticket-categories/{category['id']}",
            headers=headers,
            json={"price": "599.00", "max_per_order": 5},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["price"] == "599.00"
        assert updated.json()["max_per_order"] == 5

        deleted = client.delete(f"/api/v1/events/{event_id}/ticket-categories/{category['id']}", headers=headers)
        assert deleted.status_code == 204
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_attendees_can_view_active_categories_but_cannot_manage_them():
    client, engine, factory = make_client()
    try:
        host = register_as(client, factory, "host@example.com", "organizer")
        event_id = create_event(client, factory, host)
        active = client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=host, json=ticket_payload())
        inactive = client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=host, json=ticket_payload(
            name="VIP", status="inactive", price="999.00"
        ))
        assert active.status_code == inactive.status_code == 201

        attendee = register_as(client, factory, "attendee@example.com", "attendee")
        visible = client.get(f"/api/v1/events/{event_id}/ticket-categories")
        assert visible.status_code == 200
        assert [item["name"] for item in visible.json()] == ["General Admission"]
        denied = client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=attendee, json=ticket_payload(name="Attendee-created"))
        assert denied.status_code == 403
        inactive_denied = client.get(f"/api/v1/events/{event_id}/ticket-categories", params={"include_inactive": "true"})
        assert inactive_denied.status_code == 403
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_owner_isolation_and_capacity_rules():
    client, engine, factory = make_client()
    try:
        host_a = register_as(client, factory, "host-a@example.com", "organizer")
        event_id = create_event(client, factory, host_a, "host-a@example.com", capacity=50)
        oversized = client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=host_a, json=ticket_payload(total_quantity=51))
        assert oversized.status_code == 422
        created = client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=host_a, json=ticket_payload(total_quantity=50))
        assert created.status_code == 201, created.text

        host_b = register_as(client, factory, "host-b@example.com", "organizer")
        denied = client.patch(
            f"/api/v1/events/{event_id}/ticket-categories/{created.json()['id']}",
            headers=host_b,
            json={"price": "1.00"},
        )
        assert denied.status_code == 403
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_invalid_sales_window_order_limits_and_duplicate_names():
    client, engine, factory = make_client()
    try:
        host = register_as(client, factory, "host@example.com", "organizer")
        event_id = create_event(client, factory, host)
        invalid = client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=host, json=ticket_payload(
            min_per_order=5, max_per_order=2
        ))
        assert invalid.status_code == 422
        invalid_window = client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=host, json=ticket_payload(
            sales_start_at="2027-01-02T00:00:00Z", sales_end_at="2027-01-01T00:00:00Z"
        ))
        assert invalid_window.status_code == 422

        first = client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=host, json=ticket_payload())
        second = client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=host, json=ticket_payload())
        assert first.status_code == 201
        assert second.status_code == 409
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_inventory_adjustment_is_atomic_and_never_below_sold_or_reserved():
    client, engine, factory = make_client()
    try:
        headers = register_as(client, factory, "host@example.com", "organizer")
        event_id = create_event(client, factory, headers, capacity=100)
        category = client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=headers, json=ticket_payload(total_quantity=50))
        assert category.status_code == 201
        category_id = category.json()["id"]
        with factory() as db:
            row = db.get(TicketCategory, category_id)
            row.sold_quantity = 20
            row.reserved_quantity = 10
            db.commit()

        conflict = client.post(
            f"/api/v1/ticket-categories/{category_id}/inventory/adjust",
            params={"quantity_delta": -21},
            headers=headers,
        )
        assert conflict.status_code == 409
        reduced = client.post(
            f"/api/v1/ticket-categories/{category_id}/inventory/adjust",
            params={"quantity_delta": -20},
            headers=headers,
        )
        assert reduced.status_code == 200, reduced.text
        assert reduced.json()["total_quantity"] == 30
        assert reduced.json()["available_quantity"] == 0
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_ticket_category_cannot_be_deleted_after_sales_or_reservations():
    client, engine, factory = make_client()
    try:
        headers = register_as(client, factory, "host@example.com", "organizer")
        event_id = create_event(client, factory, headers)
        created = client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=headers, json=ticket_payload())
        assert created.status_code == 201
        with factory() as db:
            category = db.get(TicketCategory, created.json()["id"])
            category.sold_quantity = 1
            db.commit()
        deleted = client.delete(
            f"/api/v1/events/{event_id}/ticket-categories/{created.json()['id']}",
            headers=headers,
        )
        assert deleted.status_code == 409
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
