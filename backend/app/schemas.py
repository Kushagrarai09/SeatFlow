"""Pydantic schemas for the initial SeatFlow domain models."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORMReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VenueCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    address: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    country: str = Field(default="India", min_length=1, max_length=100)
    capacity: int = Field(gt=0)


class VenueRead(VenueCreate, ORMReadModel):
    id: int
    created_at: datetime
    updated_at: datetime


class OrganizerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=254)
    description: str | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("A valid email address is required")
        return value


class OrganizerRead(OrganizerCreate, ORMReadModel):
    id: int
    created_at: datetime
    updated_at: datetime


class EventCreate(BaseModel):
    organizer_id: int = Field(gt=0)
    venue_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=180)
    description: str | None = None
    category: str = Field(min_length=1, max_length=80)
    starts_at: datetime
    ends_at: datetime
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    capacity: int = Field(gt=0)
    status: str = Field(default="draft", pattern="^(draft|published|cancelled|completed)$")

    @field_validator("ends_at")
    @classmethod
    def end_must_follow_start(cls, value: datetime, info) -> datetime:
        start = info.data.get("starts_at")
        if start is not None and value <= start:
            raise ValueError("ends_at must be later than starts_at")
        return value


class EventRead(EventCreate, ORMReadModel):
    id: int
    created_at: datetime
    updated_at: datetime
