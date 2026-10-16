"""Pydantic schemas for the initial SeatFlow domain models."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class TicketCategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    total_quantity: int = Field(gt=0, le=1_000_000)
    min_per_order: int = Field(default=1, ge=1, le=100)
    max_per_order: int = Field(default=10, ge=1, le=100)
    sales_start_at: datetime | None = None
    sales_end_at: datetime | None = None
    status: str = Field(default="active", pattern="^(active|inactive)$")

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Ticket category name cannot be blank")
        return value

    @model_validator(mode="after")
    def validate_rules(self):
        if self.max_per_order < self.min_per_order:
            raise ValueError("max_per_order must be greater than or equal to min_per_order")
        if self.sales_start_at is not None and self.sales_end_at is not None:
            start = self.sales_start_at
            end = self.sales_end_at
            if start.tzinfo is None:
                start = start.replace(tzinfo=__import__("datetime").timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=__import__("datetime").timezone.utc)
            if end <= start:
                raise ValueError("sales_end_at must be later than sales_start_at")
        return self


class TicketCategoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    total_quantity: int | None = Field(default=None, gt=0, le=1_000_000)
    min_per_order: int | None = Field(default=None, ge=1, le=100)
    max_per_order: int | None = Field(default=None, ge=1, le=100)
    sales_start_at: datetime | None = None
    sales_end_at: datetime | None = None
    status: str | None = Field(default=None, pattern="^(active|inactive)$")

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Ticket category name cannot be blank")
        return value

    @model_validator(mode="after")
    def validate_rules(self):
        if self.min_per_order is not None and self.max_per_order is not None:
            if self.max_per_order < self.min_per_order:
                raise ValueError("max_per_order must be greater than or equal to min_per_order")
        if self.sales_start_at is not None and self.sales_end_at is not None:
            start = self.sales_start_at
            end = self.sales_end_at
            if start.tzinfo is None:
                start = start.replace(tzinfo=__import__("datetime").timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=__import__("datetime").timezone.utc)
            if end <= start:
                raise ValueError("sales_end_at must be later than sales_start_at")
        return self


class TicketCategoryRead(ORMReadModel):
    id: int
    event_id: int
    name: str
    description: str | None
    price: Decimal
    total_quantity: int
    sold_quantity: int
    reserved_quantity: int
    available_quantity: int
    min_per_order: int
    max_per_order: int
    sales_start_at: datetime | None
    sales_end_at: datetime | None
    status: str
    sales_open: bool
    created_at: datetime
    updated_at: datetime
