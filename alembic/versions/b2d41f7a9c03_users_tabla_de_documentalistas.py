"""users: tabla de documentalistas

Sustituye al operador unico contra credenciales del entorno. El operador
existente no se pierde: `db/users.seed_operator()` lo inserta como primer
usuario admin en el arranque de la API.

Revision ID: b2d41f7a9c03
Revises: a7c3e5f01b92
Create Date: 2026-08-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2d41f7a9c03'
down_revision: Union[str, Sequence[str], None] = 'a7c3e5f01b92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('username_key', sa.String(length=80), nullable=False),
        sa.Column('display_name', sa.String(length=160), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='documentalista'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username_key', name='uq_user_username'),
    )
    op.create_index(op.f('ix_users_username_key'), 'users', ['username_key'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_users_username_key'), table_name='users')
    op.drop_table('users')
