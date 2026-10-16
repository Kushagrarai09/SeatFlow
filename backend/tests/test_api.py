"""API tests using an isolated SQLite database; no MySQL server is needed."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def create_event_resources(client: TestClient) -> tuple[int, int]:
    organizer_response = client.post(
        "/api/v1/organizers",
        json={"name": "SeatFlow Demo", "email": "host@example.test"},
    )
    assert organizer_response.status_code == 201
    venue_response = client.post(
        "/api/v1/venues",
        json={
            "name": "Example Hall",
            "address": "1 Example Road",
            "city": "Mumbai",
            "country": "India",
            "capacity": 300,
        },
    )
    assert venue_response.status_code == 201
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


def test_create_event_and_keep_drafts_out_of_public_discovery(client):
    organizer_id, venue_id = create_event_resources(client)
    create_response = client.post(
        "/api/v1/events",
        json=event_payload(organizer_id, venue_id),
    )
    assert create_response.status_code == 201
    event_id = create_response.json()["id"]

    discovery = client.get("/api/v1/events")
    assert discovery.status_code == 200
    assert discovery.json() == []

    detail = client.get(f"/api/v1/events/{event_id}")
    assert detail.status_code == 404


def test_publish_event_and_filter_discovery_by_city_and_category(client):
    organizer_id, venue_id = create_event_resources(client)
    create_response = client.post(
        "/api/v1/events",
        json=event_payload(organizer_id, venue_id, status="published"),
    )
    assert create_response.status_code == 201

    response = client.get("/api/v1/events", params={"city": "Mumbai", "category": "TECH"})
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Backend Builders Meetup"


def test_event_rejects_unknown_organizer_or_venue(client):
    response = client.post(
        "/api/v1/events",
        json=event_payload(organizer_id=999, venue_id=999),
    )
    assert response.status_code == 404


def test_duplicate_organizer_email_returns_conflict(client):
    first = client.post(
        "/api/v1/organizers",
        json={"name": "Organizer One", "email": "same@example.test"},
    )
    second = client.post(
        "/api/v1/organizers",
        json={"name": "Organizer Two", "email": "SAME@example.test"},
    )
    assert first.status_code == 201
    # Emails are normalized by the request schema, so the DB uniqueness constraint applies.
    assert second.status_code == 409


def test_patch_event_updates_only_supplied_fields_and_rejects_invalid_dates(client):
    organizer_id, venue_id = create_event_resources(client)
    created = client.post(
        "/api/v1/events",
        json=event_payload(organizer_id, venue_id, status="published"),
    )
    event_id = created.json()["id"]

    patch_response = client.patch(f"/api/v1/events/{event_id}", json={"title": "Updated Meetup"})
    assert patch_response.status_code == 200
    assert patch_response.json()["title"] == "Updated Meetup"
    assert patch_response.json()["category"] == "technology"

    invalid_response = client.patch(
        f"/api/v1/events/{event_id}",
        json={"ends_at": "2027-01-10T17:00:00Z"},
    )
    assert invalid_response.status_code == 422
