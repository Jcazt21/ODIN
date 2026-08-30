"""articles: documentalista y fecha de analisis

Autoria humana, distinta del linaje del analisis (`analyzer_name`, que dice que
MODELO lo produjo). Nulo en lo ya guardado y en lo que entra por el rastreo
masivo: no hay forma de reconstruir retroactivamente quien reviso que.

Revision ID: c9e8b3d5107f
Revises: b2d41f7a9c03
Create Date: 2026-08-22 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9e8b3d5107f'
down_revision: Union[str, Sequence[str], None] = 'b2d41f7a9c03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # batch_alter_table: SQLite no soporta ALTER TABLE ADD CONSTRAINT directo;
    # en Postgres y SQL Server emite el mismo ALTER nativo sin cambios.
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('documentalist_id', sa.Integer(), nullable=True))
        # Date y no DateTime: el requisito es dia/mes/anio sin hora.
        batch_op.add_column(sa.Column('analyzed_on', sa.Date(), nullable=True))
        batch_op.create_index(
            batch_op.f('ix_articles_documentalist_id'), ['documentalist_id'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_articles_analyzed_on'), ['analyzed_on'], unique=False
        )
        batch_op.create_foreign_key(
            'fk_articles_documentalist_id_users', 'users', ['documentalist_id'], ['id'], ondelete='SET NULL'
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.drop_constraint('fk_articles_documentalist_id_users', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_articles_analyzed_on'))
        batch_op.drop_index(batch_op.f('ix_articles_documentalist_id'))
        batch_op.drop_column('analyzed_on')
        batch_op.drop_column('documentalist_id')
