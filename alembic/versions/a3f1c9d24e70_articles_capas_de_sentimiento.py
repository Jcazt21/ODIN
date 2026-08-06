"""articles: capas de sentimiento (hechos/discurso citado/voz del medio) + flags de contenido

Revision ID: a3f1c9d24e70
Revises: 0436fbef10e9
Create Date: 2026-08-05 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f1c9d24e70'
down_revision: Union[str, Sequence[str], None] = '0436fbef10e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # batch_alter_table: ver nota en 88129941422b sobre SQLite vs Postgres/SQL
    # Server. Todas nullable: las filas ya analizadas no tienen estas capas y
    # no hay forma de reconstruirlas sin re-analizar el artículo (y con
    # LocalAnalyzer quedan NULL para siempre — no las produce).
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sentiment_basis', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('facts_sentiment', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('quoted_sentiment', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('media_stance', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('media_stance_evidence', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('overall_sentiment_reason', sa.String(length=800), nullable=True))
        batch_op.add_column(sa.Column('content_flags', sa.String(length=200), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.drop_column('content_flags')
        batch_op.drop_column('overall_sentiment_reason')
        batch_op.drop_column('media_stance_evidence')
        batch_op.drop_column('media_stance')
        batch_op.drop_column('quoted_sentiment')
        batch_op.drop_column('facts_sentiment')
        batch_op.drop_column('sentiment_basis')
