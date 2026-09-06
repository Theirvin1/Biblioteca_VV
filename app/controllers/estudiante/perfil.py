"""
Perfil del estudiante autenticado.

Politica de edicion de este modulo: el estudiante SOLO puede tocar su propio
telefono (ver editar_telefono). Cedula, nombres, apellidos, carrera, correo,
estado y rol son de solo lectura aqui; el bibliotecario los corrige desde
bibliotecario/estudiantes.py y el gerente administra Usuario (estado, rol,
password) desde gerente/usuarios.py. Ningun endpoint de este archivo toca
esas dos cosas.
"""
from datetime import date

from flask import redirect, render_template, url_for, flash
from flask_login import login_required, current_user

from app.controllers.decoradores import requiere_rol
from app.controllers.estudiante import estudiante_bp
from app.extensions import db
from app.forms import TelefonoForm
from app.models import Prestamo
from app.presentacion import calcular_edad, iniciales


def _estadisticas_prestamos(estudiante_id, hoy=None):
    """
    (activos, devueltos, vencidos) del estudiante, EN TIEMPO REAL.

    "Vencido" no se lee aqui de Prestamo.estado: esa columna solo cambia
    cuando corre el job periodico (ver app/scheduler.py), asi que un prestamo
    recien vencido puede seguir marcado 'activo' hasta la proxima corrida.
    Las estadisticas del perfil comparan en cambio `fecha_limite` contra la
    fecha de hoy -- la misma comparacion que ya usan
    resumen_operacion()/paginar_operaciones() en
    app/controllers/bibliotecario/comun.py -- asi siempre reflejan la
    situacion actual sin depender del scheduler. No se toca Prestamo.estado
    ni la logica de prestamos/devoluciones: esto es solo lectura.

    Los tres conteos siguen siendo mutuamente excluyentes:
    - devueltos: estado == 'devuelto'
    - vencidos:  no devuelto y fecha_limite YA paso
    - activos:   no devuelto y fecha_limite todavia NO paso
    """
    hoy = hoy or date.today()

    devueltos = Prestamo.query.filter_by(estudiante_id=estudiante_id, estado='devuelto').count()
    vencidos = Prestamo.query.filter(
        Prestamo.estudiante_id == estudiante_id,
        Prestamo.estado != 'devuelto',
        Prestamo.fecha_limite < hoy,
    ).count()
    activos = Prestamo.query.filter(
        Prestamo.estudiante_id == estudiante_id,
        Prestamo.estado != 'devuelto',
        Prestamo.fecha_limite >= hoy,
    ).count()
    return activos, devueltos, vencidos


def _contexto_perfil(estudiante, form_telefono, abrir_modal_telefono=False):
    activos, devueltos, vencidos = _estadisticas_prestamos(estudiante.id)
    return {
        'estudiante': estudiante,
        'edad': calcular_edad(estudiante.fecha_nacimiento),
        'iniciales_estudiante': iniciales(estudiante.nombres, estudiante.apellidos),
        'prestamos_activos': activos,
        'prestamos_devueltos': devueltos,
        'prestamos_vencidos': vencidos,
        'form_telefono': form_telefono,
        'abrir_modal_telefono': abrir_modal_telefono,
    }


@estudiante_bp.route('/perfil')
@login_required
@requiere_rol('estudiante')
def mi_perfil():
    estudiante = current_user.estudiante
    if estudiante is None:
        flash('Tu cuenta no tiene un perfil de estudiante vinculado. Contacta al bibliotecario.', 'warning')
        return render_template('estudiante/perfil.html', estudiante=None)

    form_telefono = TelefonoForm(telefono=estudiante.telefono)
    return render_template(
        'estudiante/perfil.html', **_contexto_perfil(estudiante, form_telefono)
    )


@estudiante_bp.route('/perfil/telefono', methods=['POST'])
@login_required
@requiere_rol('estudiante')
def editar_telefono():
    """
    Unico dato editable por el estudiante sobre si mismo.

    El estudiante a editar sale SIEMPRE de current_user.estudiante, nunca de
    un id/cedula recibido por POST: no existe forma de que esta ruta toque la
    ficha de otro estudiante. TelefonoForm tampoco lleva mas campos que
    telefono, asi que aunque se manipule el cuerpo del POST no hay cedula,
    nombres, apellidos, carrera, correo, estado ni rol que cambiar por aqui.
    """
    estudiante = current_user.estudiante
    if estudiante is None:
        flash('Tu cuenta no tiene un perfil de estudiante vinculado. Contacta al bibliotecario.', 'warning')
        return redirect(url_for('estudiante.mi_perfil'))

    form = TelefonoForm()
    if form.validate_on_submit():
        # Vacio es valido (telefono es opcional): se guarda como NULL, igual
        # que en el registro/edicion del bibliotecario, y el perfil vuelve a
        # mostrar "No registrado".
        estudiante.telefono = (form.telefono.data or '').strip() or None
        db.session.commit()
        mensaje = (
            'Teléfono actualizado correctamente.' if estudiante.telefono
            else 'Teléfono eliminado correctamente.'
        )
        flash(mensaje, 'success')
        return redirect(url_for('estudiante.mi_perfil'))

    # Formulario invalido: se vuelve a pintar el perfil completo (mismas
    # estadisticas y datos) con los errores, y se marca para que el modal se
    # reabra solo en la carga de esta respuesta.
    return render_template(
        'estudiante/perfil.html',
        **_contexto_perfil(estudiante, form, abrir_modal_telefono=True)
    )
