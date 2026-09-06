"""
Inicializacion de la base de datos en Azure (una sola vez por entorno).

Uso:
    python -m scripts.init_azure_db

Requiere que DATABASE_URL (variable de entorno / App Setting de Azure)
apunte ya a la base de datos PostgreSQL Flexible Server creada para este
despliegue. Ver DEPLOY_AZURE.md para los pasos completos.

Es seguro volver a ejecutarlo: ningun paso borra tablas ni filas
existentes, solo crea lo que falte.

Pasos, en orden (cada uno depende de que el anterior haya terminado):
1. Migraciones de Alembic (flask_migrate.upgrade) -> crea/actualiza tablas
   a partir de los modelos de SQLAlchemy.
2. database/setup.sql -> indices, funciones, triggers y vistas. Se omite
   automaticamente si ya fue aplicado antes (se detecta buscando una de
   sus vistas), porque el script en si no es idempotente (CREATE INDEX y
   CREATE TRIGGER fallarian si se repiten).
3. database/seed.py -> datos base (usuarios, categorias, facultades,
   etc.). Ya es idempotente por si mismo: solo inserta lo que no exista.
"""
import sys
from pathlib import Path
from urllib.parse import urlsplit

from flask_migrate import upgrade
from sqlalchemy import text

from app import create_app
from app.extensions import db

RUTA_SETUP_SQL = Path(__file__).resolve().parent.parent / 'database' / 'setup.sql'


def _describir_conexion(url):
    """Host/base de datos, sin usuario ni contraseña, solo para confirmar el destino."""
    if not url:
        return '(DATABASE_URL no configurada)'
    partes = urlsplit(url)
    return f'{partes.scheme}://{partes.hostname}{partes.path}'


def _setup_sql_ya_aplicado():
    resultado = db.session.execute(
        text("SELECT to_regclass('public.vista_prestamos_activos')")
    ).scalar()
    return resultado is not None


def _aplicar_migraciones():
    print('[1/3] Aplicando migraciones (flask db upgrade)...')
    upgrade()
    print('[1/3] Migraciones aplicadas.')


def _aplicar_setup_sql():
    if _setup_sql_ya_aplicado():
        print('[2/3] setup.sql ya estaba aplicado (existe vista_prestamos_activos). Se omite.')
        return

    print('[2/3] Aplicando database/setup.sql...')
    contenido = RUTA_SETUP_SQL.read_text(encoding='utf-8')
    with db.engine.begin() as conexion:
        conexion.execute(text(contenido))
    print('[2/3] setup.sql aplicado.')


def _aplicar_seed():
    print('[3/3] Cargando datos base (database/seed.py)...')
    from database.seed import run_seed
    run_seed()
    print('[3/3] Datos base cargados.')


def main():
    app = create_app()

    with app.app_context():
        destino = _describir_conexion(app.config.get('SQLALCHEMY_DATABASE_URI'))
        print(f'Inicializando base de datos en: {destino}\n')

        try:
            _aplicar_migraciones()
            _aplicar_setup_sql()
            _aplicar_seed()
        except Exception as error:
            print(f'\nERROR durante la inicializacion: {error}', file=sys.stderr)
            raise

    print('\nInicializacion completada.')


if __name__ == '__main__':
    main()
