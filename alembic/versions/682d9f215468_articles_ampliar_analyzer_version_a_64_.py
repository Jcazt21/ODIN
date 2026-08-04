"""articles: ampliar analyzer_version a 64 chars

Revision ID: 682d9f215468
Revises: 73ed4b404bce
Create Date: 2026-08-04 12:27:28.749478

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '682d9f215468'
down_revision: Union[str, Sequence[str], None] = '73ed4b404bce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # HybridAnalyzer.version combina local+groq+combine (p.ej.
    # "local2+groq3+combine2", 22 chars) y ya excede los 20 originales,
    # causando StringDataRightTruncation en Postgres al persistir.
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.alter_column(
            'analyzer_version',
            existing_type=sa.String(length=20),
            type_=sa.String(length=64),
            existing_nullable=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.alter_column(
            'analyzer_version',
            existing_type=sa.String(length=64),
            type_=sa.String(length=20),
            existing_nullable=True,
        )
