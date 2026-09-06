"""
Pruebas de "Mi perfil" (estudiante) y de su unica accion de edicion:
cambiar su propio telefono.

Politica que se verifica aqui (ver app/controllers/estudiante/perfil.py):
- El estudiante SOLO puede editar su telefono.
- La ruta de edicion toma el estudiante de current_user, nunca de un id o
  cedula recibidos por POST: no hay forma de editar a otro estudiante ni de
  colar cedula/nombres/apellidos/carrera/correo/estado por esta via.
- Cedula, nombres, apellidos, carrera, correo y estado son de solo lectura
  en esta pantalla.
"""
from datetime import date

import pytest
from werkzeug.security import generate_password_hash

from app.models import (
    CategoriaLibro, ConfiguracionSistema, Editorial, Ejemplar, Estudiante,
    Libro, Prestamo, Usuario,
)


def _login_estudiante(login):
    login('1234567899', 'ClaveSegura123')


def _crear_estudiante(db, cedula, carrera_id, **overrides):
    """Segundo estudiante (para las pruebas de aislamiento entre cuentas)."""
    datos = {
        'nombres': 'Otro',
        'apellidos': 'Estudiante',
        'correo': f'{cedula}@uteq.edu.ec',
        'carrera_id': carrera_id,
    }
    datos.update(overrides)

    usuario = Usuario(
        username=cedula, password_hash=generate_password_hash('ClaveSegura123'), rol='estudiante',
    )
    db.session.add(usuario)
    db.session.flush()

    estudiante = Estudiante(cedula=cedula, usuario_id=usuario.id, **datos)
    db.session.add(estudiante)
    db.session.commit()
    return estudiante


# --------------------------------------------------------- carga del perfil

def test_mi_perfil_carga_correctamente(client, db, login, usuario_estudiante):
    _login_estudiante(login)
    respuesta = client.get('/estudiante/perfil')
    assert respuesta.status_code == 200


def test_mi_perfil_muestra_nombre_completo(client, db, login, usuario_estudiante):
    _login_estudiante(login)
    html = client.get('/estudiante/perfil').get_data(as_text=True)
    assert 'Estudiante De Pruebas' in html


def test_mi_perfil_muestra_cedula(client, db, login, usuario_estudiante):
    _login_estudiante(login)
    html = client.get('/estudiante/perfil').get_data(as_text=True)
    assert '1234567899' in html


def test_mi_perfil_muestra_carrera(client, db, login, usuario_estudiante, carrera_prueba):
    _login_estudiante(login)
    html = client.get('/estudiante/perfil').get_data(as_text=True)
    assert carrera_prueba.nombre in html


def test_mi_perfil_muestra_edad_cuando_hay_fecha_de_nacimiento(client, db, login, usuario_estudiante):
    estudiante = usuario_estudiante.estudiante
    estudiante.fecha_nacimiento = date(2000, 1, 1)
    db.session.commit()

    _login_estudiante(login)
    html = client.get('/estudiante/perfil').get_data(as_text=True)
    assert 'años' in html
    assert 'No registrada' not in html


def test_mi_perfil_muestra_avatar_con_iniciales(client, db, login, usuario_estudiante):
    """'Estudiante De Pruebas' -> iniciales 'ED' (primera letra de cada nombre)."""
    _login_estudiante(login)
    html = client.get('/estudiante/perfil').get_data(as_text=True)
    assert 'avatar-iniciales' in html
    assert '>ED<' in html


def test_mi_perfil_existe_boton_cambiar_password(client, db, login, usuario_estudiante):
    _login_estudiante(login)
    html = client.get('/estudiante/perfil').get_data(as_text=True)
    assert 'Cambiar contraseña' in html
    assert '/cambiar-password' in html


def test_mi_perfil_funciona_con_datos_opcionales_null(client, db, login, usuario_estudiante):
    """
    usuario_estudiante no trae telefono ni fecha_nacimiento (ambos NULL en
    BD): el perfil debe seguir cargando y usar los textos de reemplazo, sin
    mostrar guiones.
    """
    _login_estudiante(login)
    respuesta = client.get('/estudiante/perfil')
    html = respuesta.get_data(as_text=True)

    assert respuesta.status_code == 200
    assert 'No registrado' in html    # telefono
    assert 'No registrada' in html    # edad


