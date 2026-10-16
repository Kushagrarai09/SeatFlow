"""Ticket category and inventory APIs."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import Event, TicketCategory, User
from app.schemas import TicketCategoryCreate, TicketCategoryRead, TicketCategoryUpdate

router = APIRouter(prefix="/api/v1", tags=["Ticket inventory"])
DbSession = Annotated[Session, Depends(get_db)]
OrganizerOrAdmin = Annotated[User, Depends(require_roles("organizer", "admin"))]


def _get_event(db: Session, event_id: int) -> Event:
    event = db.scalar(select(Event).options(joinedload(Event.organizer)).where(Event.id == event_id))
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


def _assert_event_owner(event: Event, user: User) -> None:
    if user.role != "admin" and event.organizer.user_id != user.id:
        raise HTTPException(status_code=403, detail="You cannot manage tickets for this event")


def _to_read(category: TicketCategory) -> TicketCategoryRead:
    now = datetime.now(timezone.utc)
    remaining = max(0, category.total_quantity - category.sold_quantity - category.reserved_quantity)
    starts = category.sales_start_at
    ends = category.sales_end_at
    # Normalize naive timestamps from SQLite into UTC for deterministic test behavior.
    if starts is not None and starts.tzinfo is None:
        starts = starts.replace(tzinfo=timezone.utc)
    if ends is not None and ends.tzinfo is None:
        ends = ends.replace(tzinfo=timezone.utc)
    window_open = ((starts is None or starts <= now) and (ends is None or ends > now))
    return TicketCategoryRead(
        id=category.id,
        event_id=category.event_id,
        name=category.name,
        description=category.description,
        price=category.price,
        total_quantity=category.total_quantity,
        sold_quantity=category.sold_quantity,
        reserved_quantity=category.reserved_quantity,
        available_quantity=remaining,
        min_per_order=category.min_per_order,
        max_per_order=category.max_per_order,
        sales_start_at=category.sales_start_at,
        sales_end_at=category.sales_end_at,
        status=category.status,
        sales_open=category.status == "active" and remaining > 0 and window_open,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


def _get_category(db: Session, event_id: int, category_id: int) -> TicketCategory:
    category = db.scalar(select(TicketCategory).where(
        TicketCategory.id == category_id,
        TicketCategory.event_id == event_id,
    ))
    if category is None:
        raise HTTPException(status_code=404, detail="Ticket category not found")
    return category


def _validate_inventory_change(category: TicketCategory, changes: dict) -> None:
    total = changes.get("total_quantity", category.total_quantity)
    sold = category.sold_quantity
    reserved = category.reserved_quantity
    if total < sold + reserved:
        raise HTTPException(status_code=409, detail="total_quantity cannot be less than sold plus reserved tickets")
    minimum = changes.get("min_per_order", category.min_per_order)
    maximum = changes.get("max_per_order", category.max_per_order)
    if maximum < minimum:
        raise HTTPException(status_code=422, detail="max_per_order must be greater than or equal to min_per_order")
    starts = changes.get("sales_start_at", category.sales_start_at)
    ends = changes.get("sales_end_at", category.sales_end_at)
    if starts is not None and ends is not None:
        if starts.tzinfo is None:
            starts = starts.replace(tzinfo=timezone.utc)
        if ends.tzinfo is None:
            ends = ends.replace(tzinfo=timezone.utc)
        if ends <= starts:
            raise HTTPException(status_code=422, detail="sales_end_at must be later than sales_start_at")


@router.post(
    "/events/{event_id}/ticket-categories",
    response_model=TicketCategoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_ticket_category(
    event_id: int,
    payload: TicketCategoryCreate,
    db: DbSession,
    current_user: OrganizerOrAdmin,
) -> TicketCategoryRead:
    event = _get_event(db, event_id)
    _assert_event_owner(event, current_user)
    if event.status in ("cancelled", "completed"):
        raise HTTPException(status_code=409, detail="Cannot add ticket categories to a cancelled or completed event")
    if payload.total_quantity > event.capacity:
        raise HTTPException(status_code=422, detail="Ticket category quantity cannot exceed the event capacity")
    category = TicketCategory(
        event_id=event.id,
        name=payload.name,
        description=payload.description,
        price=payload.price,
        total_quantity=payload.total_quantity,
        min_per_order=payload.min_per_order,
        max_per_order=payload.max_per_order,
        sales_start_at=payload.sales_start_at,
        sales_end_at=payload.sales_end_at,
        status=payload.status,
    )
    db.add(category)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A ticket category with this name already exists for the event") from exc
    db.refresh(category)
    return _to_read(category)


@router.get("/events/{event_id}/ticket-categories", response_model=list[TicketCategoryRead])
def list_ticket_categories(
    event_id: int,
    db: DbSession,
    include_inactive: bool = Query(default=False),
    current_user: User | None = Depends(get_current_user),
) -> list[TicketCategoryRead]:
    """Public users see active ticket types; owners/admins may request inactive ones."""
    event = _get_event(db, event_id)
    is_manager = current_user is not None and (
        current_user.role == "admin" or event.organizer.user_id == current_user.id
    )
    if include_inactive and not is_manager:
        raise HTTPException(status_code=403, detail="Only the event organizer or an administrator can view inactive ticket categories")
    if event.status != "published" and not is_manager:
        raise HTTPException(status_code=404, detail="Event not found")
    statement = select(TicketCategory).where(TicketCategory.event_id == event_id)
    if not include_inactive and not is_manager:
        statement = statement.where(TicketCategory.status == "active")
    return [_to_read(item) for item in db.scalars(statement.order_by(TicketCategory.price, TicketCategory.id)).all()]


@router.get("/events/{event_id}/ticket-categories/{category_id}", response_model=TicketCategoryRead)
def get_ticket_category(
    event_id: int,
    category_id: int,
    db: DbSession,
    current_user: User | None = Depends(get_current_user),
) -> TicketCategoryRead:
    event = _get_event(db, event_id)
    is_manager = current_user is not None and (
        current_user.role == "admin" or event.organizer.user_id == current_user.id
    )
    if event.status != "published" and not is_manager:
        raise HTTPException(status_code=404, detail="Event not found")
    category = _get_category(db, event_id, category_id)
    if category.status != "active" and not is_manager:
        raise HTTPException(status_code=404, detail="Ticket category not found")
    return _to_read(category)


@router.patch("/events/{event_id}/ticket-categories/{category_id}", response_model=TicketCategoryRead)
def update_ticket_category(
    event_id: int,
    category_id: int,
    payload: TicketCategoryUpdate,
    db: DbSession,
    current_user: OrganizerOrAdmin,
) -> TicketCategoryRead:
    event = _get_event(db, event_id)
    _assert_event_owner(event, current_user)
    category = _get_category(db, event_id, category_id)
    changes = payload.model_dump(exclude_unset=True)
    for field in ("name", "price", "total_quantity", "min_per_order", "max_per_order", "status"):
        if field in changes and changes[field] is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
    if "total_quantity" in changes and changes["total_quantity"] > event.capacity:
        raise HTTPException(status_code=422, detail="Ticket category quantity cannot exceed event capacity")
    _validate_inventory_change(category, changes)
    for field, value in changes.items():
        setattr(category, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ticket category name already exists for this event") from exc
    db.refresh(category)
    return _to_read(category)


@router.delete(
    "/events/{event_id}/ticket-categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_ticket_category(
    event_id: int,
    category_id: int,
    db: DbSession,
    current_user: OrganizerOrAdmin,
) -> None:
    event = _get_event(db, event_id)
    _assert_event_owner(event, current_user)
    category = _get_category(db, event_id, category_id)
    if category.sold_quantity or category.reserved_quantity:
        raise HTTPException(status_code=409, detail="Ticket categories with sold or reserved inventory cannot be deleted; mark them inactive instead")
    db.delete(category)
    db.commit()


@router.post("/ticket-categories/{category_id}/inventory/adjust", response_model=TicketCategoryRead)
def adjust_inventory(
    category_id: int,
    quantity_delta: Annotated[int, Query(ne=0, ge=-1_000_000, le=1_000_000)],
    db: DbSession,
    current_user: OrganizerOrAdmin,
) -> TicketCategoryRead:
    """Apply atomic stock adjustment without going below sold/reserved units."""
    category = db.get(TicketCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Ticket category not found")
    event = _get_event(db, category.event_id)
    _assert_event_owner(event, current_user)
    if event.status in ("cancelled", "completed"):
        raise HTTPException(status_code=409, detail="Cannot adjust inventory for a cancelled or completed event")
    statement = (
        update(TicketCategory)
        .where(
            TicketCategory.id == category_id,
            TicketCategory.total_quantity + quantity_delta >= TicketCategory.sold_quantity + TicketCategory.reserved_quantity,
            TicketCategory.total_quantity + quantity_delta > 0,
            TicketCategory.total_quantity + quantity_delta <= event.capacity,
        )
        .values(total_quantity=TicketCategory.total_quantity + quantity_delta)
    )
    result = db.execute(statement)
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Inventory adjustment would make capacity invalid or lower than sold/reserved quantity")
    db.commit()
    db.refresh(category)
    return _to_read(category)
