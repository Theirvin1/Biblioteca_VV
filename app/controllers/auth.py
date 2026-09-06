from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.forms import LoginForm, CambiarPasswordForm
from app.models import Usuario, Sesion

auth_bp = Blueprint('auth', __name__)

MAX_INTENTOS_FALLIDOS = 5
TIEMPO_BLOQUEO_MINUTOS = 5


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(_ruta_inicio_por_rol(current_user.rol)))

    form = LoginForm()

    if form.validate_on_submit():
        usuario = Usuario.query.filter_by(username=form.username.data).first()

        if usuario is None:
            flash('Usuario o contraseña incorrectos', 'danger')
            return render_template('auth/login.html', form=form)

        # `and usuario.fecha_bloqueo`: una fila con bloqueado=TRUE pero sin
        # fecha_bloqueo (edicion manual de la BD, restauracion parcial) hacia
        # reventar la resta con TypeError -> error 500 en el login. Sin fecha
        # no se puede saber cuando expira el bloqueo, asi que se trata como no
        # bloqueada y el flujo sigue normal (contraseña, activo, etc.).
        if usuario.bloqueado and usuario.fecha_bloqueo:
            tiempo_transcurrido = datetime.utcnow() - usuario.fecha_bloqueo
            if tiempo_transcurrido.total_seconds() < TIEMPO_BLOQUEO_MINUTOS * 60:
                minutos_restantes = TIEMPO_BLOQUEO_MINUTOS - int(tiempo_transcurrido.total_seconds() / 60)
                flash(f'Cuenta suspendida temporalmente. Intente de nuevo en {minutos_restantes} minutos.', 'danger')
                return render_template('auth/login.html', form=form)
            else:
                usuario.bloqueado = False
                usuario.intentos_fallidos = 0
                usuario.fecha_bloqueo = None
                db.session.commit()

        if not usuario.activo:
            flash('Esta cuenta está desactivada', 'danger')
            return render_template('auth/login.html', form=form)

        if not check_password_hash(usuario.password_hash, form.password.data):
            usuario.intentos_fallidos = (usuario.intentos_fallidos or 0) + 1

            if usuario.intentos_fallidos >= MAX_INTENTOS_FALLIDOS:
                usuario.bloqueado = True
                usuario.fecha_bloqueo = datetime.utcnow()
                flash(f'Cuenta suspendida. Inténtalo nuevamente en {TIEMPO_BLOQUEO_MINUTOS} minutos.', 'warning')
            else:
                intentos_restantes = MAX_INTENTOS_FALLIDOS - usuario.intentos_fallidos
                flash('Usuario o contraseña incorrectos', 'danger')

            db.session.commit()
            _registrar_sesion(usuario.id, resultado='fallido', motivo_cierre=None)
            return render_template('auth/login.html', form=form)

        # Login exitoso
        usuario.intentos_fallidos = 0
        usuario.ultimo_acceso = datetime.utcnow()
        db.session.commit()

        login_user(usuario)
        _registrar_sesion(usuario.id, resultado='exitoso', motivo_cierre=None)

        return redirect(url_for(_ruta_inicio_por_rol(usuario.rol)))

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    _cerrar_sesion_activa(current_user.id, motivo='logout')
    logout_user()
    flash('Sesión cerrada correctamente', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/cambiar-password', methods=['GET', 'POST'])
@login_required
def cambiar_password():
    form = CambiarPasswordForm()

    if form.validate_on_submit():
        if not check_password_hash(current_user.password_hash, form.password_actual.data):
            flash('La contraseña actual no es correcta.', 'danger')
            return render_template('auth/cambiar_password.html', form=form)

        # Impide "cambiar" la clave dejando la misma (util sobre todo cuando la
        # actual es una clave temporal que debe dejar de usarse).
        if check_password_hash(current_user.password_hash, form.password_nueva.data):
            flash('La nueva contraseña debe ser distinta de la actual.', 'danger')
            return render_template('auth/cambiar_password.html', form=form)

        current_user.password_hash = generate_password_hash(form.password_nueva.data)
        current_user.debe_cambiar_password = False
        db.session.commit()

        flash('Contraseña actualizada correctamente.', 'success')
        return redirect(url_for(_ruta_inicio_por_rol(current_user.rol)))

    return render_template('auth/cambiar_password.html', form=form)


@auth_bp.before_app_request
def _revisar_sesion_activa():
    """
    Expulsa en CADA peticion a quien fue desactivado despues de iniciar sesion.

    El login ya rechaza cuentas inactivas, pero una sesion abierta seguia
    navegando hasta cerrar sesion. Se ejecuta antes que el hook de cambio de
    contraseña para que un usuario inactivo no quede atrapado en un bucle
    hacia /cambiar-password.
    """
    if not current_user.is_authenticated:
        return None
    if current_user.activo:
        return None

    # `static` se deja pasar para no romper el CSS/JS de la propia pantalla
    # de login a la que se redirige.
    if request.endpoint == 'static':
        return None

    # 'forzado' es uno de los motivos permitidos por chk_sesiones_motivo_cierre
    # ('logout', 'expiracion', 'forzado'): el cierre lo provoca el administrador.
    _cerrar_sesion_activa(current_user.id, motivo='forzado')
    logout_user()
    flash('Tu cuenta fue desactivada. Contacta al administrador.', 'warning')
    return redirect(url_for('auth.login'))


@auth_bp.before_app_request
def _exigir_cambio_password():
    if not current_user.is_authenticated:
        return None
    if not current_user.debe_cambiar_password:
        return None

    endpoints_permitidos = {'auth.cambiar_password', 'auth.logout', 'static'}
    if request.endpoint in endpoints_permitidos:
        return None

    return redirect(url_for('auth.cambiar_password'))


def _ruta_inicio_por_rol(rol):
    rutas = {
        'bibliotecario': 'bibliotecario.inicio',
        'estudiante': 'estudiante.listado_catalogo',
        'gerente': 'gerente.dashboard',
    }
    return rutas.get(rol, 'auth.login')


def _registrar_sesion(usuario_id, resultado, motivo_cierre):
    sesion = Sesion(
        usuario_id=usuario_id,
        ip_address=request.remote_addr,
        dispositivo=request.user_agent.string,
        resultado=resultado,
        motivo_cierre=motivo_cierre
    )
    db.session.add(sesion)
    db.session.commit()


def _cerrar_sesion_activa(usuario_id, motivo):
    sesion = Sesion.query.filter_by(
        usuario_id=usuario_id, fecha_fin=None
    ).order_by(Sesion.fecha_inicio.desc()).first()

    if sesion:
        sesion.fecha_fin = datetime.utcnow()
        sesion.motivo_cierre = motivo
        db.session.commit()