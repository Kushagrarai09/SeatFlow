"""Ticket inventory API tests using isolated SQLite state."""
import os
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-that-is-long-enough-for-seatflow")

from datetime import datetime, timezone
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.models import User, TicketCategory


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
    response = client.post("/api/v1/auth/register", json={
        "email": email, "full_name": "Ticket Test User", "password": "correct-horse-123"
    })
    assert response.status_code == 201, response.text
    with factory() as db:
        user = db.scalar(select(User).where(User.email == email.lower()))
        user.role = role
        db.commit()
    tokens = client.post("/api/v1/auth/login", json={"email": email, "password": "correct-horse-123"})
    assert tokens.status_code == 200, tokens.text
    return {"Authorization": "Bearer " + tokens.json()["access_token"]}


def create_event(client, headers, email="ticket-host@example.com", capacity=200):
    org = client.post("/api/v1/organizers", headers=headers, json={
        "name": "Ticket Host " + email, "email": email, "description": "Inventory test host"
    })
    assert org.status_code == 201, org.text
    venue = client.post("/api/v1/venues", headers=headers, json={
        "name": "Ticket Hall", "address": "1 Test Road", "city": "Mumbai", "country": "India", "capacity": capacity
    })
    assert venue.status_code == 201, venue.text
    next_year = datetime.now(timezone.utc).year + 1
    response = client.post("/api/v1/events", headers=headers, json={
        "organizer_id": org.json()["id"], "venue_id": venue.json()["id"],
        "title": "Ticket Inventory Event", "description": "Test event for ticket categories",
        "category": "technology", "starts_at": f"{next_year}-06-10T18:00:00Z",
        "ends_at": f"{next_year}-06-10T21:00:00Z", "price": "0.00",
        "capacity": capacity, "status": "published",
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def ticket_payload(**overrides):
    result = {"name": "General Admission", "description": "Standard entry", "price": "499.00",
              "total_quantity": 100, "min_per_order": 1, "max_per_order": 8, "status": "active"}
    result.update(overrides)
    return result


def cleanup(client, engine):
    client.close()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_create_list_update_delete():
    client, engine, factory = make_client()
    try:
        headers = register_as(client, factory, "host@example.com", "organizer")
        event_id = create_event(client, headers)
        created = client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=headers, json=ticket_payload())
        assert created.status_code == 201, created.text
        row = created.json()
        assert row["available_quantity"] == 100 and row["sales_open"]
        updated = client.patch(f"/api/v1/events/{event_id}/ticket-categories/{row['id']}",
                               headers=headers, json={"price":"599.00", "max_per_order":5})
        assert updated.status_code == 200, updated.text
        assert updated.json()["price"] == "599.00"
        assert client.delete(f"/api/v1/events/{event_id}/ticket-categories/{row['id']}", headers=headers).status_code == 204
    finally:
        cleanup(client, engine)


def test_public_visibility_and_attendee_denied_management():
    client, engine, factory = make_client()
    try:
        host = register_as(client, factory, "host@example.com", "organizer")
        event_id = create_event(client, host)
        active = client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=host, json=ticket_payload())
        inactive = client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=host,
                               json=ticket_payload(name="VIP", status="inactive", price="999.00"))
        assert active.status_code == inactive.status_code == 201
        register_as(client, factory, "attendee@example.com", "attendee")
        listing = client.get(f"/api/v1/events/{event_id}/ticket-categories")
        assert listing.status_code == 200 and [x["name"] for x in listing.json()] == ["General Admission"]
        assert client.get(f"/api/v1/events/{event_id}/ticket-categories", params={"include_inactive":"true"}).status_code == 403
    finally:
        cleanup(client, engine)


def test_ownership_and_capacity_validation():
    client, engine, factory = make_client()
    try:
        host_a = register_as(client, factory, "host-a@example.com", "organizer")
        event_id = create_event(client, host_a, "host-a@example.com", capacity=50)
        assert client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=host_a,
                           json=ticket_payload(total_quantity=51)).status_code == 422
        category = client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=host_a,
                               json=ticket_payload(total_quantity=30))
        assert category.status_code == 201, category.text
        host_b = register_as(client, factory, "host-b@example.com", "organizer")
        assert client.patch(f"/api/v1/events/{event_id}/ticket-categories/{category.json()['id']}",
                            headers=host_b, json={"price":"1.00"}).status_code == 403
    finally:
        cleanup(client, engine)


def test_bad_sales_window_order_rules_and_duplicate_name():
    client, engine, factory = make_client()
    try:
        host = register_as(client, factory, "host@example.com", "organizer")
        event_id = create_event(client, host)
        assert client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=host,
                           json=ticket_payload(min_per_order=5, max_per_order=2)).status_code == 422
        assert client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=host,
                           json=ticket_payload(sales_start_at="2027-01-02T00:00:00Z",
                                               sales_end_at="2027-01-01T00:00:00Z")).status_code == 422
        assert client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=host, json=ticket_payload()).status_code == 201
        assert client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=host, json=ticket_payload()).status_code == 409
    finally:
        cleanup(client, engine)


def test_inventory_adjustment_cannot_undercut_sold_reserved_or_event_capacity():
    client, engine, factory = make_client()
    try:
        host = register_as(client, factory, "host@example.com", "organizer")
        event_id = create_event(client, host, capacity=100)
        created = client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=host,
                              json=ticket_payload(total_quantity=50))
        assert created.status_code == 201, created.text
        category_id = created.json()["id"]
        with factory() as db:
            category = db.get(TicketCategory, category_id)
            category.sold_quantity, category.reserved_quantity = 20, 10
            db.commit()
        bad = client.post(f"/api/v1/ticket-categories/{category_id}/inventory/adjust",
                          params={"quantity_delta":-21}, headers=host)
        assert bad.status_code == 409
        good = client.post(f"/api/v1/ticket-categories/{category_id}/inventory/adjust",
                           params={"quantity_delta":-20}, headers=host)
        assert good.status_code == 200 and good.json()["total_quantity"] == 30
        assert good.json()["available_quantity"] == 0
        too_many = client.post(f"/api/v1/ticket-categories/{category_id}/inventory/adjust",
                               params={"quantity_delta":80}, headers=host)
        assert too_many.status_code == 409
    finally:
        cleanup(client, engine)


def test_category_with_sold_inventory_cannot_be_deleted():
    client, engine, factory = make_client()
    try:
        host = register_as(client, factory, "host@example.com", "organizer")
        event_id = create_event(client, host)
        category = client.post(f"/api/v1/events/{event_id}/ticket-categories", headers=host, json=ticket_payload())
        with factory() as db:
            row = db.get(TicketCategory, category.json()["id"])
            row.sold_quantity = 1
            db.commit()
        assert client.delete(f"/api/v1/events/{event_id}/ticket-categories/{category.json()['id']}",
                             headers=host).status_code == 409
    finally:
        cleanup(client, engine)
