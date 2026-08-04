"""articles: actores de encuadre como FK a canonical_entities

Revision ID: bedd70abc693
Revises: 88129941422b
Create Date: 2026-08-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bedd70abc693'
down_revision: Union[str, Sequence[str], None] = '88129941422b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # batch_alter_table: ver nota en 88129941422b sobre SQLite vs Postgres/SQL
    # Server. Las columnas string (`dominant_actor` etc.) se eliminan aquí: no
    # se conserva su contenido porque siempre fue derivable de `entities` para
    # ese mismo artículo (match_actor_name reapunta al nombre canonicalizado
    # de una entidad ya vinculada); las filas que no resuelvan a ninguna
    # CanonicalEntity simplemente quedan con la FK en NULL.
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dominant_actor_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('blamed_actor_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('credited_actor_id', sa.Integer(), nullable=True))
        batch_op.create_index(
            op.f('ix_articles_dominant_actor_id'), ['dominant_actor_id'], unique=False
        )
        batch_op.create_index(
            op.f('ix_articles_blamed_actor_id'), ['blamed_actor_id'], unique=False
        )
        batch_op.create_index(
            op.f('ix_articles_credited_actor_id'), ['credited_actor_id'], unique=False
        )
        batch_op.create_foreign_key(
            'fk_articles_dominant_actor_id', 'canonical_entities',
            ['dominant_actor_id'], ['id'], ondelete='SET NULL',
        )
        batch_op.create_foreign_key(
            'fk_articles_blamed_actor_id', 'canonical_entities',
            ['blamed_actor_id'], ['id'], ondelete='SET NULL',
        )
        batch_op.create_foreign_key(
            'fk_articles_credited_actor_id', 'canonical_entities',
            ['credited_actor_id'], ['id'], ondelete='SET NULL',
        )
        batch_op.drop_column('dominant_actor')
        batch_op.drop_column('blamed_actor')
        batch_op.drop_column('credited_actor')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dominant_actor', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('blamed_actor', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('credited_actor', sa.String(length=300), nullable=True))
        batch_op.drop_constraint('fk_articles_credited_actor_id', type_='foreignkey')
        batch_op.drop_constraint('fk_articles_blamed_actor_id', type_='foreignkey')
        batch_op.drop_constraint('fk_articles_dominant_actor_id', type_='foreignkey')
        batch_op.drop_index(op.f('ix_articles_credited_actor_id'))
        batch_op.drop_index(op.f('ix_articles_blamed_actor_id'))
        batch_op.drop_index(op.f('ix_articles_dominant_actor_id'))
        batch_op.drop_column('credited_actor_id')
        batch_op.drop_column('blamed_actor_id')
        batch_op.drop_column('dominant_actor_id')
