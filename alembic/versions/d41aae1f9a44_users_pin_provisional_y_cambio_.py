"""users: PIN provisional y cambio obligatorio

El alta de usuarios pasa a generar un PIN de 4 digitos en vez de recibir una
contrasena elegida por el admin. `must_change_password` obliga a cambiarlo al
entrar; `temp_password_used_at` sella cuando se consumio, y con eso el PIN vale
UNA sola vez.

Revision ID: d41aae1f9a44
Revises: c9e8b3d5107f

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd41aae1f9a44'
down_revision: Union[str, Sequence[str], None] = 'c9e8b3d5107f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # batch_alter_table por SQLite, igual que el resto de migraciones del
    # proyecto; en Postgres emite el ALTER nativo sin cambios.
    with op.batch_alter_table('users', schema=None) as batch_op:
        # server_default: las filas que ya existen no deben quedar con NULL ni
        # exigirle un cambio de contrasena a quien ya tiene la suya.
        batch_op.add_column(
            sa.Column(
                'must_change_password',
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column('temp_password_used_at', sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('temp_password_used_at')
        batch_op.drop_column('must_change_password')
