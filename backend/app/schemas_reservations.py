"""Request and response schemas for temporary ticket reservations."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ReservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_category_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=100)


class ReservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    ticket_category_id: int
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    status: str
    idempotency_key: str
    expires_at: datetime
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime
