"""analyze_jobs: índices para reuso por URL y barrido de jobs colgados

Revision ID: c4d7b91f0a35
Revises: 6aa0bf2d11b2
Create Date: 2026-08-07 18:05:12.418733

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c4d7b91f0a35'
down_revision: Union[str, Sequence[str], None] = '6aa0bf2d11b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        'ix_analyze_jobs_url_created_at', 'analyze_jobs', ['url', 'created_at']
    )
    op.create_index(
        'ix_analyze_jobs_status_created_at', 'analyze_jobs', ['status', 'created_at']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_analyze_jobs_status_created_at', table_name='analyze_jobs')
    op.drop_index('ix_analyze_jobs_url_created_at', table_name='analyze_jobs')
