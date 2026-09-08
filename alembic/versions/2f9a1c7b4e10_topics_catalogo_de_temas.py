"""topics: catalogo administrable de temas y vinculo con articles

Crea las tres tablas del tema de la noticia, calcadas del triangulo geografico
(`localities` / `locality_aliases` / `article_localities`):

  topics         -> el catalogo (tema / subtema) en UNA tabla autorreferencial,
                    con `path` materializado para consultar el subarbol por
                    prefijo (LIKE '/1/%'), sin CTE recursivo.
  topic_aliases  -> otros terminos por los que la prensa nombra un tema
                    ("acueducto", "suministro de agua" -> Agua).
  article_topics -> vinculo N:M articulo <-> tema, con `origin` (AUTO lo propuso
                    el clasificador por reglas, MANUAL lo puso un documentalista),
                    `score` (confianza del match automatico) y `evidence` (el
                    termino que disparo el match).

Esta migracion NO carga el catalogo: solo crea el esquema. El contenido lo
siembra `db.topics.load_seed()` en el arranque de la API, igual que
`db.localities` y `db.aliases`. La razon es la misma: el catalogo lo entrega y
lo administra el cliente desde la UI, no debe requerir una migracion nueva por
cada tema que se agregue o se de de baja.

Revision ID: 2f9a1c7b4e10
Revises: e5b2c81d3f47
Create Date: 2026-09-08 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f9a1c7b4e10'
down_revision: Union[str, Sequence[str], None] = 'e5b2c81d3f47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'topics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('norm_key', sa.String(length=160), nullable=False),
        sa.Column('slug', sa.String(length=160), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('path', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['parent_id'], ['topics.id'], ondelete='CASCADE'),
        # Dos hermanos no pueden llamarse igual, pero el mismo nombre SI puede
        # repetirse bajo padres distintos (un subtema "Infraestructura" bajo
        # Agua y otro bajo Transporte).
        sa.UniqueConstraint('parent_id', 'norm_key', name='uq_topic_sibling_name'),
    )
    op.create_index(op.f('ix_topics_name'), 'topics', ['name'], unique=False)
    op.create_index(op.f('ix_topics_norm_key'), 'topics', ['norm_key'], unique=False)
    op.create_index(op.f('ix_topics_parent_id'), 'topics', ['parent_id'], unique=False)
    # El indice que sostiene el filtro por subarbol (LIKE '/1/%'), la consulta
    # caliente: "todas las noticias del tema Agua y sus subtemas".
    op.create_index('ix_topics_path', 'topics', ['path'], unique=False)

    op.create_table(
        'topic_aliases',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.Column('alias', sa.String(length=160), nullable=False),
        sa.Column('alias_key', sa.String(length=160), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('topic_id', 'alias_key', name='uq_topic_alias'),
    )
    op.create_index(
        op.f('ix_topic_aliases_topic_id'), 'topic_aliases', ['topic_id'], unique=False
    )
    op.create_index(
        op.f('ix_topic_aliases_alias_key'), 'topic_aliases', ['alias_key'], unique=False
    )

    op.create_table(
        'article_topics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('article_id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('origin', sa.String(length=20), nullable=False, server_default='AUTO'),
        sa.Column('evidence', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        # Un tema no puede estar dos veces en la misma nota. Si el clasificador
        # (AUTO) ya lo puso y luego un documentalista lo confirma, el vinculo se
        # actualiza in situ, no se duplica.
        sa.UniqueConstraint('article_id', 'topic_id', name='uq_article_topic'),
    )
    op.create_index(
        op.f('ix_article_topics_article_id'), 'article_topics', ['article_id'], unique=False
    )
    op.create_index(
        op.f('ix_article_topics_topic_id'), 'article_topics', ['topic_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_article_topics_topic_id'), table_name='article_topics')
    op.drop_index(op.f('ix_article_topics_article_id'), table_name='article_topics')
    op.drop_table('article_topics')

    op.drop_index(op.f('ix_topic_aliases_alias_key'), table_name='topic_aliases')
    op.drop_index(op.f('ix_topic_aliases_topic_id'), table_name='topic_aliases')
    op.drop_table('topic_aliases')

    op.drop_index('ix_topics_path', table_name='topics')
    op.drop_index(op.f('ix_topics_parent_id'), table_name='topics')
    op.drop_index(op.f('ix_topics_norm_key'), table_name='topics')
    op.drop_index(op.f('ix_topics_name'), table_name='topics')
    op.drop_table('topics')
