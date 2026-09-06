"""corregir generar_codigo_prestamo (bug 0100)

Revision ID: c2b9d5e7a1f4
Revises: f3a6c1e8d4b2
Create Date: 2026-09-06 00:00:00.000000

La version original tomaba la parte numerica con SUBSTRING(... FROM 10), que
solo leia los dos ultimos digitos: para 'P-2026-0100' devolvia '00', el MAX se
quedaba en 99 y la funcion regeneraba un codigo ya existente (violacion de la
restriccion unica de codigo_prestamo al registrar el siguiente prestamo).

Ademas serializa la generacion con un advisory lock TRANSACCIONAL: sin el, dos
transacciones simultaneas podian leer el mismo MAX y proponer el mismo codigo.

Esta migracion aplica la version corregida sobre bases ya creadas. Las
instalaciones nuevas la reciben desde database/setup.sql, que tiene la misma
definicion. Solo reemplaza la funcion: no toca tablas, datos ni codigos ya
generados.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'c2b9d5e7a1f4'
down_revision = 'f3a6c1e8d4b2'
branch_labels = None
depends_on = None


FUNCION_CORREGIDA = """
CREATE OR REPLACE FUNCTION generar_codigo_prestamo()
RETURNS VARCHAR AS $$
DECLARE
    v_anio VARCHAR(4);
    v_siguiente INTEGER;
    v_codigo VARCHAR(20);
BEGIN
    v_anio := EXTRACT(YEAR FROM CURRENT_DATE)::VARCHAR;

    -- Lock TRANSACCIONAL (se libera solo en COMMIT/ROLLBACK) para que dos
    -- transacciones simultaneas no lean el mismo MAX. La clave se deriva del
    -- nombre de la funcion y del anio, no es un numero arbitrario.
    PERFORM pg_advisory_xact_lock(hashtext('generar_codigo_prestamo'), v_anio::INTEGER);

    SELECT COALESCE(MAX(CAST(SUBSTRING(codigo_prestamo FROM LENGTH('P-' || v_anio || '-') + 1) AS INTEGER)), 0) + 1
    INTO v_siguiente
    FROM prestamos
    WHERE codigo_prestamo LIKE 'P-' || v_anio || '-%'
      AND codigo_prestamo ~ ('^P-' || v_anio || '-[0-9]+$');

    v_codigo := 'P-' || v_anio || '-' || LPAD(v_siguiente::TEXT, 4, '0');

    RETURN v_codigo;
END;
$$ LANGUAGE plpgsql;
"""

# Version anterior, con el bug. Solo se usa en downgrade() para que la
# migracion sea reversible; no conviene volver a ella.
FUNCION_ORIGINAL = """
CREATE OR REPLACE FUNCTION generar_codigo_prestamo()
RETURNS VARCHAR AS $$
DECLARE
    v_anio VARCHAR(4);
    v_siguiente INTEGER;
    v_codigo VARCHAR(20);
BEGIN
    v_anio := EXTRACT(YEAR FROM CURRENT_DATE)::VARCHAR;

    SELECT COALESCE(MAX(CAST(SUBSTRING(codigo_prestamo FROM 10) AS INTEGER)), 0) + 1
    INTO v_siguiente
    FROM prestamos
    WHERE codigo_prestamo LIKE 'P-' || v_anio || '-%';

    v_codigo := 'P-' || v_anio || '-' || LPAD(v_siguiente::TEXT, 4, '0');

    RETURN v_codigo;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade():
    op.execute(FUNCION_CORREGIDA)


def downgrade():
    op.execute(FUNCION_ORIGINAL)
