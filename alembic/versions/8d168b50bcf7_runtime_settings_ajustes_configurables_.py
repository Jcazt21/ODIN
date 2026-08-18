"""runtime settings: ajustes configurables sin variables de entorno

Revision ID: 8d168b50bcf7
Revises: c4d7b91f0a35
Create Date: 2026-08-17 10:15:34.267621

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d168b50bcf7'
down_revision: Union[str, Sequence[str], None] = 'c4d7b91f0a35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "runtime_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analyzer_mode", sa.String(length=20), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("runtime_settings")