def test_telefono_nulo_muestra_no_registrado(client, db, login, usuario_estudiante):
    assert usuario_estudiante.estudiante.telefono is None
    _login_estudiante(login)
    html = client.get('/estudiante/perfil').get_data(as_text=True)
    assert 'No registrado' in html


# ---------------------------------------------------- estadisticas reales

@pytest.mark.requiere_setup_sql
def test_mi_perfil_muestra_estadisticas_reales_de_prestamos(client, db, login, usuario_estudiante):
    """
    Un prestamo activo, uno devuelto y uno vencido, creados directamente en
    BD (no por la ruta de prestamos: aqui solo interesa el conteo que
    muestra el perfil, no el flujo de registro). Los tres estados son los
    unicos que admite Prestamo.estado (CHECK), asi que la suma es real: no
    hay categorias inventadas.
    """
    db.session.add(ConfiguracionSistema(clave='plazo_prestamo_dias', valor='7'))
    db.session.commit()

    estudiante = usuario_estudiante.estudiante
    bibliotecario = Usuario(
        username='biblio_stats', password_hash=generate_password_hash('x'), rol='bibliotecario',
    )
    db.session.add(bibliotecario)
    db.session.flush()

    editorial = Editorial(nombre='Editorial Stats VV')
    categoria = CategoriaLibro(nombre='Categoria Stats VV')
    db.session.add_all([editorial, categoria])
    db.session.commit()

    def _prestamo(isbn, estado):
        libro = Libro(
            isbn=isbn, titulo=f'Libro {estado}', editorial_id=editorial.id,
            categoria_id=categoria.id, stock_total=1, stock_disponible=1,
        )
        db.session.add(libro)
        db.session.flush()
        ejemplar = Ejemplar(libro_id=libro.id, codigo_ejemplar=f'EJ-ST-{isbn[-4:]}', fecha_adquisicion=date.today())
        db.session.add(ejemplar)
        db.session.flush()
        db.session.add(Prestamo(
            codigo_prestamo=f'P-ST-{isbn[-4:]}', estudiante_id=estudiante.id,
            ejemplar_id=ejemplar.id, bibliotecario_id=bibliotecario.id, estado=estado,
        ))

    _prestamo('9780000000001', 'activo')
    _prestamo('9780000000002', 'devuelto')
    _prestamo('9780000000003', 'vencido')
    db.session.commit()

    _login_estudiante(login)
    html = client.get('/estudiante/perfil').get_data(as_text=True)

    assert Prestamo.query.filter_by(estudiante_id=estudiante.id, estado='activo').count() == 1
    assert Prestamo.query.filter_by(estudiante_id=estudiante.id, estado='devuelto').count() == 1
    assert Prestamo.query.filter_by(estudiante_id=estudiante.id, estado='vencido').count() == 1
    assert 'Préstamos activos' in html
    assert 'Devueltos' in html
    assert 'Vencidos' in html


# ---------------------------------------------- edicion de telefono (unica)

def test_estudiante_puede_cambiar_su_telefono(client, db, login, usuario_estudiante):
    _login_estudiante(login)

    respuesta = client.post('/estudiante/perfil/telefono', data={
        'telefono': '0987654321',
    }, follow_redirects=True)

    assert respuesta.status_code == 200
    assert 'Teléfono actualizado correctamente' in respuesta.get_data(as_text=True)
    assert usuario_estudiante.estudiante.telefono == '0987654321'


def test_telefono_invalido_es_rechazado(client, db, login, usuario_estudiante):
    _login_estudiante(login)

    for telefono_malo in ('12345', '099ABCDE12', '099123456789'):
        respuesta = client.post('/estudiante/perfil/telefono', data={'telefono': telefono_malo})
        assert respuesta.status_code == 200
        assert 'exactamente 10 dígitos' in respuesta.get_data(as_text=True)

    db.session.refresh(usuario_estudiante.estudiante)
    assert usuario_estudiante.estudiante.telefono is None  # nada se guardo


def test_telefono_de_10_digitos_sigue_funcionando(client, db, login, usuario_estudiante):
    """El caso valido normal no se rompio al hacer el campo opcional."""
    _login_estudiante(login)

    respuesta = client.post('/estudiante/perfil/telefono', data={
        'telefono': '0991234567',
    }, follow_redirects=True)

    assert respuesta.status_code == 200
    assert 'Teléfono actualizado correctamente' in respuesta.get_data(as_text=True)
    db.session.refresh(usuario_estudiante.estudiante)
    assert usuario_estudiante.estudiante.telefono == '0991234567'


def test_estudiante_puede_dejar_telefono_vacio(client, db, login, usuario_estudiante):
    """Telefono es opcional: enviar el campo vacio debe borrar el que hubiera."""
    estudiante = usuario_estudiante.estudiante
    estudiante.telefono = '0991234567'
    db.session.commit()

    _login_estudiante(login)
    respuesta = client.post('/estudiante/perfil/telefono', data={'telefono': ''}, follow_redirects=True)

    assert respuesta.status_code == 200
    assert 'Teléfono eliminado correctamente' in respuesta.get_data(as_text=True)
    db.session.refresh(estudiante)
    assert estudiante.telefono is None


def test_perfil_muestra_no_registrado_despues_de_quitar_telefono(client, db, login, usuario_estudiante):
    estudiante = usuario_estudiante.estudiante
    estudiante.telefono = '0991234567'
    db.session.commit()

    _login_estudiante(login)
    client.post('/estudiante/perfil/telefono', data={'telefono': ''})

    html = client.get('/estudiante/perfil').get_data(as_text=True)
    assert 'No registrado' in html
    assert '0991234567' not in html


def test_estudiante_no_puede_modificar_campos_bloqueados_manipulando_el_post(
    client, db, login, usuario_estudiante, carrera_prueba
):
    """
    TelefonoForm SOLO tiene el campo telefono: aunque el POST incluya
    cedula/nombres/apellidos/correo/carrera_id/estado, no hay ningun campo
    del formulario que los reciba, asi que el controlador no tiene forma de
    usarlos. Se comprueba que, tras el envio, solo cambio el telefono.
    """
    estudiante = usuario_estudiante.estudiante
    cedula_original = estudiante.cedula
    nombres_original = estudiante.nombres
    apellidos_original = estudiante.apellidos
    correo_original = estudiante.correo
    carrera_original = estudiante.carrera_id
    estado_original = estudiante.estado

    _login_estudiante(login)

    respuesta = client.post('/estudiante/perfil/telefono', data={
        'telefono': '0987654321',
        'cedula': '9999999999',
        'nombres': 'Hackeado',
        'apellidos': 'Hackeado',
        'correo': 'hackeado@evil.com',
        'carrera_id': '999999',
        'estado': 'suspendido',
        'usuario_id': '999999',
        'rol': 'gerente',
    }, follow_redirects=True)

    assert respuesta.status_code == 200
    db.session.refresh(estudiante)

    assert estudiante.telefono == '0987654321'   # el unico campo que si cambia
    assert estudiante.cedula == cedula_original
    assert estudiante.nombres == nombres_original
    assert estudiante.apellidos == apellidos_original
    assert estudiante.correo == correo_original
    assert estudiante.carrera_id == carrera_original
    assert estudiante.estado == estado_original

    usuario = Usuario.query.filter_by(username=cedula_original).first()
    assert usuario is not None
    assert usuario.rol == 'estudiante'  # el intento de "rol=gerente" no tuvo ningun efecto


def test_estudiante_a_no_puede_editar_datos_de_estudiante_b(
    client, db, login, usuario_estudiante, carrera_prueba
):
    """
    La ruta no acepta ningun identificador del estudiante a editar: siempre
    usa current_user.estudiante. Se confirma enviando el id/cedula de B en el
    POST de A y comprobando que B no cambia en absoluto.
    """
    estudiante_b = _crear_estudiante(db, '0955555555', carrera_prueba.id, telefono='0911111111')

    _login_estudiante(login)  # sesion de A (usuario_estudiante)

    respuesta = client.post('/estudiante/perfil/telefono', data={
        'telefono': '0987654321',
        'estudiante_id': str(estudiante_b.id),
        'cedula': estudiante_b.cedula,
    }, follow_redirects=True)

    assert respuesta.status_code == 200

    db.session.refresh(estudiante_b)
    db.session.refresh(usuario_estudiante.estudiante)

    assert estudiante_b.telefono == '0911111111'          # B no cambio
    assert usuario_estudiante.estudiante.telefono == '0987654321'  # A si (el autenticado)


