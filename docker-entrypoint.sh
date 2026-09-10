#!/bin/bash
# Entrypoint del contenedor biblio-app.
#
# Deja la base lista sola en cada arranque (todo idempotente, seguro
# re-ejecutar sobre una base con datos):
#   1. espera a PostgreSQL (pg_isready en bucle, sin dependencias externas)
#   2. flask db upgrade          (tablas Alembic; no hace nada si ya estan)
#   3. database/setup.sql        (triggers/vistas/funciones, todo OR REPLACE)
#   4. database/seed.py          (usuarios/config demo; omite lo existente)
set -e

echo "[entrypoint] esperando a PostgreSQL en ${PGHOST:-postgres}:${PGPORT:-5432}..."
for i in $(seq 1 30); do
  if pg_isready -h "${PGHOST:-postgres}" -p "${PGPORT:-5432}" -U "${PGUSER:-biblio}" -q; then
    echo "[entrypoint] PostgreSQL disponible."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "[entrypoint] ERROR: PostgreSQL no responde tras 30 intentos." >&2
    exit 1
  fi
  sleep 2
done

echo "[entrypoint] aplicando migraciones..."
flask --app run.py db upgrade

echo "[entrypoint] aplicando database/setup.sql..."
psql "host=${PGHOST:-postgres} port=${PGPORT:-5432} user=${PGUSER:-biblio} dbname=${PGDATABASE:-biblioteca_vv} password=${PGPASSWORD:-biblio123}" \
  -v ON_ERROR_STOP=1 -f database/setup.sql

echo "[entrypoint] aplicando database/seed.py..."
# -m y no ruta directa: asi /code queda en sys.path y "from app import ..."
# funciona (con "python database/seed.py" solo entraria database/).
python -m database.seed

echo "[entrypoint] arrancando: $*"
exec "$@"
