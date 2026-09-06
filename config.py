import os


def _normalizar_url_postgres(url):
    """Azure/Heroku a veces entregan 'postgres://', pero SQLAlchemy 1.4+
    solo acepta 'postgresql://'. Sin esto, la app no arranca en produccion."""
    if url and url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql://', 1)
    return url


class Config:
    """Configuracion base compartida por todos los entornos."""

    SECRET_KEY = os.environ.get('SECRET_KEY', 'clave-temporal-desarrollo')
    SQLALCHEMY_DATABASE_URI = _normalizar_url_postgres(os.environ.get('DATABASE_URL'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Limite global de tamaño de peticion (protege contra subidas enormes,
    # incluida la portada de libros: ver app/portadas.py). 3 MB da margen
    # sobre el maximo de 2 MB de la imagen para el resto de campos del form.
    MAX_CONTENT_LENGTH = 3 * 1024 * 1024


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False
    # Sin fallback a DATABASE_URL a proposito: si TEST_DATABASE_URL no esta
    # configurada, preferimos que falle de forma explicita a que las pruebas
    # (que hacen create_all/drop_all) corran contra la base de desarrollo.
    SQLALCHEMY_DATABASE_URI = _normalizar_url_postgres(os.environ.get('TEST_DATABASE_URL'))


class ProductionConfig(Config):
    DEBUG = False


config_por_nombre = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
}
