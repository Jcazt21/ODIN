"""users: nombre y apellido separados

De ellos se deriva el `username` (inicial del nombre + 4 primeras del
apellido). Las filas existentes se rellenan partiendo `display_name` por el
PRIMER espacio: lo que queda a la derecha es el apellido, que es la convencion
con la que se cargaron.

Revision ID: e5b2c81d3f47
Revises: d41aae1f9a44

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5b2c81d3f47'
down_revision: Union[str, Sequence[str], None] = 'd41aae1f9a44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('first_name', sa.String(length=80), nullable=False, server_default='')
        )
        batch_op.add_column(
            sa.Column('last_name', sa.String(length=80), nullable=False, server_default='')
        )

    # Backfill: primer token del display_name al nombre, el resto al apellido.
    # Se usa SQL neutro (SUBSTR/INSTR no lo es) via la API de expresiones para
    # que corra igual en SQLite y en Postgres.
    users = sa.table(
        'users',
        sa.column('display_name', sa.String),
        sa.column('first_name', sa.String),
        sa.column('last_name', sa.String),
    )
    bind = op.get_bind()
    for display_name, in bind.execute(sa.select(users.c.display_name)).fetchall():
        first, _, rest = (display_name or '').strip().partition(' ')
        bind.execute(
            users.update()
            .where(users.c.display_name == display_name)
            .values(first_name=first, last_name=rest.strip())
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('last_name')
        batch_op.drop_column('first_name')
