"""articles: linaje del analisis (analyzer_name/model/version, analyzed_at, schema_version)

Revision ID: 73ed4b404bce
Revises: bedd70abc693
Create Date: 2026-08-03 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '73ed4b404bce'
down_revision: Union[str, Sequence[str], None] = 'bedd70abc693'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # batch_alter_table: ver nota en 88129941422b sobre SQLite vs Postgres/SQL
    # Server. Todas nullable: las filas ya existentes no tienen forma de
    # reconstruir retroactivamente qué analizador las produjo.
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('analyzer_name', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('analyzer_model', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('analyzer_version', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('analysis_schema_version', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('analyzed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.drop_column('analyzed_at')
        batch_op.drop_column('analysis_schema_version')
        batch_op.drop_column('analyzer_version')
        batch_op.drop_column('analyzer_model')
        batch_op.drop_column('analyzer_name')
