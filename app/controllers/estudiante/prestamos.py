from datetime import date

from flask import render_template, request, flash
from flask_login import login_required, current_user

from app.controllers.decoradores import requiere_rol
from app.controllers.estudiante import estudiante_bp
from app.models import Devolucion, Prestamo
from app.paginacion import POR_PAGINA, argumentos_activos, opcion_filtro, pagina_actual


@estudiante_bp.route('/prestamos')
@login_required
@requiere_rol('estudiante')
def mis_prestamos():
    estudiante = current_user.estudiante
    if estudiante is None:
        flash('Tu cuenta no tiene un perfil de estudiante vinculado. Contacta al bibliotecario.', 'warning')
        return render_template(
            'estudiante/prestamos.html',
            prestamos_activos=[], historial=[], paginacion_historial=None,
            filtros={'retraso': ''}, argumentos={}, hoy=date.today(),
        )

    # Los activos/vencidos estan acotados por el cupo del estudiante
    # (max_prestamos_activos): no hace falta paginarlos.
    # Se ordena por id (no por fecha_prestamo): varios prestamos de una misma
    # operacion (prestamo multiple) comparten el mismo now() de la transaccion,
    # asi que fecha_prestamo no alcanza para distinguir "el mas reciente".
    prestamos_activos = (
        Prestamo.query.filter(Prestamo.estudiante_id == estudiante.id, Prestamo.estado != 'devuelto')
        .order_by(Prestamo.id.desc())
        .all()
    )

    # El historial (devueltos) si puede crecer indefinidamente: se pagina.
    filtro_retraso = opcion_filtro(request, 'retraso', ('atiempo', 'retraso'))

    consulta_historial = (
        Prestamo.query.join(Devolucion, Devolucion.prestamo_id == Prestamo.id)
        .filter(Prestamo.estudiante_id == estudiante.id, Prestamo.estado == 'devuelto')
    )
    if filtro_retraso == 'atiempo':
        consulta_historial = consulta_historial.filter(Devolucion.dias_retraso == 0)
    elif filtro_retraso == 'retraso':
        consulta_historial = consulta_historial.filter(Devolucion.dias_retraso > 0)

    # Recientes primero (por id, mismo motivo que arriba).
    paginacion_historial = consulta_historial.order_by(Prestamo.id.desc()).paginate(
        page=pagina_actual(request), per_page=POR_PAGINA, error_out=False
    )

    return render_template(
        'estudiante/prestamos.html',
        prestamos_activos=prestamos_activos,
        historial=paginacion_historial.items,
        paginacion_historial=paginacion_historial,
        filtros={'retraso': filtro_retraso},
        argumentos=argumentos_activos(retraso=filtro_retraso),
        hoy=date.today(),
    )
