"""
Gestion de usuarios del gerente: listado/filtros/paginacion, activar y
desactivar, restablecimiento de contraseña y cambio de rol restringido.

Incluye tambien el nuevo flujo de credenciales temporales del registro de
estudiante y las garantias de seguridad: la clave temporal nunca queda en la
base de datos (solo su hash) y obliga a cambiarla en el primer ingreso.
"""
import pytest
from werkzeug.security import check_password_hash, generate_password_hash

from app.models import Carrera, Estudiante, Facultad, Usuario
from app.seguridad import ALFABETO_TEMPORAL, generar_password_temporal

pytestmark = pytest.mark.requiere_setup_sql


@pytest.fixture
def gerente_logueado(login, usuario_gerente):
    login('test_gerente', 'ClaveSegura123')
    return usuario_gerente


@pytest.fixture
def crear_usuario(db):
    def _crear(username, rol='bibliotecario', activo=True, password='ClaveSegura123'):
        usuario = Usuario(
            username=username,
            password_hash=generate_password_hash(password),
            rol=rol,
            activo=activo,
        )
        db.session.add(usuario)
        db.session.commit()
        return usuario
    return _crear


@pytest.fixture
def carrera(db):
    facultad = Facultad(nombre='Facultad Usuarios')
    db.session.add(facultad)
    db.session.flush()
    carrera = Carrera(nombre='Carrera Usuarios', facultad_id=facultad.id)
    db.session.add(carrera)
    db.session.commit()
    return carrera


@pytest.fixture
def crear_estudiante_con_cuenta(db, carrera):
    def _crear(cedula, nombres='Est', apellidos='Prueba'):
        usuario = Usuario(
            username=cedula,
            password_hash=generate_password_hash('ClaveSegura123'),
            rol='estudiante',
        )
        db.session.add(usuario)
        db.session.flush()
        estudiante = Estudiante(
            cedula=cedula, nombres=nombres, apellidos=apellidos,
            correo=f'{cedula}@uteq.edu.ec', carrera_id=carrera.id, usuario_id=usuario.id,
        )
        db.session.add(estudiante)
        db.session.commit()
        return usuario, estudiante
    return _crear


def _datos_estudiante(**overrides):
    datos = {
        'cedula': '1710034065',
        'nombres': 'Nuevo',
        'apellidos': 'Estudiante',
        'correo': 'nuevo.estudiante@uteq.edu.ec',
        'telefono': '0991234567',
        'fecha_nacimiento': '2003-05-20',
        'genero': 'M',
    }
    datos.update(overrides)
    return datos


# ------------------------------------------------------------------ acceso

def test_gerente_puede_abrir_gestion_de_usuarios(client, gerente_logueado):
    respuesta = client.get('/gerente/usuarios')
    assert respuesta.status_code == 200
    assert 'Gestión de usuarios' in respuesta.get_data(as_text=True)


