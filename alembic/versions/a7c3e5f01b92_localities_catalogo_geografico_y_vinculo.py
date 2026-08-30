"""localities: catalogo geografico jerarquico y vinculo con articles

Crea las tres tablas del lugar de la noticia:

  localities         -> el arbol (pais / macrorregion / region / provincia /
                        municipio) en UNA tabla autorreferencial.
  locality_aliases   -> otros nombres por los que la prensa cita un lugar
                        ("Salcedo" por Hermanas Mirabal, "Navarrete" por
                        Villa Bisono).
  article_localities -> vinculo N:M articulo <-> lugar, con el papel que juega
                        el lugar en la nota (HECHO / MENCIONADO).

Esta migracion NO carga el catalogo: solo crea el esquema. El contenido lo
siembra `db.localities.seed_localities()` en el arranque de la API, igual que
`db.aliases.load_seed()` hace con las siglas. La razon es que el catalogo
cambia por ley (Baitoa 2013, La Victoria y La Caleta 2024) y debe poder
actualizarse editando la semilla o desde la UI, sin escribir una migracion
nueva por cada municipio que crea el Congreso.

Revision ID: a7c3e5f01b92
Revises: 8d168b50bcf7
Create Date: 2026-08-22 10:24:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c3e5f01b92'
down_revision: Union[str, Sequence[str], None] = '8d168b50bcf7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'localities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('norm_key', sa.String(length=160), nullable=False),
        sa.Column('level', sa.String(length=20), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('path', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['parent_id'], ['localities.id'], ondelete='CASCADE'),
        # Dos hermanos no pueden llamarse igual, pero el mismo nombre SI puede
        # repetirse bajo padres distintos: "Santiago" es provincia del Cibao y
        # tambien municipio dentro de esa provincia.
        sa.UniqueConstraint('parent_id', 'norm_key', name='uq_locality_sibling_name'),
    )
    op.create_index(op.f('ix_localities_name'), 'localities', ['name'], unique=False)
    op.create_index(op.f('ix_localities_norm_key'), 'localities', ['norm_key'], unique=False)
    op.create_index(op.f('ix_localities_parent_id'), 'localities', ['parent_id'], unique=False)
    # El indice que sostiene el filtro por subarbol (LIKE '/1/2/%'), que es la
    # consulta caliente: "todas las noticias del Cibao".
    op.create_index('ix_localities_path', 'localities', ['path'], unique=False)
    op.create_index('ix_localities_level', 'localities', ['level'], unique=False)

    op.create_table(
        'locality_aliases',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('locality_id', sa.Integer(), nullable=False),
        sa.Column('alias', sa.String(length=160), nullable=False),
        sa.Column('alias_key', sa.String(length=160), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['locality_id'], ['localities.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('locality_id', 'alias_key', name='uq_locality_alias'),
    )
    op.create_index(
        op.f('ix_locality_aliases_locality_id'), 'locality_aliases', ['locality_id'], unique=False
    )
    op.create_index(
        op.f('ix_locality_aliases_alias_key'), 'locality_aliases', ['alias_key'], unique=False
    )

    op.create_table(
        'article_localities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('article_id', sa.Integer(), nullable=False),
        sa.Column('locality_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False, server_default='HECHO'),
        sa.Column('origin', sa.String(length=20), nullable=False, server_default='MANUAL'),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['locality_id'], ['localities.id'], ondelete='CASCADE'),
        # El mismo lugar puede estar dos veces en una nota si juega dos papeles
        # distintos (ocurre en Santiago y ademas se menciona a Santiago), pero
        # no dos veces con el mismo papel.
        sa.UniqueConstraint('article_id', 'locality_id', 'kind', name='uq_article_locality'),
    )
    op.create_index(
        op.f('ix_article_localities_article_id'), 'article_localities', ['article_id'], unique=False
    )
    op.create_index(
        op.f('ix_article_localities_locality_id'),
        'article_localities',
        ['locality_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_article_localities_locality_id'), table_name='article_localities')
    op.drop_index(op.f('ix_article_localities_article_id'), table_name='article_localities')
    op.drop_table('article_localities')

    op.drop_index(op.f('ix_locality_aliases_alias_key'), table_name='locality_aliases')
    op.drop_index(op.f('ix_locality_aliases_locality_id'), table_name='locality_aliases')
    op.drop_table('locality_aliases')

    op.drop_index('ix_localities_level', table_name='localities')
    op.drop_index('ix_localities_path', table_name='localities')
    op.drop_index(op.f('ix_localities_parent_id'), table_name='localities')
    op.drop_index(op.f('ix_localities_norm_key'), table_name='localities')
    op.drop_index(op.f('ix_localities_name'), table_name='localities')
    op.drop_table('localities')
