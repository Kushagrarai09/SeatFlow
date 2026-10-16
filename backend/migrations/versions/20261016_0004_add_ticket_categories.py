"""Add general-admission ticket categories and inventory.

Revision ID: 20261016_0004
Revises: 20261016_0003
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261016_0004"
down_revision: Union[str, None] = "20261016_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ticket_categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_quantity", sa.Integer(), nullable=False),
        sa.Column("sold_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reserved_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("min_per_order", sa.Integer(), server_default="1", nullable=False),
        sa.Column("max_per_order", sa.Integer(), server_default="10", nullable=False),
        sa.Column("sales_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sales_end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("price >= 0", name="ck_ticket_categories_price_nonnegative"),
        sa.CheckConstraint("total_quantity > 0", name="ck_ticket_categories_total_positive"),
        sa.CheckConstraint("sold_quantity >= 0", name="ck_ticket_categories_sold_nonnegative"),
        sa.CheckConstraint("reserved_quantity >= 0", name="ck_ticket_categories_reserved_nonnegative"),
        sa.CheckConstraint("sold_quantity + reserved_quantity <= total_quantity", name="ck_ticket_categories_inventory_bounds"),
        sa.CheckConstraint("min_per_order > 0", name="ck_ticket_categories_min_order_positive"),
        sa.CheckConstraint("max_per_order >= min_per_order", name="ck_ticket_categories_order_bounds"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'sold_out')", name="ck_ticket_categories_status_valid"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "name", name="uq_ticket_categories_event_name"),
    )
    op.create_index("ix_ticket_categories_event_status", "ticket_categories", ["event_id", "status"])
    op.create_index("ix_ticket_categories_sales_window", "ticket_categories", ["sales_start_at", "sales_end_at"])


def downgrade() -> None:
    op.drop_index("ix_ticket_categories_sales_window", table_name="ticket_categories")
    op.drop_index("ix_ticket_categories_event_status", table_name="ticket_categories")
    op.drop_table("ticket_categories")
