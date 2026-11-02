"""analyze_jobs: columna steps_json para el timeline de progreso

Revision ID: 7b3e5d2a9c64
Revises: 2f9a1c7b4e10
Create Date: 2026-11-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b3e5d2a9c64'
down_revision: Union[str, Sequence[str], None] = '2f9a1c7b4e10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('analyze_jobs') as batch_op:
        batch_op.add_column(sa.Column('steps_json', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('analyze_jobs') as batch_op:
        batch_op.drop_column('steps_json')
