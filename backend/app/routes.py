"""Versioned CRUD and discovery endpoints for the SeatFlow domain."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Event, Organizer, Venue
from app.schemas import (
    EventCreate,
    EventRead,
    OrganizerCreate,
    OrganizerRead,
    VenueCreate,
    VenueRead,
)

router = APIRouter(prefix="/api/v1", tags=["Events and catalog"])
DbSession = Annotated[Session, Depends(get_db)]


def _get_venue(db: Session, venue_id: int) -> Venue:
    venue = db.get(Venue, venue_id)
    if venue is None:
        raise HTTPException(status_code=404, detail="Venue not found")
    return venue


def _get_organizer(db: Session, organizer_id: int) -> Organizer:
    organizer = db.get(Organizer, organizer_id)
    if organizer is None:
        raise HTTPException(status_code=404, detail="Organizer not found")
    return organizer


def _get_event(db: Session, event_id: int) -> Event:
    event = db.scalar(
        select(Event)
        .options(joinedload(Event.venue), joinedload(Event.organizer))
        .where(Event.id == event_id)
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("/venues", response_model=VenueRead, status_code=status.HTTP_201_CREATED)
def create_venue(payload: VenueCreate, db: DbSession) -> Venue:
    """Create a venue. This management endpoint requires auth in a later phase."""
    venue = Venue(**payload.model_dump())
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


@router.get("/venues", response_model=list[VenueRead])
def list_venues(
    db: DbSession,
    city: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[Venue]:
    statement = select(Venue).order_by(Venue.city, Venue.name)
    if city:
        statement = statement.where(Venue.city.ilike(f"%{city.strip()}%"))
    return list(db.scalars(statement.offset(offset).limit(limit)).all())


@router.post("/organizers", response_model=OrganizerRead, status_code=status.HTTP_201_CREATED)
def create_organizer(payload: OrganizerCreate, db: DbSession) -> Organizer:
    """Create an organizer profile. This management endpoint requires auth in a later phase."""
    organizer = Organizer(**payload.model_dump())
    db.add(organizer)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        # Do not leak SQL, database credentials, or driver internals in API errors.
        from sqlalchemy.exc import IntegrityError

        if isinstance(exc, IntegrityError):
            raise HTTPException(status_code=409, detail="An organizer with this email already exists") from exc
        raise
    db.refresh(organizer)
    return organizer


@router.get("/organizers", response_model=list[OrganizerRead])
def list_organizers(
    db: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[Organizer]:
    return list(db.scalars(select(Organizer).order_by(Organizer.name).offset(offset).limit(limit)).all())


@router.post("/events", response_model=EventRead, status_code=status.HTTP_201_CREATED)
def create_event(payload: EventCreate, db: DbSession) -> Event:
    """Create an event listing. Organizer authorization is added with authentication."""
    _get_organizer(db, payload.organizer_id)
    _get_venue(db, payload.venue_id)
    event = Event(**payload.model_dump())
    db.add(event)
    db.commit()
    return _get_event(db, event.id)


@router.get("/events", response_model=list[EventRead])
def discover_events(
    db: DbSession,
    q: Annotated[str | None, Query(min_length=1, max_length=180)] = None,
    category: Annotated[str | None, Query(min_length=1, max_length=80)] = None,
    city: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    starts_after: datetime | None = None,
    starts_before: datetime | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[Event]:
    """Discover only published events, with optional text, category, city, and date filters."""
    statement = (
        select(Event)
        .join(Event.venue)
        .options(joinedload(Event.venue), joinedload(Event.organizer))
        .where(Event.status == "published")
        .order_by(Event.starts_at, Event.id)
    )
    if q:
        statement = statement.where(Event.title.ilike(f"%{q.strip()}%"))
    if category:
        statement = statement.where(Event.category.ilike(f"%{category.strip()}%"))
    if city:
        statement = statement.where(Venue.city.ilike(f"%{city.strip()}%"))
    if starts_after:
        statement = statement.where(Event.starts_at >= starts_after)
    if starts_before:
        statement = statement.where(Event.starts_at <= starts_before)
    if starts_after and starts_before and starts_after > starts_before:
        raise HTTPException(status_code=422, detail="starts_after must be earlier than starts_before")
    return list(db.scalars(statement.offset(offset).limit(limit)).unique().all())


@router.get("/events/{event_id}", response_model=EventRead)
def get_public_event(event_id: int, db: DbSession) -> Event:
    event = _get_event(db, event_id)
    if event.status != "published":
        # Unpublished drafts should not be available through public discovery APIs.
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.patch("/events/{event_id}", response_model=EventRead)
def update_event(event_id: int, payload: "EventUpdate", db: DbSession) -> Event:
    """Partially update an event. Add organizer ownership checks with authentication."""
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    changes = payload.model_dump(exclude_unset=True)
    if "organizer_id" in changes:
        _get_organizer(db, changes["organizer_id"])
    if "venue_id" in changes:
        _get_venue(db, changes["venue_id"])
    proposed_start = changes.get("starts_at", event.starts_at)
    proposed_end = changes.get("ends_at", event.ends_at)
    try:
        invalid_range = proposed_end <= proposed_start
    except TypeError as exc:
        raise HTTPException(status_code=422, detail="Event timestamps must use compatible timezone information") from exc
    if invalid_range:
        raise HTTPException(status_code=422, detail="ends_at must be later than starts_at")
    for field, value in changes.items():
        setattr(event, field, value)
    db.commit()
    return _get_event(db, event.id)


class EventUpdate(EventCreate):
    """Optional version of EventCreate used for PATCH updates."""

    organizer_id: int | None = None
    venue_id: int | None = None
    title: str | None = None
    description: str | None = None
    category: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    price: Decimal | None = None
    capacity: int | None = None
    status: str | None = None

    # The shared create validators assume both timestamps exist, so PATCH validates
    # the combined start/end range in update_event instead.
    model_config = {"extra": "forbid"}