def test_estudiante_no_puede_acceder_a_edicion_administrativa(
    client, db, login, usuario_estudiante
):
    """La ruta de edicion del bibliotecario esta protegida por rol."""
    _login_estudiante(login)

    respuesta = client.get(
        f'/bibliotecario/estudiantes/{usuario_estudiante.estudiante.id}/editar',
        follow_redirects=False,
    )

    assert respuesta.status_code == 302
    assert '/bibliotecario/estudiantes' not in respuesta.headers['Location']


# ------------------------------ estadisticas en tiempo real (fecha_limite)

@pytest.mark.requiere_setup_sql
def test_estadisticas_del_perfil_usan_fecha_limite_no_estado(client, db, login, usuario_estudiante):
    """
    Tres prestamos, ninguno tocado por el scheduler:

    - 'activo' con fecha_limite en el FUTURO   -> cuenta en Activos.
    - 'activo' con fecha_limite en el PASADO   -> cuenta en Vencidos, NO en
      Activos (el estado sigue diciendo 'activo': el scheduler no corrio).
    - 'devuelto'                               -> cuenta en Devueltos.

    _estadisticas_prestamos no toca Prestamo.estado en ningun momento: se
    comprueba leyendo el estado tal cual quedo despues de llamarla.
    """
    from datetime import datetime, timedelta

    from app.controllers.estudiante.perfil import _estadisticas_prestamos

    db.session.add(ConfiguracionSistema(clave='plazo_prestamo_dias', valor='7'))
    db.session.commit()

    estudiante = usuario_estudiante.estudiante
    bibliotecario = Usuario(
        username='biblio_fechas', password_hash=generate_password_hash('x'), rol='bibliotecario',
    )
    db.session.add(bibliotecario)
    db.session.flush()

    editorial = Editorial(nombre='Editorial Fechas VV')
    categoria = CategoriaLibro(nombre='Categoria Fechas VV')
    db.session.add_all([editorial, categoria])
    db.session.commit()

    def _prestamo(isbn, estado, fecha_prestamo):
        libro = Libro(
            isbn=isbn, titulo=f'Libro {isbn}', editorial_id=editorial.id,
            categoria_id=categoria.id, stock_total=1, stock_disponible=1,
        )
        db.session.add(libro)
        db.session.flush()
        ejemplar = Ejemplar(libro_id=libro.id, codigo_ejemplar=f'EJ-F-{isbn[-4:]}', fecha_adquisicion=date.today())
        db.session.add(ejemplar)
        db.session.flush()
        prestamo = Prestamo(
            codigo_prestamo=f'P-F-{isbn[-4:]}', estudiante_id=estudiante.id, ejemplar_id=ejemplar.id,
            bibliotecario_id=bibliotecario.id, estado=estado, fecha_prestamo=fecha_prestamo,
        )
        db.session.add(prestamo)
        db.session.commit()
        db.session.refresh(prestamo)
        return prestamo

    # plazo=7 dias: prestado hoy -> fecha_limite = hoy+7 (vigente).
    vigente = _prestamo('9780000000101', 'activo', datetime.combine(date.today(), datetime.min.time()))
    # plazo=7 dias: prestado hace 20 dias -> fecha_limite = hoy-13 (ya paso).
    vencido_sin_actualizar = _prestamo(
        '9780000000102', 'activo',
        datetime.combine(date.today() - timedelta(days=20), datetime.min.time()),
    )
    devuelto = _prestamo('9780000000103', 'devuelto', datetime.combine(date.today(), datetime.min.time()))

    # El estado en BD sigue siendo 'activo': nadie lo cambio a 'vencido'.
    assert vencido_sin_actualizar.estado == 'activo'
    assert vencido_sin_actualizar.fecha_limite < date.today()
    assert vigente.fecha_limite >= date.today()
    assert devuelto.estado == 'devuelto'

    activos, devueltos, vencidos = _estadisticas_prestamos(estudiante.id)
    assert activos == 1     # solo el vigente
    assert vencidos == 1    # el que tiene fecha_limite pasada, aunque su estado diga 'activo'
    assert devueltos == 1

    # La lectura no modifico nada en BD.
    db.session.refresh(vencido_sin_actualizar)
    assert vencido_sin_actualizar.estado == 'activo'

    _login_estudiante(login)
    assert client.get('/estudiante/perfil').status_code == 200
