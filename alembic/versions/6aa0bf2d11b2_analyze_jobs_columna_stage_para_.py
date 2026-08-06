"""analyze_jobs: columna stage para progreso del pipeline

Revision ID: 6aa0bf2d11b2
Revises: a3f1c9d24e70
Create Date: 2026-08-06 10:17:44.880337

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6aa0bf2d11b2'
down_revision: Union[str, Sequence[str], None] = 'a3f1c9d24e70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('analyze_jobs', sa.Column('stage', sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('analyze_jobs', 'stage')
