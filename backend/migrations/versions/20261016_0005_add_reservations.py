"""Add time-limited reservations and idempotency keys.

Revision ID: 20261016_0005
Revises: 20261016_0004
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261016_0005"
down_revision: Union[str, None] = "20261016_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reservations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ticket_category_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_reservations_quantity_positive"),
        sa.CheckConstraint("status IN ('pending', 'confirmed', 'expired', 'cancelled')",
                           name="ck_reservations_status_valid"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ticket_category_id"], ["ticket_categories.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_reservations_user_idempotency"),
    )
    op.create_index("ix_reservations_status_expiry", "reservations", ["status", "expires_at"])
    op.create_index("ix_reservations_user_created", "reservations", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_reservations_user_created", table_name="reservations")
    op.drop_index("ix_reservations_status_expiry", table_name="reservations")
    op.drop_table("reservations")
