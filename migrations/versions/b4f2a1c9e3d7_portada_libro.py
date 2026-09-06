"""agregar portada_archivo a libros

Revision ID: b4f2a1c9e3d7
Revises: 7c1e9a2b4d3f
Create Date: 2026-07-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4f2a1c9e3d7'
down_revision = '7c1e9a2b4d3f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'libros',
        sa.Column('portada_archivo', sa.String(length=255), nullable=True)
    )


def downgrade():
    op.drop_column('libros', 'portada_archivo')
