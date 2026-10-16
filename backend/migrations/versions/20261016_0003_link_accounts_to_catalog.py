"""Link organizer profiles and venues to user accounts.

Revision ID: 20261016_0003
Revises: 20261016_0002
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261016_0003"
down_revision: Union[str, None] = "20261016_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizers", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_unique_constraint("uq_organizers_user_id", "organizers", ["user_id"])
    op.create_foreign_key("fk_organizers_user_id_users", "organizers", "users", ["user_id"], ["id"], ondelete="SET NULL")
    op.add_column("venues", sa.Column("owner_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_venues_owner_user_id_users", "venues", "users", ["owner_user_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_venues_owner_user_id_users", "venues", type_="foreignkey")
    op.drop_column("venues", "owner_user_id")
    op.drop_constraint("fk_organizers_user_id_users", "organizers", type_="foreignkey")
    op.drop_constraint("uq_organizers_user_id", "organizers", type_="unique")
    op.drop_column("organizers", "user_id")
