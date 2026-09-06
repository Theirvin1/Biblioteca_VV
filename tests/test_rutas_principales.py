"""
Pruebas de las rutas principales de cada modulo.

Las marcadas con @pytest.mark.requiere_setup_sql llaman a funciones o
vistas SQL de database/setup.sql (vista_prestamos_vencidos,
obtener_indicadores_dashboard). tests/conftest.py aplica ese script
automaticamente sobre la base de pruebas antes de correr cualquier
prueba, asi que no requieren ningun paso manual: el marcador solo
documenta la dependencia.
"""
import pytest


@pytest.mark.requiere_setup_sql
def test_bibliotecario_inicio(client, login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')

    respuesta = client.get('/bibliotecario/inicio')

    assert respuesta.status_code == 200
    assert 'Panel del bibliotecario' in respuesta.get_data(as_text=True)


def test_bibliotecario_libros(client, login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')

    respuesta = client.get('/bibliotecario/libros')

    assert respuesta.status_code == 200
    assert 'Catálogo de libros' in respuesta.get_data(as_text=True)


def test_estudiante_catalogo(client, login, usuario_estudiante):
    login('1234567899', 'ClaveSegura123')

    respuesta = client.get('/estudiante/catalogo')

    assert respuesta.status_code == 200
    assert 'Catálogo de libros' in respuesta.get_data(as_text=True)


def test_estudiante_prestamos(client, login, usuario_estudiante):
    login('1234567899', 'ClaveSegura123')

    respuesta = client.get('/estudiante/prestamos')

    assert respuesta.status_code == 200
    assert 'Mis préstamos' in respuesta.get_data(as_text=True)


@pytest.mark.requiere_setup_sql
def test_gerente_dashboard(client, login, usuario_gerente):
    login('test_gerente', 'ClaveSegura123')

    respuesta = client.get('/gerente/dashboard')

    assert respuesta.status_code == 200
    assert 'Panel del gerente' in respuesta.get_data(as_text=True)


def test_gerente_reportes_listado(client, login, usuario_gerente):
    login('test_gerente', 'ClaveSegura123')

    respuesta = client.get('/gerente/reportes')

    assert respuesta.status_code == 200
    assert 'Reportes' in respuesta.get_data(as_text=True)
