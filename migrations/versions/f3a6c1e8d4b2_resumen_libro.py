"""agregar resumen a libros

Revision ID: f3a6c1e8d4b2
Revises: d7e4c2a9b1f6
Create Date: 2026-09-05 00:00:00.000000

Resumen/sinopsis opcional del libro. Text (no VARCHAR) para admitir textos
largos. Nullable: los libros existentes quedan en NULL y siguen funcionando
igual (las plantillas ya muestran "No hay un resumen disponible..." en ese caso).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3a6c1e8d4b2'
down_revision = 'd7e4c2a9b1f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'libros',
        sa.Column('resumen', sa.Text(), nullable=True)
    )


def downgrade():
    op.drop_column('libros', 'resumen')
