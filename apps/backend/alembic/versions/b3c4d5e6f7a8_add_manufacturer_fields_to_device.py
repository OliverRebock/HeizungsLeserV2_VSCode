"""Add manufacturer and heat pump type to device

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-04-17 11:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b3c4d5e6f7a8"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("device", sa.Column("manufacturer", sa.String(length=120), nullable=True))
    op.add_column("device", sa.Column("heat_pump_type", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("device", "heat_pump_type")
    op.drop_column("device", "manufacturer")
