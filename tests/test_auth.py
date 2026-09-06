"""
Pruebas de autenticacion: login correcto por cada rol del sistema.
"""


def test_login_bibliotecario_exitoso(login, usuario_bibliotecario):
    respuesta = login('test_bibliotecario', 'ClaveSegura123')

    assert respuesta.status_code == 302
    assert respuesta.headers['Location'] == '/bibliotecario/inicio'


def test_login_estudiante_exitoso(login, usuario_estudiante):
    respuesta = login('1234567899', 'ClaveSegura123')

    assert respuesta.status_code == 302
    assert respuesta.headers['Location'] == '/estudiante/catalogo'


def test_login_gerente_exitoso(login, usuario_gerente):
    respuesta = login('test_gerente', 'ClaveSegura123')

    assert respuesta.status_code == 302
    assert respuesta.headers['Location'] == '/gerente/dashboard'


def test_login_credenciales_invalidas(login, usuario_bibliotecario):
    respuesta = login('test_bibliotecario', 'clave-incorrecta')

    # No debe redirigir: se re-renderiza el formulario con el mensaje de error.
    assert respuesta.status_code == 200
    assert 'incorrectos' in respuesta.get_data(as_text=True)


def test_login_con_bloqueo_sin_fecha_no_revienta(client, db, login, usuario_bibliotecario):
    """
    Regresion: una fila con bloqueado=TRUE pero fecha_bloqueo=NULL (edicion
    manual de la BD o restauracion parcial) hacia que la resta de fechas
    lanzara TypeError -> error 500 en el login, dejando la cuenta sin acceso.

    Sin fecha no se puede saber cuando expira el bloqueo, asi que se ignora y
    el login sigue su curso normal.
    """
    usuario_bibliotecario.bloqueado = True
    usuario_bibliotecario.fecha_bloqueo = None
    db.session.commit()

    respuesta = login('test_bibliotecario', 'ClaveSegura123')

    assert respuesta.status_code == 302, 'el login no debe fallar con 500'
    assert respuesta.headers['Location'] == '/bibliotecario/inicio'

    # Con la contraseña incorrecta tampoco revienta: responde el formulario.
    client.get('/logout')
    fallido = login('test_bibliotecario', 'ClaveIncorrecta')
    assert fallido.status_code == 200
    assert 'incorrectos' in fallido.get_data(as_text=True)


def test_el_bloqueo_normal_por_intentos_fallidos_sigue_funcionando(client, db, login, usuario_bibliotecario):
    """El fix no debe desactivar el bloqueo real (5 intentos -> 5 minutos)."""
    for _ in range(5):
        login('test_bibliotecario', 'ClaveIncorrecta')

    db.session.expire_all()
    assert usuario_bibliotecario.bloqueado is True
    assert usuario_bibliotecario.fecha_bloqueo is not None

    # Con la clave correcta sigue rechazando mientras dura el bloqueo.
    respuesta = login('test_bibliotecario', 'ClaveSegura123')
    assert respuesta.status_code == 200
    assert 'suspendida' in respuesta.get_data(as_text=True)
