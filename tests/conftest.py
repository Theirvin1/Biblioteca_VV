"""
Fixtures compartidas para las pruebas del sistema de biblioteca.

Requisitos para correr esta suite:
- Una base de datos PostgreSQL de pruebas, SEPARADA de la de desarrollo,
  configurada en la variable de entorno TEST_DATABASE_URL (ver .env.example).
- Las pruebas usan TestingConfig (config.py), que apunta a esa base y
  desactiva CSRF para simplificar los POST de las pruebas.

Preparacion del esquema (una vez por sesion de pruebas)
--------------------------------------------------------
1. DROP SCHEMA public CASCADE / CREATE SCHEMA public sobre TEST_DATABASE_URL:
   arranca siempre desde una base realmente vacia, sin importar que haya
   quedado de una corrida anterior, de un intento manual con psql, o de una
   corrida interrumpida a la mitad. Esto es lo que hace que el proceso sea
   repetible: no dependemos de que cada sentencia de setup.sql sea idempotente
   (varias no lo son, p. ej. CREATE INDEX y CREATE TRIGGER sin OR REPLACE),
   simplemente no queda nada previo con lo que puedan chocar.
2. db.create_all(): crea las tablas a partir de los modelos de SQLAlchemy.
3. Se ejecuta database/setup.sql completo (indices, funciones, triggers y
   vistas) sobre esa misma base, ya con las tablas existiendo. Por eso las
   pruebas que dependen de funciones/vistas (marcadas con
   @pytest.mark.requiere_setup_sql, solo a modo de documentacion) tambien
   pasan corriendo `pytest` normal, sin pasos manuales.

Limpieza entre pruebas
----------------------
Las fixtures de datos (usuario_bibliotecario, usuario_estudiante, etc.) solo
crean y devuelven objetos: no borran nada ellas mismas. Borrar un Usuario a
mano es fragil porque login() ya crea filas en `sesiones` que apuntan a el
(usuario_id es NOT NULL), y ese no es el unico caso en el modelo.

En vez de eso, la fixture autouse `limpiar_base_de_datos` corre despues de
CADA prueba (haya pasado o fallado) y hace TRUNCATE ... RESTART IDENTITY
CASCADE sobre todas las tablas, en una conexion nueva y separada de
`db.session`. Así cada prueba arranca con la base vacia y una sesion de
SQLAlchemy sana, sin importar como haya terminado la prueba anterior.
"""
import os
from pathlib import Path

import pytest
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db as _db
from app.models import Carrera, Estudiante, Facultad, Usuario

RUTA_SETUP_SQL = Path(__file__).resolve().parent.parent / 'database' / 'setup.sql'


def _reiniciar_esquema():
    """DROP/CREATE SCHEMA public: garantiza una base vacia sin importar el estado previo."""
    with _db.engine.begin() as conexion:
        conexion.execute(text('DROP SCHEMA public CASCADE'))
        conexion.execute(text('CREATE SCHEMA public'))


def _ejecutar_setup_sql():
    """Aplica database/setup.sql completo sobre TEST_DATABASE_URL (tablas ya creadas)."""
    contenido = RUTA_SETUP_SQL.read_text(encoding='utf-8')
    with _db.engine.begin() as conexion:
        conexion.execute(text(contenido))


@pytest.fixture(scope='session')
def _flask_app():
    """Crea la app y el esquema UNA sola vez para toda la sesion de pruebas."""
    test_db_url = os.environ.get('TEST_DATABASE_URL')
    dev_db_url = os.environ.get('DATABASE_URL')

    if not test_db_url:
        pytest.exit(
            'Falta configurar TEST_DATABASE_URL en tu archivo .env. '
            'Debe apuntar a una base de datos de pruebas, separada de la de desarrollo '
            '(ver .env.example).'
        )
    if test_db_url == dev_db_url:
        pytest.exit(
            'TEST_DATABASE_URL es igual a DATABASE_URL. Usa una base de datos distinta: '
            'esta suite ejecuta un DROP SCHEMA public CASCADE y borraria tu base de desarrollo.'
        )

    application = create_app('testing')

    with application.app_context():
        _reiniciar_esquema()
        _db.create_all()
        _ejecutar_setup_sql()

    yield application

    # No hace falta drop_all() aqui: la proxima sesion de pruebas vuelve a
    # reiniciar el esquema completo (_reiniciar_esquema) antes de usarlo.


@pytest.fixture
def app(_flask_app):
    """
    Empuja un app context NUEVO para cada prueba.

    Importante: flask.g (y con el, el cache de current_user de Flask-Login)
    vive en el app context. Si un solo app context se mantuviera abierto
    durante TODA la sesion de pytest, el usuario autenticado de una prueba
    quedaria "pegado" en flask.g para la siguiente prueba, y al estar su
    sesion de SQLAlchemy ya cerrada (removida), cualquier acceso a sus
    atributos revienta con DetachedInstanceError. Empujar un contexto propio
    por prueba evita esa fuga sin renunciar a crear el esquema una sola vez.
    """
    with _flask_app.app_context():
        yield _flask_app


@pytest.fixture
def db(app):
    """Acceso directo a la sesion de SQLAlchemy dentro de una prueba."""
    return _db


@pytest.fixture(autouse=True)
def limpiar_base_de_datos(db):
    """Vacia todas las tablas despues de cada prueba, sin importar el resultado."""
    yield

    # Si la prueba dejo la sesion en un estado invalido (p. ej. por un
    # IntegrityError sin manejar), la deshacemos y la cerramos antes de
    # truncar, para no dejarla dañada de cara a la siguiente prueba.
    db.session.rollback()
    db.session.remove()

    tablas = ', '.join(f'"{tabla.name}"' for tabla in _db.metadata.sorted_tables)
    with db.engine.begin() as conexion:
        conexion.execute(text(f'TRUNCATE TABLE {tablas} RESTART IDENTITY CASCADE'))


@pytest.fixture
def login(client):
    """Helper para autenticarse: login('usuario', 'password')."""
    def _login(username, password):
        return client.post(
            '/login',
            data={'username': username, 'password': password},
            follow_redirects=False,
        )
    return _login


@pytest.fixture
def carrera_prueba(db):
    facultad = Facultad(nombre='Facultad de Pruebas VV')
    db.session.add(facultad)
    db.session.flush()

    carrera = Carrera(nombre='Carrera de Pruebas VV', facultad_id=facultad.id)
    db.session.add(carrera)
    db.session.commit()

    return carrera


@pytest.fixture
def usuario_bibliotecario(db):
    usuario = Usuario(
        username='test_bibliotecario',
        password_hash=generate_password_hash('ClaveSegura123'),
        rol='bibliotecario',
    )
    db.session.add(usuario)
    db.session.commit()

    return usuario


@pytest.fixture
def usuario_gerente(db):
    usuario = Usuario(
        username='test_gerente',
        password_hash=generate_password_hash('ClaveSegura123'),
        rol='gerente',
    )
    db.session.add(usuario)
    db.session.commit()

    return usuario


@pytest.fixture
def usuario_estudiante(db, carrera_prueba):
    usuario = Usuario(
        username='1234567899',
        password_hash=generate_password_hash('ClaveSegura123'),
        rol='estudiante',
    )
    db.session.add(usuario)
    db.session.flush()

    estudiante = Estudiante(
        cedula='1234567899',
        nombres='Estudiante',
        apellidos='De Pruebas',
        correo='estudiante.pruebas@uteq.edu.ec',
        carrera_id=carrera_prueba.id,
        usuario_id=usuario.id,
    )
    db.session.add(estudiante)
    db.session.commit()

    return usuario
