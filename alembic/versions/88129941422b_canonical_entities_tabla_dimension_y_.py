"""canonical_entities: tabla dimension y vinculo desde entities

Revision ID: 88129941422b
Revises: 716c8e4a7513
Create Date: 2026-08-03 09:24:13.414169

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '88129941422b'
down_revision: Union[str, Sequence[str], None] = '716c8e4a7513'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'canonical_entities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=300), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('description', sa.String(length=300), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', 'type', name='uq_canonical_entity_name_type'),
    )
    op.create_index(op.f('ix_canonical_entities_name'), 'canonical_entities', ['name'], unique=False)

    # batch_alter_table: SQLite no soporta ALTER TABLE ADD CONSTRAINT directo
    # (hace falta la estrategia de copiar-y-mover); en Postgres/SQL Server,
    # los otros dos motores objetivo del proyecto, batch mode emite el mismo
    # ALTER TABLE nativo sin cambios de comportamiento.
    with op.batch_alter_table('entities', schema=None) as batch_op:
        # server_default en el ADD COLUMN (no solo el default de Python en el
        # modelo): las filas de `entities` que ya existan antes de esta
        # migración necesitan un valor para poder aplicar NOT NULL sin romper.
        batch_op.add_column(
            sa.Column('extraction_confidence', sa.Float(), nullable=False, server_default='1')
        )
        batch_op.add_column(sa.Column('canonical_entity_id', sa.Integer(), nullable=True))
        batch_op.create_index(
            op.f('ix_entities_canonical_entity_id'), ['canonical_entity_id'], unique=False
        )
        batch_op.create_foreign_key(
            'fk_entities_canonical_entity_id', 'canonical_entities',
            ['canonical_entity_id'], ['id'], ondelete='SET NULL',
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('entities', schema=None) as batch_op:
        batch_op.drop_constraint('fk_entities_canonical_entity_id', type_='foreignkey')
        batch_op.drop_index(op.f('ix_entities_canonical_entity_id'))
        batch_op.drop_column('canonical_entity_id')
        batch_op.drop_column('extraction_confidence')

    op.drop_index(op.f('ix_canonical_entities_name'), table_name='canonical_entities')
    op.drop_table('canonical_entities')