def test_bibliotecario_no_puede_acceder(client, login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')
    respuesta = client.get('/gerente/usuarios')
    assert respuesta.status_code == 302
    assert '/bibliotecario' in respuesta.headers['Location']


def test_estudiante_no_puede_acceder(client, login, usuario_estudiante):
    login('1234567899', 'ClaveSegura123')
    respuesta = client.get('/gerente/usuarios')
    assert respuesta.status_code == 302
    assert '/estudiante' in respuesta.headers['Location']


def test_acciones_administrativas_requieren_rol_gerente(client, login, usuario_bibliotecario, crear_usuario):
    objetivo = crear_usuario('objetivo_bib')
    login('test_bibliotecario', 'ClaveSegura123')

    for url in (
        f'/gerente/usuarios/{objetivo.id}/estado',
        f'/gerente/usuarios/{objetivo.id}/restablecer-password',
        f'/gerente/usuarios/{objetivo.id}/rol',
    ):
        respuesta = client.post(url, data={'rol': 'gerente'})
        assert respuesta.status_code == 302, url
        assert '/gerente' not in respuesta.headers['Location'], url

    # Nada cambio.
    assert objetivo.activo is True
    assert objetivo.rol == 'bibliotecario'


# --------------------------------------------------- listado / filtros

def test_listado_pagina_de_10(client, db, gerente_logueado, crear_usuario):
    for indice in range(12):
        crear_usuario(f'usuario{indice:02d}')

    texto = client.get('/gerente/usuarios').get_data(as_text=True)
    # 12 creados + el gerente de la sesion = 13.
    assert 'Mostrando 1-10 de 13 usuarios' in texto

    pagina2 = client.get('/gerente/usuarios?page=2').get_data(as_text=True)
    assert 'Mostrando 11-13 de 13 usuarios' in pagina2


def test_filtro_por_username(client, db, gerente_logueado, crear_usuario):
    crear_usuario('bibliotecario_norte')
    crear_usuario('bibliotecario_sur')

    texto = client.get('/gerente/usuarios?q=norte').get_data(as_text=True)
    assert 'bibliotecario_norte' in texto
    assert 'bibliotecario_sur' not in texto


def test_filtro_por_cedula_y_por_nombre(client, db, gerente_logueado, crear_estudiante_con_cuenta):
    crear_estudiante_con_cuenta('0911111111', nombres='Ana', apellidos='Lopez')
    crear_estudiante_con_cuenta('0922222222', nombres='Luis', apellidos='Mendoza')

    por_cedula = client.get('/gerente/usuarios?q=0911111111').get_data(as_text=True)
    assert 'Ana Lopez' in por_cedula
    assert 'Luis Mendoza' not in por_cedula

    por_nombre = client.get('/gerente/usuarios?q=Mendoza').get_data(as_text=True)
    assert 'Luis Mendoza' in por_nombre
    assert 'Ana Lopez' not in por_nombre


def test_filtro_por_rol(client, db, gerente_logueado, crear_usuario, crear_estudiante_con_cuenta):
    crear_usuario('un_bibliotecario', rol='bibliotecario')
    crear_estudiante_con_cuenta('0933333333', nombres='Pedro', apellidos='Estudiante')

    solo_bibliotecarios = client.get('/gerente/usuarios?rol=bibliotecario').get_data(as_text=True)
    assert 'un_bibliotecario' in solo_bibliotecarios
    assert '0933333333' not in solo_bibliotecarios

    solo_estudiantes = client.get('/gerente/usuarios?rol=estudiante').get_data(as_text=True)
    assert '0933333333' in solo_estudiantes
    assert 'un_bibliotecario' not in solo_estudiantes


def test_filtro_por_activo_inactivo(client, db, gerente_logueado, crear_usuario):
    crear_usuario('cuenta_viva', activo=True)
    crear_usuario('cuenta_apagada', activo=False)

    activos = client.get('/gerente/usuarios?estado=activo').get_data(as_text=True)
    assert 'cuenta_viva' in activos
    assert 'cuenta_apagada' not in activos

    inactivos = client.get('/gerente/usuarios?estado=inactivo').get_data(as_text=True)
    assert 'cuenta_apagada' in inactivos
    assert 'cuenta_viva' not in inactivos


def test_filtros_se_conservan_al_cambiar_de_pagina(client, db, gerente_logueado, crear_usuario):
    for indice in range(12):
        crear_usuario(f'filtrado{indice:02d}', rol='bibliotecario')
    crear_usuario('otro_que_no_aparece', rol='bibliotecario')

    respuesta = client.get('/gerente/usuarios?q=filtrado&rol=bibliotecario&page=2')
    texto = respuesta.get_data(as_text=True)
    assert 'otro_que_no_aparece' not in texto
    assert 'Mostrando 11-12 de 12 usuarios' in texto
    assert 'q=filtrado' in texto
    assert 'rol=bibliotecario' in texto


def test_el_listado_no_muestra_hashes(client, db, gerente_logueado, crear_usuario):
    usuario = crear_usuario('sin_hash_visible')
    texto = client.get('/gerente/usuarios').get_data(as_text=True)
    assert 'sin_hash_visible' in texto
    assert usuario.password_hash not in texto
    assert 'scrypt' not in texto


# --------------------------------------------------- activar / desactivar

def test_gerente_puede_desactivar_otro_usuario(client, db, gerente_logueado, crear_usuario):
    objetivo = crear_usuario('para_desactivar')

    respuesta = client.post(f'/gerente/usuarios/{objetivo.id}/estado',
                            data={'accion': 'desactivar'}, follow_redirects=True)
    assert respuesta.status_code == 200
    assert 'fue desactivada' in respuesta.get_data(as_text=True)

    db.session.expire_all()
    assert db.session.get(Usuario, objetivo.id).activo is False

    # Y puede volver a activarla.
    client.post(f'/gerente/usuarios/{objetivo.id}/estado',
                data={'accion': 'activar'}, follow_redirects=True)
    db.session.expire_all()
    assert db.session.get(Usuario, objetivo.id).activo is True


def test_pedir_desactivar_dos_veces_no_vuelve_a_activar(client, db, gerente_logueado, crear_usuario):
    """La accion es explicita e idempotente: un doble POST no invierte el estado."""
    objetivo = crear_usuario('doble_desactivar')

    primera = client.post(f'/gerente/usuarios/{objetivo.id}/estado',
                          data={'accion': 'desactivar'}, follow_redirects=True)
    assert 'fue desactivada' in primera.get_data(as_text=True)

    segunda = client.post(f'/gerente/usuarios/{objetivo.id}/estado',
                          data={'accion': 'desactivar'}, follow_redirects=True)
    assert 'ya estaba desactivada' in segunda.get_data(as_text=True)

    db.session.expire_all()
    assert db.session.get(Usuario, objetivo.id).activo is False


def test_pedir_activar_dos_veces_no_vuelve_a_desactivar(client, db, gerente_logueado, crear_usuario):
    objetivo = crear_usuario('doble_activar', activo=False)

    primera = client.post(f'/gerente/usuarios/{objetivo.id}/estado',
                          data={'accion': 'activar'}, follow_redirects=True)
    assert 'fue activada' in primera.get_data(as_text=True)

    segunda = client.post(f'/gerente/usuarios/{objetivo.id}/estado',
                          data={'accion': 'activar'}, follow_redirects=True)
    assert 'ya estaba activa' in segunda.get_data(as_text=True)

    db.session.expire_all()
    assert db.session.get(Usuario, objetivo.id).activo is True


def test_accion_de_estado_invalida_se_rechaza(client, db, gerente_logueado, crear_usuario):
    objetivo = crear_usuario('accion_invalida')

    respuesta = client.post(f'/gerente/usuarios/{objetivo.id}/estado',
                            data={'accion': 'borrar'}, follow_redirects=True)
    assert 'Acción no válida' in respuesta.get_data(as_text=True)

    # Sin `accion` tampoco hace nada (ya no es un toggle).
    sin_accion = client.post(f'/gerente/usuarios/{objetivo.id}/estado', follow_redirects=True)
    assert 'Acción no válida' in sin_accion.get_data(as_text=True)

    db.session.expire_all()
    assert db.session.get(Usuario, objetivo.id).activo is True


def test_usuario_inactivo_no_puede_iniciar_sesion(client, db, crear_usuario, login):
    crear_usuario('cuenta_inactiva', activo=False, password='ClaveSegura123')

    respuesta = login('cuenta_inactiva', 'ClaveSegura123')
    assert respuesta.status_code == 200
    assert 'desactivada' in respuesta.get_data(as_text=True)


def test_usuario_autenticado_pierde_acceso_al_quedar_inactivo(client, db, login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')
    assert client.get('/bibliotecario/inicio').status_code == 200

    # El gerente lo desactiva mientras la sesion sigue abierta.
    usuario_bibliotecario.activo = False
    db.session.commit()

    respuesta = client.get('/bibliotecario/inicio')
    assert respuesta.status_code == 302
    assert '/login' in respuesta.headers['Location']

    # La sesion quedo cerrada: sigue sin poder entrar.
    seguimiento = client.get('/bibliotecario/inicio', follow_redirects=True)
    assert 'desactivada' in seguimiento.get_data(as_text=True)


def test_gerente_no_puede_desactivarse_a_si_mismo(client, db, gerente_logueado):
    respuesta = client.post(
        f'/gerente/usuarios/{gerente_logueado.id}/estado',
        data={'accion': 'desactivar'}, follow_redirects=True,
    )
    assert 'No puedes desactivar tu propia cuenta' in respuesta.get_data(as_text=True)

    db.session.expire_all()
    assert db.session.get(Usuario, gerente_logueado.id).activo is True


def test_no_se_puede_desactivar_al_ultimo_gerente_activo(client, db, gerente_logueado, crear_usuario):
    otro_gerente = crear_usuario('gerente_suplente', rol='gerente')

    # Con dos gerentes activos, desactivar a uno si se permite.
    respuesta = client.post(f'/gerente/usuarios/{otro_gerente.id}/estado',
                            data={'accion': 'desactivar'}, follow_redirects=True)
    assert 'fue desactivada' in respuesta.get_data(as_text=True)

    db.session.expire_all()
    assert db.session.get(Usuario, otro_gerente.id).activo is False

    # Ahora el de la sesion es el unico gerente activo: no puede quedar ninguno.
    respuesta = client.post(
        f'/gerente/usuarios/{gerente_logueado.id}/estado',
        data={'accion': 'desactivar'}, follow_redirects=True,
    )
    texto = respuesta.get_data(as_text=True)
    assert 'No puedes desactivar tu propia cuenta' in texto
    db.session.expire_all()
    assert db.session.get(Usuario, gerente_logueado.id).activo is True


def test_no_se_puede_desactivar_al_ultimo_gerente_aunque_no_sea_uno_mismo(
    client, db, login, crear_usuario
):
    """Un gerente A desactiva a B, luego B (unico activo restante) no puede caer."""
    gerente_a = crear_usuario('gerente_a', rol='gerente', password='ClaveSegura123')
    gerente_b = crear_usuario('gerente_b', rol='gerente', password='ClaveSegura123')

    login('gerente_a', 'ClaveSegura123')
    client.post(f'/gerente/usuarios/{gerente_b.id}/estado',
                data={'accion': 'desactivar'}, follow_redirects=True)
    db.session.expire_all()
    assert db.session.get(Usuario, gerente_b.id).activo is False

    # gerente_a queda como unico gerente activo y no puede desactivarse.
    respuesta = client.post(f'/gerente/usuarios/{gerente_a.id}/estado',
                            data={'accion': 'desactivar'}, follow_redirects=True)
    assert 'No puedes desactivar tu propia cuenta' in respuesta.get_data(as_text=True)
    db.session.expire_all()
    assert db.session.get(Usuario, gerente_a.id).activo is True


# --------------------------------------------------- restablecer password

def _extraer_password_temporal(html):
    """Lee la clave que la pantalla de credenciales muestra una sola vez."""
    marca = 'credencial-temporal">'
    inicio = html.find(marca)
    assert inicio != -1, 'la respuesta no muestra una clave temporal'
    inicio += len(marca)
    return html[inicio:html.find('<', inicio)].strip()


def test_reset_genera_hash_nuevo_y_muestra_clave_temporal(client, db, gerente_logueado, crear_usuario):
    objetivo = crear_usuario('para_resetear', password='ClaveOriginal123')
    hash_anterior = objetivo.password_hash

    respuesta = client.post(f'/gerente/usuarios/{objetivo.id}/restablecer-password')
    assert respuesta.status_code == 200
    texto = respuesta.get_data(as_text=True)

    assert 'Contraseña restablecida correctamente' in texto
    assert 'para_resetear' in texto
    assert 'una sola vez' in texto

    temporal = _extraer_password_temporal(texto)
    assert len(temporal) >= 10

    db.session.expire_all()
    actualizado = db.session.get(Usuario, objetivo.id)
    assert actualizado.password_hash != hash_anterior
    assert actualizado.debe_cambiar_password is True
    # La clave vieja ya no sirve; la nueva si.
    assert not check_password_hash(actualizado.password_hash, 'ClaveOriginal123')
    assert check_password_hash(actualizado.password_hash, temporal)


def test_la_clave_temporal_no_queda_persistida_en_bd(client, db, gerente_logueado, crear_usuario):
    objetivo = crear_usuario('sin_rastro')

    respuesta = client.post(f'/gerente/usuarios/{objetivo.id}/restablecer-password')
    temporal = _extraer_password_temporal(respuesta.get_data(as_text=True))

    db.session.expire_all()
    actualizado = db.session.get(Usuario, objetivo.id)
    # En la fila solo hay hash: la clave en claro no aparece en ningun campo.
    assert temporal not in actualizado.password_hash
    valores = [
        str(getattr(actualizado, columna.name))
        for columna in Usuario.__table__.columns
    ]
    assert all(temporal not in valor for valor in valores)

    # Tampoco quedo en la auditoria del restablecimiento.
    registros = db.session.execute(
        db.text("SELECT COALESCE(datos_nuevos::text, '') || COALESCE(datos_anteriores::text, '') "
                "FROM auditoria WHERE modulo = 'gestion_usuarios'")
    ).scalars().all()
    assert registros, 'se esperaba al menos un registro de auditoria'
    assert all(temporal not in registro for registro in registros)
    assert all('scrypt' not in registro for registro in registros)


def test_la_clave_temporal_sirve_para_iniciar_sesion_y_obliga_a_cambiarla(
    client, db, gerente_logueado, crear_usuario, login
):
    objetivo = crear_usuario('reseteado_login')
    respuesta = client.post(f'/gerente/usuarios/{objetivo.id}/restablecer-password')
    temporal = _extraer_password_temporal(respuesta.get_data(as_text=True))

    client.get('/logout')
    acceso = login('reseteado_login', temporal)
    assert acceso.status_code == 302

    # Cualquier pantalla redirige a cambiar la contraseña.
    forzado = client.get('/bibliotecario/inicio')
    assert forzado.status_code == 302
    assert '/cambiar-password' in forzado.headers['Location']


def test_no_existe_ruta_get_para_recuperar_la_clave(client, gerente_logueado, crear_usuario):
    objetivo = crear_usuario('sin_get')
    respuesta = client.get(f'/gerente/usuarios/{objetivo.id}/restablecer-password')
    assert respuesta.status_code == 405  # Method Not Allowed: solo POST


def test_respuesta_de_reset_no_se_cachea(client, gerente_logueado, crear_usuario):
    objetivo = crear_usuario('sin_cache_reset')
    respuesta = client.post(f'/gerente/usuarios/{objetivo.id}/restablecer-password')

    cache_control = respuesta.headers.get('Cache-Control', '')
    assert 'no-store' in cache_control
    assert 'private' in cache_control
    assert 'max-age=0' in cache_control
    assert respuesta.headers.get('Pragma') == 'no-cache'
    assert respuesta.headers.get('Expires') == '0'


def test_respuesta_de_registro_no_se_cachea(client, db, login, usuario_bibliotecario, carrera):
    login('test_bibliotecario', 'ClaveSegura123')
    respuesta = client.post(
        '/bibliotecario/estudiantes/nuevo',
        data=_datos_estudiante(carrera_id=str(carrera.id)),
    )

    cache_control = respuesta.headers.get('Cache-Control', '')
    assert 'no-store' in cache_control
    assert 'private' in cache_control
    assert respuesta.headers.get('Pragma') == 'no-cache'
    assert respuesta.headers.get('Expires') == '0'


def test_pantalla_de_reset_prepara_navegacion_segura(client, gerente_logueado, crear_usuario):
    """history.replaceState deja una URL GET para que F5 no reenvie el POST."""
    objetivo = crear_usuario('navegacion_reset')
    texto = client.post(
        f'/gerente/usuarios/{objetivo.id}/restablecer-password'
    ).get_data(as_text=True)

    assert 'data-url-segura="/gerente/usuarios"' in texto
    assert 'js/copiar_credenciales.js' in texto


def test_pantalla_de_registro_prepara_navegacion_segura(
    client, db, login, usuario_bibliotecario, carrera
):
    login('test_bibliotecario', 'ClaveSegura123')
    texto = client.post(
        '/bibliotecario/estudiantes/nuevo',
        data=_datos_estudiante(carrera_id=str(carrera.id)),
    ).get_data(as_text=True)

    estudiante = Estudiante.query.filter_by(cedula='1710034065').first()
    assert f'data-url-segura="/bibliotecario/estudiantes?nuevo={estudiante.id}"' in texto
    assert 'js/copiar_credenciales.js' in texto


def test_el_js_compartido_hace_replacestate():
    """El JS de credenciales debe sustituir la entrada del POST en el historial."""
    from pathlib import Path
    js = Path('app/static/js/copiar_credenciales.js').read_text(encoding='utf-8')
    assert 'replaceState' in js
    assert 'data-credenciales' in js


def test_generador_de_claves_es_seguro_y_sin_caracteres_ambiguos():
    claves = {generar_password_temporal() for _ in range(50)}
    assert len(claves) == 50, 'las claves temporales no deben repetirse'
    for clave in claves:
        assert len(clave) >= 10
        assert all(caracter in ALFABETO_TEMPORAL for caracter in clave)
        assert not set(clave) & set('0O1lI')


# ------------------------------------------- cambio obligatorio de password

def test_no_puede_reutilizar_la_misma_contrasena_actual(client, db, gerente_logueado, crear_usuario, login):
    objetivo = crear_usuario('reutiliza')
    respuesta = client.post(f'/gerente/usuarios/{objetivo.id}/restablecer-password')
    temporal = _extraer_password_temporal(respuesta.get_data(as_text=True))

    client.get('/logout')
    login('reutiliza', temporal)

    intento = client.post('/cambiar-password', data={
        'password_actual': temporal,
        'password_nueva': temporal,
        'password_confirmar': temporal,
    })
    assert 'debe ser distinta de la actual' in intento.get_data(as_text=True)

    db.session.expire_all()
    assert db.session.get(Usuario, objetivo.id).debe_cambiar_password is True

    # Con una contraseña realmente nueva si funciona.
    correcto = client.post('/cambiar-password', data={
        'password_actual': temporal,
        'password_nueva': 'ClaveNuevaSegura9',
        'password_confirmar': 'ClaveNuevaSegura9',
    }, follow_redirects=True)
    assert 'actualizada correctamente' in correcto.get_data(as_text=True)

    db.session.expire_all()
    assert db.session.get(Usuario, objetivo.id).debe_cambiar_password is False


# --------------------------------------------------------------- roles

def test_cuenta_de_estudiante_no_puede_cambiar_de_rol(
    client, db, gerente_logueado, crear_estudiante_con_cuenta
):
    usuario, _ = crear_estudiante_con_cuenta('0944444444')

    respuesta = client.post(
        f'/gerente/usuarios/{usuario.id}/rol', data={'rol': 'gerente'}, follow_redirects=True
    )
    assert 'ficha de estudiante asociada' in respuesta.get_data(as_text=True)

    db.session.expire_all()
    assert db.session.get(Usuario, usuario.id).rol == 'estudiante'


def test_bibliotecario_puede_pasar_a_gerente_y_volver(client, db, gerente_logueado, crear_usuario):
    objetivo = crear_usuario('promovible', rol='bibliotecario')

    respuesta = client.post(
        f'/gerente/usuarios/{objetivo.id}/rol', data={'rol': 'gerente'}, follow_redirects=True
    )
    assert 'ahora tiene el rol gerente' in respuesta.get_data(as_text=True)
    db.session.expire_all()
    assert db.session.get(Usuario, objetivo.id).rol == 'gerente'

    respuesta = client.post(
        f'/gerente/usuarios/{objetivo.id}/rol', data={'rol': 'bibliotecario'}, follow_redirects=True
    )
    assert 'ahora tiene el rol bibliotecario' in respuesta.get_data(as_text=True)
    db.session.expire_all()
    assert db.session.get(Usuario, objetivo.id).rol == 'bibliotecario'


def test_enviar_dos_veces_el_mismo_rol_no_lo_alterna(client, db, gerente_logueado, crear_usuario):
    """El POST lleva el rol destino explicito: repetirlo no lo devuelve al anterior."""
    objetivo = crear_usuario('rol_idempotente', rol='bibliotecario')

    primera = client.post(f'/gerente/usuarios/{objetivo.id}/rol',
                          data={'rol': 'gerente'}, follow_redirects=True)
    assert 'ahora tiene el rol gerente' in primera.get_data(as_text=True)

    segunda = client.post(f'/gerente/usuarios/{objetivo.id}/rol',
                          data={'rol': 'gerente'}, follow_redirects=True)
    assert 'ya tiene el rol gerente' in segunda.get_data(as_text=True)

    db.session.expire_all()
    assert db.session.get(Usuario, objetivo.id).rol == 'gerente'


def test_gerente_no_puede_quitarse_su_propio_rol(client, db, gerente_logueado, crear_usuario):
    # Hay otro gerente activo, asi que la unica barrera es la de "uno mismo".
    crear_usuario('gerente_extra', rol='gerente')

    respuesta = client.post(
        f'/gerente/usuarios/{gerente_logueado.id}/rol',
        data={'rol': 'bibliotecario'}, follow_redirects=True,
    )
    assert 'No puedes quitarte a ti mismo el rol de gerente' in respuesta.get_data(as_text=True)

    db.session.expire_all()
    assert db.session.get(Usuario, gerente_logueado.id).rol == 'gerente'


def test_no_se_acepta_un_rol_fuera_de_la_lista_blanca(client, db, gerente_logueado, crear_usuario):
    objetivo = crear_usuario('rol_invalido')

    respuesta = client.post(
        f'/gerente/usuarios/{objetivo.id}/rol', data={'rol': 'superadmin'}, follow_redirects=True
    )
    assert 'Solo se puede alternar' in respuesta.get_data(as_text=True)

    db.session.expire_all()
    assert db.session.get(Usuario, objetivo.id).rol == 'bibliotecario'


def test_no_se_puede_quitar_el_rol_al_ultimo_gerente_activo(client, db, login, crear_usuario):
    gerente_a = crear_usuario('gerente_unico_a', rol='gerente', password='ClaveSegura123')
    gerente_b = crear_usuario('gerente_unico_b', rol='gerente', password='ClaveSegura123')

    login('gerente_unico_a', 'ClaveSegura123')
    # Quitar el rol a B se permite: A sigue siendo gerente activo.
    client.post(f'/gerente/usuarios/{gerente_b.id}/rol',
                data={'rol': 'bibliotecario'}, follow_redirects=True)
    db.session.expire_all()
    assert db.session.get(Usuario, gerente_b.id).rol == 'bibliotecario'

    # A es ahora el unico gerente activo y no puede quitarse el rol.
    respuesta = client.post(f'/gerente/usuarios/{gerente_a.id}/rol',
                            data={'rol': 'bibliotecario'}, follow_redirects=True)
    assert 'No puedes quitarte a ti mismo el rol de gerente' in respuesta.get_data(as_text=True)
    db.session.expire_all()
    assert db.session.get(Usuario, gerente_a.id).rol == 'gerente'


# ------------------------------------------- credenciales al registrar

def test_registro_de_estudiante_crea_usuario_y_muestra_credenciales(
    client, db, login, usuario_bibliotecario, carrera
):
    login('test_bibliotecario', 'ClaveSegura123')

    respuesta = client.post(
        '/bibliotecario/estudiantes/nuevo',
        data=_datos_estudiante(carrera_id=str(carrera.id)),
    )
    assert respuesta.status_code == 200
    texto = respuesta.get_data(as_text=True)

    assert 'Estudiante registrado correctamente' in texto
    assert '1710034065' in texto
    assert 'Copiar credenciales' in texto
    assert 'una sola vez' in texto

    estudiante = Estudiante.query.filter_by(cedula='1710034065').first()
    assert estudiante is not None
    usuario = db.session.get(Usuario, estudiante.usuario_id)
    assert usuario.username == '1710034065'
    assert usuario.rol == 'estudiante'
    assert usuario.debe_cambiar_password is True

    # La clave mostrada es la que quedo hasheada, y no se guardo en claro.
    temporal = _extraer_password_temporal(texto)
    assert check_password_hash(usuario.password_hash, temporal)
    assert temporal not in usuario.password_hash

    # El enlace al listado conserva el marcado del registro nuevo.
    assert f'nuevo={estudiante.id}' in texto


def test_credenciales_del_registro_sirven_para_iniciar_sesion(
    client, db, login, usuario_bibliotecario, carrera
):
    login('test_bibliotecario', 'ClaveSegura123')
    respuesta = client.post(
        '/bibliotecario/estudiantes/nuevo',
        data=_datos_estudiante(carrera_id=str(carrera.id)),
    )
    temporal = _extraer_password_temporal(respuesta.get_data(as_text=True))

    client.get('/logout')
    acceso = login('1710034065', temporal)
    assert acceso.status_code == 302

    forzado = client.get('/estudiante/catalogo')
    assert forzado.status_code == 302
    assert '/cambiar-password' in forzado.headers['Location']
