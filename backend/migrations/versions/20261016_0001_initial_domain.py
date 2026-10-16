"""Create the initial SeatFlow domain tables.

Revision ID: 20261016_0001
Revises:
Create Date: 2026-10-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261016_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "venues",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("address", sa.String(255), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("country", sa.String(100), server_default="India", nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("capacity > 0", name="ck_venues_capacity_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_venues_city_name", "venues", ["city", "name"])

    op.create_table(
        "organizers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_organizers_email"),
    )
    op.create_index("ix_organizers_name", "organizers", ["name"])

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organizer_id", sa.Integer(), nullable=False),
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("price >= 0", name="ck_events_price_nonnegative"),
        sa.CheckConstraint("capacity > 0", name="ck_events_capacity_positive"),
        sa.CheckConstraint("status IN ('draft', 'published', 'cancelled', 'completed')", name="ck_events_status_valid"),
        sa.ForeignKeyConstraint(["organizer_id"], ["organizers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_status_starts_at", "events", ["status", "starts_at"])
    op.create_index("ix_events_venue_starts_at", "events", ["venue_id", "starts_at"])
    op.create_index("ix_events_organizer_starts_at", "events", ["organizer_id", "starts_at"])


def downgrade() -> None:
    op.drop_index("ix_events_organizer_starts_at", table_name="events")
    op.drop_index("ix_events_venue_starts_at", table_name="events")
    op.drop_index("ix_events_status_starts_at", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_organizers_name", table_name="organizers")
    op.drop_table("organizers")
    op.drop_index("ix_venues_city_name", table_name="venues")
    op.drop_table("venues")
