"""
Pruebas de control de acceso por rol.

Cada rol debe poder entrar unicamente a las rutas de su propio modulo.
Como @requiere_rol redirige ANTES de ejecutar la vista protegida, estas
pruebas no dependen de database/setup.sql: nunca llegan a tocar consultas
ni funciones SQL del modulo al que se les niega el acceso.
"""

RUTA_BIBLIOTECARIO = '/bibliotecario/inicio'
RUTA_ESTUDIANTE = '/estudiante/catalogo'
RUTA_GERENTE = '/gerente/dashboard'


def test_bibliotecario_no_accede_a_estudiante(client, login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')

    respuesta = client.get(RUTA_ESTUDIANTE)

    assert respuesta.status_code == 302
    assert respuesta.headers['Location'] == RUTA_BIBLIOTECARIO


def test_bibliotecario_no_accede_a_gerente(client, login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')

    respuesta = client.get(RUTA_GERENTE)

    assert respuesta.status_code == 302
    assert respuesta.headers['Location'] == RUTA_BIBLIOTECARIO


def test_estudiante_no_accede_a_bibliotecario(client, login, usuario_estudiante):
    login('1234567899', 'ClaveSegura123')

    respuesta = client.get(RUTA_BIBLIOTECARIO)

    assert respuesta.status_code == 302
    assert respuesta.headers['Location'] == RUTA_ESTUDIANTE


def test_estudiante_no_accede_a_gerente(client, login, usuario_estudiante):
    login('1234567899', 'ClaveSegura123')

    respuesta = client.get(RUTA_GERENTE)

    assert respuesta.status_code == 302
    assert respuesta.headers['Location'] == RUTA_ESTUDIANTE


def test_gerente_no_accede_a_bibliotecario(client, login, usuario_gerente):
    login('test_gerente', 'ClaveSegura123')

    respuesta = client.get(RUTA_BIBLIOTECARIO)

    assert respuesta.status_code == 302
    assert respuesta.headers['Location'] == RUTA_GERENTE


def test_gerente_no_accede_a_estudiante(client, login, usuario_gerente):
    login('test_gerente', 'ClaveSegura123')

    respuesta = client.get(RUTA_ESTUDIANTE)

    assert respuesta.status_code == 302
    assert respuesta.headers['Location'] == RUTA_GERENTE


def test_anonimo_redirige_a_login(client):
    for ruta in (RUTA_BIBLIOTECARIO, RUTA_ESTUDIANTE, RUTA_GERENTE):
        respuesta = client.get(ruta)
        assert respuesta.status_code == 302
        assert '/login' in respuesta.headers['Location']
