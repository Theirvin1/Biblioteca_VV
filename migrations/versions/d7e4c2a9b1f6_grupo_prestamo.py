"""agregar grupo_prestamo a prestamos

Revision ID: d7e4c2a9b1f6
Revises: b4f2a1c9e3d7
Create Date: 2026-09-05 00:00:00.000000

Agrupa los prestamos registrados en una misma operacion (varios libros a un
mismo estudiante en un solo registro) bajo un codigo compartido tipo
'GRP-2026-0001'. Es NULLABLE a proposito: los prestamos ya existentes se
quedan en NULL y se siguen tratando como operaciones de un solo libro.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd7e4c2a9b1f6'
down_revision = 'b4f2a1c9e3d7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'prestamos',
        sa.Column('grupo_prestamo', sa.String(length=20), nullable=True)
    )
    op.create_index('idx_prestamos_grupo', 'prestamos', ['grupo_prestamo'])


def downgrade():
    op.drop_index('idx_prestamos_grupo', table_name='prestamos')
    op.drop_column('prestamos', 'grupo_prestamo')
