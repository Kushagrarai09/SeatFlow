"""Versioned catalog endpoints with authentication and ownership authorization."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import Event, Organizer, User, Venue
from app.schemas import EventCreate, EventRead, OrganizerCreate, OrganizerRead, VenueCreate, VenueRead

router = APIRouter(prefix="/api/v1", tags=["Events and catalog"])
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
OrganizerOrAdmin = Annotated[User, Depends(require_roles("organizer", "admin"))]


class EventUpdate(BaseModel):
    """Partial event update schema. Omitted fields remain unchanged."""
    model_config = ConfigDict(extra="forbid")
    organizer_id: int | None = Field(default=None, gt=0)
    venue_id: int | None = Field(default=None, gt=0)
    title: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = None
    category: str | None = Field(default=None, min_length=1, max_length=80)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    capacity: int | None = Field(default=None, gt=0)
    status: str | None = Field(default=None, pattern="^(draft|published|cancelled|completed)$")


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
        select(Event).options(joinedload(Event.venue), joinedload(Event.organizer))
        .where(Event.id == event_id)
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


def _ensure_venue_access(user: User, venue: Venue) -> None:
    if user.role != "admin" and venue.owner_user_id not in (None, user.id):
        raise HTTPException(status_code=403, detail="You cannot manage this venue")


def _ensure_event_access(user: User, event: Event) -> None:
    if user.role == "admin":
        return
    if event.organizer.user_id != user.id:
        raise HTTPException(status_code=403, detail="You cannot manage this event")
    _ensure_venue_access(user, event.venue)


@router.post("/venues", response_model=VenueRead, status_code=status.HTTP_201_CREATED)
def create_venue(payload: VenueCreate, db: DbSession, current_user: OrganizerOrAdmin) -> Venue:
    """Create a venue as an organizer or administrator."""
    venue = Venue(**payload.model_dump(), owner_user_id=current_user.id if current_user.role == "organizer" else None)
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
        statement = statement.where(Venue.city.ilike("%" + city.strip() + "%"))
    return list(db.scalars(statement.offset(offset).limit(limit)).all())


@router.post("/organizers", response_model=OrganizerRead, status_code=status.HTTP_201_CREATED)
def create_organizer(payload: OrganizerCreate, db: DbSession, current_user: OrganizerOrAdmin) -> Organizer:
    """Create a profile linked to the current organizer account."""
    linked_user_id = current_user.id if current_user.role == "organizer" else None
    if linked_user_id is not None:
        existing = db.scalar(select(Organizer).where(Organizer.user_id == linked_user_id))
        if existing is not None:
            raise HTTPException(status_code=409, detail="This account already has an organizer profile")
    organizer = Organizer(**payload.model_dump(), user_id=linked_user_id)
    db.add(organizer)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An organizer with this email already exists") from exc
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
def create_event(payload: EventCreate, db: DbSession, current_user: OrganizerOrAdmin) -> Event:
    """Create an event and enforce that organizers use their own profile."""
    organizer = _get_organizer(db, payload.organizer_id)
    venue = _get_venue(db, payload.venue_id)
    if current_user.role != "admin":
        if organizer.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You cannot create events for another organizer")
        _ensure_venue_access(current_user, venue)
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
    """Public discovery endpoint: only published events are visible."""
    if starts_after and starts_before and starts_after > starts_before:
        raise HTTPException(status_code=422, detail="starts_after must be earlier than starts_before")
    statement = (
        select(Event).join(Event.venue)
        .options(joinedload(Event.venue), joinedload(Event.organizer))
        .where(Event.status == "published").order_by(Event.starts_at, Event.id)
    )
    if q:
        statement = statement.where(Event.title.ilike("%" + q.strip() + "%"))
    if category:
        statement = statement.where(Event.category.ilike("%" + category.strip() + "%"))
    if city:
        statement = statement.where(Venue.city.ilike("%" + city.strip() + "%"))
    if starts_after:
        statement = statement.where(Event.starts_at >= starts_after)
    if starts_before:
        statement = statement.where(Event.starts_at <= starts_before)
    return list(db.scalars(statement.offset(offset).limit(limit)).unique().all())


@router.get("/events/{event_id}", response_model=EventRead)
def get_public_event(event_id: int, db: DbSession) -> Event:
    event = _get_event(db, event_id)
    if event.status != "published":
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.patch("/events/{event_id}", response_model=EventRead)
def update_event(event_id: int, payload: EventUpdate, db: DbSession, current_user: OrganizerOrAdmin) -> Event:
    """Update an event only if the caller owns it or is an administrator."""
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    # Load relationships while the session is active before making any changes.
    event = _get_event(db, event_id)
    _ensure_event_access(current_user, event)

    changes = payload.model_dump(exclude_unset=True)
    if "organizer_id" in changes:
        if changes["organizer_id"] is None:
            raise HTTPException(status_code=422, detail="organizer_id cannot be null")
        proposed_organizer = _get_organizer(db, changes["organizer_id"])
        if current_user.role != "admin" and proposed_organizer.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You cannot assign this event to another organizer")
    if "venue_id" in changes:
        if changes["venue_id"] is None:
            raise HTTPException(status_code=422, detail="venue_id cannot be null")
        _ensure_venue_access(current_user, _get_venue(db, changes["venue_id"]))
    required_fields = ("title", "category", "starts_at", "ends_at", "price", "capacity", "status")
    if any(field in changes and changes[field] is None for field in required_fields):
        raise HTTPException(status_code=422, detail="Required event fields cannot be null")
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
