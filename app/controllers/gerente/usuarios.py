"""
Gestion de usuarios del gerente: listado, activar/desactivar, restablecer
contraseña y cambio de rol restringido.

Sobre la clave temporal: se genera en memoria, se guarda SOLO su hash y se
renderiza directamente en la respuesta del POST. No se guarda en la base de
datos, ni en session, ni en cookies, ni en auditoria: si el gerente pierde
esa pantalla, la unica salida es generar una nueva.
"""
from flask import redirect, render_template, request, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from app.controllers.decoradores import requiere_rol
from app.controllers.gerente import gerente_bp
from app.extensions import db
from app.forms import AccionUsuarioForm, NuevoUsuarioForm
from app.models import Auditoria, Carrera, Estudiante, Usuario
from app.paginacion import (
    POR_PAGINA, argumentos_activos, opcion_filtro, pagina_actual, texto_filtro,
)
from app.seguridad import generar_password_temporal, respuesta_sin_cache

ROLES = ('gerente', 'bibliotecario', 'estudiante')

# El POST indica explicitamente el estado deseado (no es un toggle): asi un
# doble envio accidental es idempotente y no deja la cuenta al reves.
ACCIONES_ESTADO = ('activar', 'desactivar')

# Solo se puede alternar entre estos dos: una cuenta con ficha de Estudiante
# conserva su rol para no dejar relaciones incoherentes (ver _puede_cambiar_rol).
ROLES_INTERCAMBIABLES = ('bibliotecario', 'gerente')


def _registrar_auditoria(usuario_objetivo, operacion, datos_anteriores, datos_nuevos):
    """
    Deja constancia de la accion administrativa. NUNCA recibe la clave
    temporal ni el hash: solo los campos que cambiaron (activo/rol) o una
    marca de que hubo restablecimiento.
    """
    db.session.add(Auditoria(
        tabla_afectada='usuarios',
        operacion=operacion,
        usuario_id=current_user.id,
        datos_anteriores=datos_anteriores,
        datos_nuevos=datos_nuevos,
        ip_address=request.remote_addr,
        modulo='gestion_usuarios',
    ))


def _gerentes_activos_restantes(excluyendo_id):
    """Cuantos gerentes activos quedarian si se excluye a `excluyendo_id`."""
    return Usuario.query.filter(
        Usuario.rol == 'gerente',
        Usuario.activo.is_(True),
        Usuario.id != excluyendo_id,
    ).count()


def _puede_cambiar_rol(usuario):
    """Una cuenta con ficha de Estudiante mantiene siempre rol 'estudiante'."""
    return Estudiante.query.filter_by(usuario_id=usuario.id).first() is None


def _buscar_usuario(usuario_id):
    return db.session.get(Usuario, usuario_id)


@gerente_bp.route('/usuarios')
@login_required
@requiere_rol('gerente')
def listado_usuarios():
    termino = texto_filtro(request, 'q')
    rol = opcion_filtro(request, 'rol', ROLES)
    estado = opcion_filtro(request, 'estado', ('activo', 'inactivo'))

    # LEFT JOIN a estudiantes para poder mostrar/buscar por la persona
    # asociada; las cuentas de bibliotecario/gerente no tienen ficha.
    consulta = db.session.query(Usuario, Estudiante).outerjoin(
        Estudiante, Estudiante.usuario_id == Usuario.id
    )

    if termino:
        patron = f'%{termino}%'
        consulta = consulta.filter(db.or_(
            Usuario.username.ilike(patron),
            Estudiante.cedula.ilike(patron),
            Estudiante.nombres.ilike(patron),
            Estudiante.apellidos.ilike(patron),
            (Estudiante.nombres + ' ' + Estudiante.apellidos).ilike(patron),
        ))
    if rol:
        consulta = consulta.filter(Usuario.rol == rol)
    if estado == 'activo':
        consulta = consulta.filter(Usuario.activo.is_(True))
    elif estado == 'inactivo':
        consulta = consulta.filter(Usuario.activo.is_(False))

    # Mas recientes primero. fecha_creacion tiene server_default now(), que es
    # constante dentro de una transaccion, asi que el id es el desempate fiable.
    paginacion = consulta.order_by(Usuario.id.desc()).paginate(
        page=pagina_actual(request), per_page=POR_PAGINA, error_out=False
    )

    filas = [
        {
            'usuario': usuario,
            'estudiante': estudiante,
            'puede_cambiar_rol': estudiante is None,
            'es_uno_mismo': usuario.id == current_user.id,
        }
        for usuario, estudiante in paginacion.items
    ]

    filtros = {'q': termino, 'rol': rol, 'estado': estado}
    return render_template(
        'gerente/usuarios_lista.html',
        paginacion=paginacion,
        filas=filas,
        form=AccionUsuarioForm(),
        form_crear=NuevoUsuarioForm(),
        carreras=Carrera.query.order_by(Carrera.nombre).all(),
        roles=ROLES,
        roles_intercambiables=ROLES_INTERCAMBIABLES,
        filtros=filtros,
        argumentos=argumentos_activos(**filtros),
    )


