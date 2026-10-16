"""Catalog API tests, including authentication and object ownership."""

import os
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-key-that-is-long-enough-for-seatflow")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import User


def register(client: TestClient, email: str, role: str = "attendee") -> dict:
    response = client.post("/api/v1/auth/register", json={
        "email": email, "full_name": "SeatFlow Test User", "password": "correct-horse-123"
    })
    assert response.status_code == 201, response.text
    # Test fixture only: privileged roles are provisioned directly to model an admin-approved grant.
    factory = app.state.test_session_factory
    with factory() as db:
        user = db.scalar(select(User).where(User.email == email.lower()))
        user.role = role
        db.commit()
    tokens = client.post("/api/v1/auth/login", json={
        "email": email, "password": "correct-horse-123"
    })
    assert tokens.status_code == 200, tokens.text
    return {"Authorization": "Bearer " + tokens.json()["access_token"]}


def client_with_database():
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
    return TestClient(app), engine


def create_event_resources(client: TestClient, headers: dict, email: str) -> tuple[int, int]:
    organizer_response = client.post("/api/v1/organizers", headers=headers, json={
        "name": "SeatFlow Demo " + email,
        "email": email,
        "description": "Test organizer"
    })
    assert organizer_response.status_code == 201, organizer_response.text
    venue_response = client.post("/api/v1/venues", headers=headers, json={
        "name": "Example Hall",
        "address": "1 Example Road",
        "city": "Mumbai",
        "country": "India",
        "capacity": 300,
    })
    assert venue_response.status_code == 201, venue_response.text
    return organizer_response.json()["id"], venue_response.json()["id"]


def event_payload(organizer_id: int, venue_id: int, **overrides):
    payload = {
        "organizer_id": organizer_id,
        "venue_id": venue_id,
        "title": "Backend Builders Meetup",
        "description": "A practical engineering meetup.",
        "category": "technology",
        "starts_at": "2027-01-10T18:00:00Z",
        "ends_at": "2027-01-10T21:00:00Z",
        "price": "499.00",
        "capacity": 250,
        "status": "draft",
    }
    payload.update(overrides)
    return payload


def test_unauthenticated_and_attendee_cannot_mutate_catalog():
    client, engine = client_with_database()
    try:
        assert client.post("/api/v1/venues", json={
            "name": "Hall", "address": "Road", "city": "Mumbai", "capacity": 100
        }).status_code == 401
        attendee = register(client, "attendee@example.com")
        denied = client.post("/api/v1/venues", headers=attendee, json={
            "name": "Hall", "address": "Road", "city": "Mumbai", "capacity": 100
        })
        assert denied.status_code == 403
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_create_event_and_keep_drafts_out_of_public_discovery():
    client, engine = client_with_database()
    try:
        headers = register(client, "host@example.com", "organizer")
        organizer_id, venue_id = create_event_resources(client, headers, "host@example.com")
        response = client.post("/api/v1/events", headers=headers, json=event_payload(organizer_id, venue_id))
        assert response.status_code == 201, response.text
        event_id = response.json()["id"]
        assert client.get("/api/v1/events").json() == []
        assert client.get(f"/api/v1/events/{event_id}").status_code == 404
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_publish_event_and_filter_discovery_by_city_and_category():
    client, engine = client_with_database()
    try:
        headers = register(client, "host@example.com", "organizer")
        organizer_id, venue_id = create_event_resources(client, headers, "host@example.com")
        created = client.post("/api/v1/events", headers=headers, json=event_payload(
            organizer_id, venue_id, status="published"
        ))
        assert created.status_code == 201, created.text
        response = client.get("/api/v1/events", params={"city": "Mumbai", "category": "TECH"})
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["title"] == "Backend Builders Meetup"
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_organizer_cannot_modify_another_organizers_event():
    client, engine = client_with_database()
    try:
        host_a = register(client, "host-a@example.com", "organizer")
        organizer_id, venue_id = create_event_resources(client, host_a, "host-a@example.com")
        created = client.post("/api/v1/events", headers=host_a, json=event_payload(
            organizer_id, venue_id, status="published"
        ))
        assert created.status_code == 201, created.text
        event_id = created.json()["id"]

        host_b = register(client, "host-b@example.com", "organizer")
        response = client.patch(f"/api/v1/events/{event_id}", headers=host_b, json={"title": "Hijacked"})
        assert response.status_code == 403
        assert client.get(f"/api/v1/events/{event_id}").json()["title"] == "Backend Builders Meetup"
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_invalid_event_dates_and_unknown_resources():
    client, engine = client_with_database()
    try:
        headers = register(client, "host@example.com", "organizer")
        missing = client.post("/api/v1/events", headers=headers, json=event_payload(999, 999))
        assert missing.status_code == 404
        organizer_id, venue_id = create_event_resources(client, headers, "host@example.com")
        created = client.post("/api/v1/events", headers=headers, json=event_payload(
            organizer_id, venue_id, status="published"
        ))
        assert created.status_code == 201, created.text
        event_id = created.json()["id"]
        invalid = client.patch(f"/api/v1/events/{event_id}", headers=headers, json={
            "ends_at": "2027-01-10T17:00:00"
        })
        assert invalid.status_code == 422
    finally:
        client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
