"""Unit tests for the initial SQLAlchemy domain model metadata."""

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Event, Organizer, Venue


def test_schema_creates_expected_tables_and_relationships():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)

    assert set(inspector.get_table_names()) == {"events", "organizers", "venues", "users", "refresh_tokens", "ticket_categories"}
    assert {fk["referred_table"] for fk in inspector.get_foreign_keys("events")} == {
        "organizers", "venues"
    }
    engine.dispose()


def test_event_links_to_organizer_and_venue():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        organizer = Organizer(name="SeatFlow Demo", email="host@example.test")
        venue = Venue(
            name="Studio Hall", address="1 Example Road", city="Mumbai",
            country="India", capacity=250,
        )
        session.add_all([organizer, venue])
        session.flush()

        from datetime import datetime, timezone
        from decimal import Decimal

        event = Event(
            organizer_id=organizer.id,
            venue_id=venue.id,
            title="Launch Night",
            category="community",
            starts_at=datetime(2027, 1, 10, 18, tzinfo=timezone.utc),
            ends_at=datetime(2027, 1, 10, 21, tzinfo=timezone.utc),
            price=Decimal("499.00"),
            capacity=200,
            status="draft",
        )
        session.add(event)
        session.commit()
        session.refresh(event)

        assert event.organizer.name == "SeatFlow Demo"
        assert event.venue.name == "Studio Hall"
        assert organizer.events[0].title == "Launch Night"

    engine.dispose()
