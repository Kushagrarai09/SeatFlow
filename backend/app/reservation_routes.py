"""Temporary ticket holds, confirmation, cancellation, expiry, and idempotency."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import Event, Reservation, TicketCategory, User
from app.schemas_reservations import ReservationCreate, ReservationRead

router = APIRouter(prefix="/api/v1", tags=["Reservations"])
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_roles("admin"))]
HOLD_MINUTES = 10


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _read(reservation: Reservation) -> dict:
    return {
        "id": reservation.id,
        "user_id": reservation.user_id,
        "ticket_category_id": reservation.ticket_category_id,
        "quantity": reservation.quantity,
        "unit_price": reservation.unit_price,
        "total_price": reservation.unit_price * reservation.quantity,
        "status": reservation.status,
        "idempotency_key": reservation.idempotency_key,
        "expires_at": reservation.expires_at,
        "confirmed_at": reservation.confirmed_at,
        "cancelled_at": reservation.cancelled_at,
        "created_at": reservation.created_at,
        "updated_at": reservation.updated_at,
    }


def _expire_due(db: Session, now: datetime, limit: int = 500) -> int:
    """Release holds that have expired; conditional state changes prevent double release."""
    due = list(db.scalars(
        select(Reservation)
        .where(Reservation.status == "pending", Reservation.expires_at <= now)
        .order_by(Reservation.expires_at, Reservation.id)
        .limit(limit)
        .with_for_update()
    ).all())
    expired = 0
    for reservation in due:
        # Transition the reservation only if it is still pending and due.
        result = db.execute(
            update(Reservation)
            .where(
                Reservation.id == reservation.id,
                Reservation.status == "pending",
                Reservation.expires_at <= now,
            )
            .values(status="expired", updated_at=now)
        )
        if result.rowcount != 1:
            continue
        released = db.execute(
            update(TicketCategory)
            .where(
                TicketCategory.id == reservation.ticket_category_id,
                TicketCategory.reserved_quantity >= reservation.quantity,
            )
            .values(reserved_quantity=TicketCategory.reserved_quantity - reservation.quantity,
                    updated_at=now)
        )
        if released.rowcount != 1:
            raise RuntimeError("Reservation inventory invariant violated during expiry")
        expired += 1
    return expired


def _get_reservation(db: Session, reservation_id: int, user: User) -> Reservation:
    reservation = db.scalar(
        select(Reservation).options(joinedload(Reservation.ticket_category))
        .where(Reservation.id == reservation_id)
    )
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if user.role != "admin" and reservation.user_id != user.id:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return reservation


@router.post("/reservations", response_model=ReservationRead, status_code=status.HTTP_201_CREATED)
def create_reservation(
    payload: ReservationCreate,
    db: DbSession,
    current_user: CurrentUser,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
):
    """Place a short hold. Replaying the same key and payload returns the original reservation."""
    key = idempotency_key.strip()
    if not key:
        raise HTTPException(status_code=422, detail="Idempotency-Key cannot be blank")
    fingerprint = hashlib.sha256(json.dumps(
        {"ticket_category_id": payload.ticket_category_id, "quantity": payload.quantity},
        sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()
    now = _now()

    existing = db.scalar(select(Reservation).where(
        Reservation.user_id == current_user.id,
        Reservation.idempotency_key == key,
    ))
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise HTTPException(status_code=409, detail="Idempotency-Key was already used with a different request")
        if existing.status == "pending" and existing.expires_at <= now:
            _expire_due(db, now)
            db.commit()
            db.refresh(existing)
        return _read(existing)

    # Expiry release and new allocation share one transaction.
    _expire_due(db, now)
    category = db.scalar(
        select(TicketCategory).where(TicketCategory.id == payload.ticket_category_id).with_for_update()
    )
    if category is None:
        db.rollback()
        raise HTTPException(status_code=404, detail="Ticket category not found")
    event = db.get(Event, category.event_id)
    if event is None or event.status != "published":
        db.rollback()
        raise HTTPException(status_code=409, detail="Tickets are not available for this event")
    if category.status != "active":
        db.rollback()
        raise HTTPException(status_code=409, detail="Ticket category is not available")
    if payload.quantity < category.min_per_order or payload.quantity > category.max_per_order:
        db.rollback()
        raise HTTPException(status_code=422, detail="Quantity is outside this category's order limits")
    if category.sales_start_at is not None and category.sales_start_at.replace(tzinfo=None) > now:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ticket sales have not started")
    if category.sales_end_at is not None and category.sales_end_at.replace(tzinfo=None) <= now:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ticket sales have ended")

    allocated = db.execute(
        update(TicketCategory)
        .where(
            TicketCategory.id == category.id,
            TicketCategory.status == "active",
            TicketCategory.total_quantity - TicketCategory.sold_quantity - TicketCategory.reserved_quantity >= payload.quantity,
        )
        .values(reserved_quantity=TicketCategory.reserved_quantity + payload.quantity, updated_at=now)
    )
    if allocated.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Not enough tickets are available")

    reservation = Reservation(
        user_id=current_user.id,
        ticket_category_id=category.id,
        quantity=payload.quantity,
        unit_price=category.price,
        status="pending",
        idempotency_key=key,
        request_fingerprint=fingerprint,
        expires_at=now + timedelta(minutes=HOLD_MINUTES),
    )
    db.add(reservation)
    try:
        db.commit()
    except IntegrityError as exc:
        # A simultaneous replay may win the unique-key race. Roll back inventory
        # allocation and return the winning reservation if its payload matches.
        db.rollback()
        existing = db.scalar(select(Reservation).where(
            Reservation.user_id == current_user.id,
            Reservation.idempotency_key == key,
        ))
        if existing is not None and existing.request_fingerprint == fingerprint:
            return _read(existing)
        raise HTTPException(status_code=409, detail="Idempotency-Key conflict; retry with the original key") from exc
    db.refresh(reservation)
    return _read(reservation)


@router.get("/reservations/{reservation_id}", response_model=ReservationRead)
def get_reservation(reservation_id: int, db: DbSession, current_user: CurrentUser):
    _expire_due(db, _now())
    db.commit()
    reservation = _get_reservation(db, reservation_id, current_user)
    return _read(reservation)


@router.post("/reservations/{reservation_id}/confirm", response_model=ReservationRead)
def confirm_reservation(reservation_id: int, db: DbSession, current_user: CurrentUser):
    """Confirm a live hold and atomically move quantity from reserved to sold."""
    now = _now()
    _expire_due(db, now)
    reservation = db.scalar(select(Reservation).where(
        Reservation.id == reservation_id
    ).with_for_update())
    if reservation is None or (current_user.role != "admin" and reservation.user_id != current_user.id):
        db.commit()
        raise HTTPException(status_code=404, detail="Reservation not found")
    if reservation.status == "confirmed":
        db.commit()
        return _read(reservation)
    if reservation.status != "pending" or reservation.expires_at <= now:
        db.commit()
        raise HTTPException(status_code=409, detail=f"Reservation cannot be confirmed because it is {reservation.status}")
    moved = db.execute(
        update(TicketCategory)
        .where(
            TicketCategory.id == reservation.ticket_category_id,
            TicketCategory.reserved_quantity >= reservation.quantity,
        )
        .values(
            reserved_quantity=TicketCategory.reserved_quantity - reservation.quantity,
            sold_quantity=TicketCategory.sold_quantity + reservation.quantity,
            updated_at=now,
        )
    )
    if moved.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Inventory changed; reservation could not be confirmed")
    reservation.status = "confirmed"
    reservation.confirmed_at = now
    reservation.updated_at = now
    db.commit()
    db.refresh(reservation)
    return _read(reservation)


@router.post("/reservations/{reservation_id}/cancel", response_model=ReservationRead)
def cancel_reservation(reservation_id: int, db: DbSession, current_user: CurrentUser):
    """Cancel a pending hold or confirmed reservation; only pending holds release inventory."""
    now = _now()
    reservation = db.scalar(select(Reservation).where(
        Reservation.id == reservation_id
    ).with_for_update())
    if reservation is None or (current_user.role != "admin" and reservation.user_id != current_user.id):
        raise HTTPException(status_code=404, detail="Reservation not found")
    if reservation.status == "cancelled":
        return _read(reservation)
    if reservation.status == "expired":
        raise HTTPException(status_code=409, detail="Expired reservation cannot be cancelled")
    if reservation.status == "confirmed":
        # Refunds/payment reversals are deliberately not implied by this MVP.
        raise HTTPException(status_code=409, detail="Confirmed bookings require a separate refund/cancellation workflow")
    released = db.execute(
        update(TicketCategory)
        .where(
            TicketCategory.id == reservation.ticket_category_id,
            TicketCategory.reserved_quantity >= reservation.quantity,
        )
        .values(reserved_quantity=TicketCategory.reserved_quantity - reservation.quantity, updated_at=now)
    )
    if released.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Inventory changed; reservation could not be cancelled")
    reservation.status = "cancelled"
    reservation.cancelled_at = now
    reservation.updated_at = now
    db.commit()
    db.refresh(reservation)
    return _read(reservation)


@router.post("/admin/reservations/expire", tags=["Administration"])
def expire_reservations(db: DbSession, _: AdminUser, limit: Annotated[int, Query(ge=1, le=5000)] = 500):
    """Admin-triggered expiry sweep; production should invoke this from a scheduled worker."""
    count = _expire_due(db, _now(), limit=limit)
    db.commit()
    return {"expired_count": count}
