"""agregar debe_cambiar_password a usuarios

Revision ID: 7c1e9a2b4d3f
Revises: 191a3f1281e2
Create Date: 2026-07-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c1e9a2b4d3f'
down_revision = '191a3f1281e2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'usuarios',
        sa.Column('debe_cambiar_password', sa.Boolean(), server_default=sa.text('false'), nullable=False)
    )


def downgrade():
    op.drop_column('usuarios', 'debe_cambiar_password')
