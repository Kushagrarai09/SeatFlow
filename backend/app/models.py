"""Initial SeatFlow domain models."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Venue(Base):
    """A physical or virtual location where an event takes place."""
    __tablename__ = "venues"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="ck_venues_capacity_positive"),
        Index("ix_venues_city_name", "city", "name"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="India")
    capacity: Mapped[int] = mapped_column(nullable=False)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    events: Mapped[list["Event"]] = relationship(back_populates="venue")
    owner: Mapped["User | None"] = relationship(back_populates="venues")


class Organizer(Base):
    """An event-hosting organization or individual."""
    __tablename__ = "organizers"
    __table_args__ = (
        UniqueConstraint("email", name="uq_organizers_email"),
        UniqueConstraint("user_id", name="uq_organizers_user_id"),
        Index("ix_organizers_name", "name"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    events: Mapped[list["Event"]] = relationship(back_populates="organizer")
    user: Mapped["User | None"] = relationship(back_populates="organizer_profile")


class Event(Base):
    """An event listing hosted by an organizer at a venue."""
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_events_price_nonnegative"),
        CheckConstraint("capacity > 0", name="ck_events_capacity_positive"),
        CheckConstraint("status IN ('draft', 'published', 'cancelled', 'completed')", name="ck_events_status_valid"),
        Index("ix_events_status_starts_at", "status", "starts_at"),
        Index("ix_events_venue_starts_at", "venue_id", "starts_at"),
        Index("ix_events_organizer_starts_at", "organizer_id", "starts_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    organizer_id: Mapped[int] = mapped_column(ForeignKey("organizers.id", ondelete="RESTRICT"), nullable=False)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id", ondelete="RESTRICT"), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    capacity: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    organizer: Mapped["Organizer"] = relationship(back_populates="events")
    venue: Mapped["Venue"] = relationship(back_populates="events")


class User(Base):
    """Account identity and authorization role; separate from public organizer profiles."""
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint("role IN ('attendee', 'organizer', 'admin')", name="ck_users_role_valid"),
        Index("ix_users_role_active", "role", "is_active"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="attendee")
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    venues: Mapped[list["Venue"]] = relationship(back_populates="owner")
    organizer_profile: Mapped["Organizer | None"] = relationship(back_populates="user", uselist=False)


class RefreshToken(Base):
    """Digest-only refresh token registry for rotation and revocation."""
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        UniqueConstraint("token_digest", name="uq_refresh_tokens_digest"),
        Index("ix_refresh_tokens_user_expiry", "user_id", "expires_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")
