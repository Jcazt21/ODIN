"""crawl_runs: tabla de resumen por corrida del pipeline

Revision ID: 16b256a1a0ab
Revises: 682d9f215468
Create Date: 2026-08-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '16b256a1a0ab'
down_revision: Union[str, Sequence[str], None] = '682d9f215468'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'crawl_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('correlation_id', sa.String(length=32), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('sources', sa.String(length=300), nullable=True),
        sa.Column('analyzer_name', sa.String(length=40), nullable=True),
        sa.Column('articles_discovered', sa.Integer(), nullable=False),
        sa.Column('articles_saved', sa.Integer(), nullable=False),
        sa.Column('articles_failed', sa.Integer(), nullable=False),
        sa.Column('stats_by_source', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_crawl_runs_correlation_id'), 'crawl_runs', ['correlation_id'], unique=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_crawl_runs_correlation_id'), table_name='crawl_runs')
    op.drop_table('crawl_runs')