@gerente_bp.route('/usuarios/nuevo', methods=['POST'])
@login_required
@requiere_rol('gerente')
def crear_usuario():
    """
    Crea una cuenta desde el modal de gestion de usuarios. Con rol
    'estudiante' exige la ficha completa y usa la cedula como username
    (misma convencion que el registro del bibliotecario); con
    'bibliotecario'/'gerente' solo crea la cuenta.
    La clave temporal se muestra UNA sola vez con la plantilla de
    credenciales, igual que el restablecimiento.
    """
    form = NuevoUsuarioForm()
    form.carrera_id.choices = [(0, '-- Selecciona una carrera --')] + [
        (c.id, f'{c.nombre} ({c.facultad.nombre})')
        for c in Carrera.query.join(Carrera.facultad).order_by(Carrera.nombre).all()
    ]

    if not form.validate_on_submit():
        for campo, errores in form.errors.items():
            for error in errores:
                flash(f'{form[campo].label.text}: {error}', 'danger')
        return redirect(url_for('gerente.listado_usuarios'))

    rol = form.rol.data
    es_estudiante = rol == 'estudiante'
    username = form.cedula.data if es_estudiante else (form.username.data or '').strip()

    if Usuario.query.filter_by(username=username).first():
        flash(f'Ya existe una cuenta con el usuario "{username}".', 'danger')
        return redirect(url_for('gerente.listado_usuarios'))

    estudiante = None
    if es_estudiante:
        correo = (form.correo.data or '').strip()
        if Estudiante.query.filter_by(cedula=form.cedula.data).first():
            flash('Ya existe un estudiante registrado con esa cédula.', 'danger')
            return redirect(url_for('gerente.listado_usuarios'))
        if Estudiante.query.filter_by(correo=correo).first():
            flash('Ya existe un estudiante registrado con ese correo.', 'danger')
            return redirect(url_for('gerente.listado_usuarios'))

    password_temporal = generar_password_temporal()
    usuario = Usuario(
        username=username,
        password_hash=generate_password_hash(password_temporal),
        rol=rol,
        debe_cambiar_password=True,
    )
    db.session.add(usuario)
    db.session.flush()

    if es_estudiante:
        estudiante = Estudiante(
            cedula=form.cedula.data,
            nombres=(form.nombres.data or '').strip(),
            apellidos=(form.apellidos.data or '').strip(),
            correo=(form.correo.data or '').strip(),
            telefono=(form.telefono.data or '').strip() or None,
            carrera_id=form.carrera_id.data,
            fecha_nacimiento=form.fecha_nacimiento.data,
            genero=form.genero.data or None,
            usuario_id=usuario.id,
        )
        db.session.add(estudiante)

    _registrar_auditoria(
        usuario, 'INSERT',
        {},
        {'id': usuario.id, 'username': usuario.username, 'rol': usuario.rol},
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('No se pudo crear el usuario. Verifica los datos ingresados.', 'danger')
        return redirect(url_for('gerente.listado_usuarios'))

    return respuesta_sin_cache(render_template(
        'gerente/usuarios_credenciales.html',
        usuario=usuario,
        estudiante=estudiante,
        password_temporal=password_temporal,
    ))


@gerente_bp.route('/usuarios/<int:usuario_id>/estado', methods=['POST'])
@login_required
@requiere_rol('gerente')
def cambiar_estado_usuario(usuario_id):
    form = AccionUsuarioForm()
    if not form.validate_on_submit():
        flash('No se pudo procesar la solicitud. Intenta nuevamente.', 'danger')
        return redirect(url_for('gerente.listado_usuarios'))

    usuario = _buscar_usuario(usuario_id)
    if usuario is None:
        flash('El usuario indicado no existe.', 'danger')
        return redirect(url_for('gerente.listado_usuarios'))

    accion = (request.form.get('accion') or '').strip()
    if accion not in ACCIONES_ESTADO:
        flash('Acción no válida sobre la cuenta.', 'danger')
        return redirect(url_for('gerente.listado_usuarios'))

    activar = accion == 'activar'

    # Idempotente: si ya esta en el estado pedido no se invierte nada. Un
    # doble POST (F5, doble clic) deja la cuenta como se pidio, no al reves.
    if usuario.activo == activar:
        estado_actual = 'activa' if activar else 'desactivada'
        flash(f'La cuenta "{usuario.username}" ya estaba {estado_actual}.', 'info')
        return redirect(url_for('gerente.listado_usuarios'))

    if not activar:
        if usuario.id == current_user.id:
            flash('No puedes desactivar tu propia cuenta.', 'danger')
            return redirect(url_for('gerente.listado_usuarios'))
        if usuario.rol == 'gerente' and _gerentes_activos_restantes(usuario.id) == 0:
            flash(
                'No se puede desactivar al último gerente activo: el sistema '
                'quedaría sin administrador.',
                'danger'
            )
            return redirect(url_for('gerente.listado_usuarios'))

    estado_anterior = usuario.activo
    usuario.activo = activar
    _registrar_auditoria(
        usuario, 'UPDATE',
        {'id': usuario.id, 'username': usuario.username, 'activo': estado_anterior},
        {'id': usuario.id, 'username': usuario.username, 'activo': activar},
    )
    db.session.commit()

    if activar:
        flash(f'La cuenta "{usuario.username}" fue activada.', 'success')
    else:
        flash(f'La cuenta "{usuario.username}" fue desactivada.', 'success')
    return redirect(url_for('gerente.listado_usuarios'))


@gerente_bp.route('/usuarios/<int:usuario_id>/restablecer-password', methods=['POST'])
@login_required
@requiere_rol('gerente')
def restablecer_password(usuario_id):
    """
    Genera una clave temporal nueva y la muestra UNA sola vez en esta misma
    respuesta. No hay ruta GET equivalente: al recargar o salir de la pantalla
    la clave deja de existir (solo queda su hash en la BD).
    """
    form = AccionUsuarioForm()
    if not form.validate_on_submit():
        flash('No se pudo procesar la solicitud. Intenta nuevamente.', 'danger')
        return redirect(url_for('gerente.listado_usuarios'))

    usuario = _buscar_usuario(usuario_id)
    if usuario is None:
        flash('El usuario indicado no existe.', 'danger')
        return redirect(url_for('gerente.listado_usuarios'))

    password_temporal = generar_password_temporal()
    usuario.password_hash = generate_password_hash(password_temporal)
    usuario.debe_cambiar_password = True
    # Una cuenta bloqueada por intentos fallidos vuelve a poder entrar con la
    # clave nueva; el estado activo/inactivo no se toca aqui.
    usuario.intentos_fallidos = 0
    usuario.bloqueado = False
    usuario.fecha_bloqueo = None

    # La auditoria registra QUE hubo restablecimiento, nunca la clave ni el hash.
    _registrar_auditoria(
        usuario, 'UPDATE',
        {'id': usuario.id, 'username': usuario.username},
        {'id': usuario.id, 'username': usuario.username, 'password_restablecido': True},
    )
    db.session.commit()

    estudiante = Estudiante.query.filter_by(usuario_id=usuario.id).first()
    # no-store: la clave se muestra en esta respuesta pero ningun cache debe
    # guardarla. El JS de la pantalla reemplaza la URL del POST por el listado
    # (GET) para que un F5 posterior no genere otra clave.
    return respuesta_sin_cache(render_template(
        'gerente/usuarios_credenciales.html',
        usuario=usuario,
        estudiante=estudiante,
        password_temporal=password_temporal,
    ))


@gerente_bp.route('/usuarios/<int:usuario_id>/rol', methods=['POST'])
@login_required
@requiere_rol('gerente')
def cambiar_rol_usuario(usuario_id):
    form = AccionUsuarioForm()
    if not form.validate_on_submit():
        flash('No se pudo procesar la solicitud. Intenta nuevamente.', 'danger')
        return redirect(url_for('gerente.listado_usuarios'))

    usuario = _buscar_usuario(usuario_id)
    if usuario is None:
        flash('El usuario indicado no existe.', 'danger')
        return redirect(url_for('gerente.listado_usuarios'))

    nuevo_rol = (request.form.get('rol') or '').strip()
    if nuevo_rol not in ROLES_INTERCAMBIABLES:
        flash('Solo se puede alternar entre los roles bibliotecario y gerente.', 'danger')
        return redirect(url_for('gerente.listado_usuarios'))

    if not _puede_cambiar_rol(usuario):
        flash(
            'Esta cuenta tiene una ficha de estudiante asociada: debe conservar '
            'el rol estudiante.',
            'danger'
        )
        return redirect(url_for('gerente.listado_usuarios'))

    if usuario.id == current_user.id and nuevo_rol != 'gerente':
        flash('No puedes quitarte a ti mismo el rol de gerente.', 'danger')
        return redirect(url_for('gerente.listado_usuarios'))

    if (usuario.rol == 'gerente' and nuevo_rol != 'gerente'
            and usuario.activo and _gerentes_activos_restantes(usuario.id) == 0):
        flash(
            'No se puede quitar el rol al último gerente activo: el sistema '
            'quedaría sin administrador.',
            'danger'
        )
        return redirect(url_for('gerente.listado_usuarios'))

    if usuario.rol == nuevo_rol:
        flash(f'La cuenta "{usuario.username}" ya tiene el rol {nuevo_rol}.', 'info')
        return redirect(url_for('gerente.listado_usuarios'))

    rol_anterior = usuario.rol
    usuario.rol = nuevo_rol
    _registrar_auditoria(
        usuario, 'UPDATE',
        {'id': usuario.id, 'username': usuario.username, 'rol': rol_anterior},
        {'id': usuario.id, 'username': usuario.username, 'rol': nuevo_rol},
    )
    db.session.commit()

    flash(f'La cuenta "{usuario.username}" ahora tiene el rol {nuevo_rol}.', 'success')
    return redirect(url_for('gerente.listado_usuarios'))
