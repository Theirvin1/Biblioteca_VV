from flask import Flask, redirect, url_for
from app.extensions import db, migrate, login_manager, csrf
from app.controllers.auth import auth_bp
from app.controllers.bibliotecario import bibliotecario_bp
from app.controllers.estudiante import estudiante_bp
from app.controllers.gerente import gerente_bp
from app.portadas import url_portada
from app.validators import limites_anio_publicacion, limites_fecha_nacimiento
from dotenv import load_dotenv
import os

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(basedir, '.env'))

# config.py lee SECRET_KEY/DATABASE_URL al importarse, por eso debe
# importarse después de cargar el .env y no junto con los demás imports.
from config import config_por_nombre  # noqa: E402


def create_app(config_name=None):
    config_name = config_name or os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config_por_nombre[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Debes iniciar sesión para acceder a esta página.'
    login_manager.login_message_category = 'warning'
    csrf.init_app(app)

    app.jinja_env.globals['url_portada'] = url_portada
    # Se registran como funciones (no como valores) a proposito: los limites
    # dependen de la fecha actual y se recalculan en cada render, en vez de
    # congelarse al arrancar la app.
    app.jinja_env.globals['limites_anio_publicacion'] = limites_anio_publicacion
    app.jinja_env.globals['limites_fecha_nacimiento'] = limites_fecha_nacimiento

    with app.app_context():
        from app import models  # noqa: F401

    app.register_blueprint(auth_bp)
    app.register_blueprint(bibliotecario_bp)
    app.register_blueprint(estudiante_bp)
    app.register_blueprint(gerente_bp)

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    return app