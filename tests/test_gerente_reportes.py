"""
Prueba de la lista blanca de reportes del gerente.

El parametro <tipo> de la URL solo se usa para buscar en el diccionario
REPORTES (app/controllers/gerente/reportes.py). Un tipo inexistente debe
redirigir sin llegar a ejecutar ningun SQL, por eso esta prueba no
necesita database/setup.sql.
"""


def test_reporte_tipo_invalido_redirige(client, login, usuario_gerente):
    login('test_gerente', 'ClaveSegura123')

    respuesta = client.get('/gerente/reportes/tipo-que-no-existe')
    assert respuesta.status_code == 302
    assert respuesta.headers['Location'] == '/gerente/reportes'

    respuesta_seguida = client.get('/gerente/reportes/tipo-que-no-existe', follow_redirects=True)
    assert respuesta_seguida.status_code == 200
    assert 'no existe' in respuesta_seguida.get_data(as_text=True)
