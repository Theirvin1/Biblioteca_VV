"""
Devoluciones del bibliotecario.

Una operacion de prestamo (uno o varios libros) se puede devolver COMPLETA o
PARCIALMENTE: se eligen los libros a devolver y cada uno lleva su propio
estado (bueno / dañado / perdido) y su observacion. El estado de la operacion
("parcial" / "completa") NO se guarda en BD: se deriva contando cuantos
prestamos del grupo ya estan en estado 'devuelto' (ver comun.resumen_operacion).

Las reglas de multa, daños/perdidas e inventario son las mismas de siempre:
viven en `_registrar_devolucion_prestamo`, que usan tanto la devolucion
individual (ruta historica) como la devolucion por operacion.
"""
from datetime import date
from decimal import Decimal

from flask import redirect, render_template, request, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import text

from app.controllers.bibliotecario import bibliotecario_bp
from app.controllers.bibliotecario.comun import (
    ESTADOS_PENDIENTES, paginar_operaciones, prestamos_de_operacion, resumen_operacion,
)
from app.controllers.decoradores import requiere_rol
from app.extensions import db
from app.forms import DevolucionForm, DevolucionLoteForm
from app.models import DanioPerdida, Devolucion, HistorialInventario, Prestamo
from app.paginacion import (
    POR_PAGINA, argumentos_activos, opcion_filtro, pagina_actual, texto_filtro,
)

ESTADOS_EJEMPLAR = ('bueno', 'dañado', 'perdido')

# Mismo tope que DevolucionForm.observaciones (Length(max=500)). Los campos
# por libro de esta pantalla son dinamicos y se leen de request.form, asi que
# no pasan por WTForms: el maxlength del HTML es solo ayuda visual y este es
# el limite que de verdad se aplica. Se rechaza (no se recorta) para que el
# bibliotecario vea que su texto no se guardo completo, igual que en el
# formulario de devolucion individual.
LARGO_MAXIMO_OBSERVACION = 500


def _registrar_devolucion_prestamo(prestamo, estado_ejemplar, observaciones):
    """
    Registra la devolucion de UN prestamo dentro de la transaccion en curso.

    No hace commit: quien llama decide cuando confirmar (asi un lote de varios
    libros se guarda entero o no se guarda nada). Devuelve la Devolucion creada.
    """
    multa = db.session.execute(
        text('SELECT calcular_multa(:prestamo_id)'), {'prestamo_id': prestamo.id}
    ).scalar() or Decimal('0')

    dias_retraso = max((date.today() - prestamo.fecha_limite).days, 0)

    devolucion = Devolucion(
        prestamo_id=prestamo.id,
        bibliotecario_id=current_user.id,
        estado_ejemplar=estado_ejemplar,
        dias_retraso=dias_retraso,
        multa_generada=multa,
        observaciones=observaciones,
    )
    db.session.add(devolucion)
    db.session.flush()  # dispara los triggers de BD (stock, ejemplar, préstamo, auditoría)

    # El trigger de devoluciones siempre deja el ejemplar como "disponible";
    # si se reporta dañado o perdido, corregimos su estado y el stock aquí
    # y dejamos constancia en danios_perdidas.
    if estado_ejemplar in ('dañado', 'perdido'):
        ejemplar = prestamo.ejemplar
        libro = ejemplar.libro
        # Releemos el libro: el trigger acaba de sumar 1 al stock por SQL y el
        # objeto en memoria podria tener el valor anterior (importante cuando
        # se devuelven varios libros seguidos en la misma transaccion).
        db.session.refresh(libro)
        estado_final = 'baja' if estado_ejemplar == 'perdido' else 'dañado'

        db.session.add(DanioPerdida(
            devolucion_id=devolucion.id,
            tipo='perdida' if estado_ejemplar == 'perdido' else 'danio',
            descripcion=observaciones or f'Ejemplar reportado como {estado_ejemplar} al devolver.',
            reportado_por=current_user.id,
        ))

        ejemplar.estado = estado_final
        libro.stock_disponible -= 1
        if estado_ejemplar == 'perdido':
            libro.stock_total -= 1

        db.session.add(HistorialInventario(
            ejemplar_id=ejemplar.id,
            tipo_movimiento='baja' if estado_ejemplar == 'perdido' else 'danio',
            estado_anterior='disponible',
            estado_nuevo=estado_final,
            usuario_id=current_user.id,
            prestamo_id=prestamo.id,
            observaciones=observaciones,
        ))

    return devolucion


@bibliotecario_bp.route('/devoluciones')
@login_required
@requiere_rol('bibliotecario')
def listado_devoluciones():
    """
    Pendientes / Completadas / Todas.

    Una operacion completamente devuelta ya no tiene libros pendientes, pero
    sigue siendo consultable desde la pestaña "Completadas": no se pierde de
    vista, solo deja de estorbar en el trabajo del dia.
    """
    termino = texto_filtro(request, 'q')
    estado = opcion_filtro(
        request, 'estado', ('pendientes', 'completadas', 'todas'), por_defecto='pendientes'
    )

    paginacion, operaciones = paginar_operaciones(
        termino=termino,
        estado=estado,
        page=pagina_actual(request),
        per_page=POR_PAGINA,
    )

    return render_template(
        'bibliotecario/devoluciones_lista.html',
        paginacion=paginacion,
        operaciones=operaciones,
        filtros={'q': termino, 'estado': estado},
        argumentos=argumentos_activos(q=termino, estado=estado),
        hoy=date.today(),
    )


@bibliotecario_bp.route('/devoluciones/operacion/<int:prestamo_id>', methods=['GET', 'POST'])
@login_required
@requiere_rol('bibliotecario')
def devolucion_operacion(prestamo_id):
    """Devolucion parcial o total de una operacion (funciona igual con 1 libro)."""
    prestamo = db.session.get(Prestamo, prestamo_id)
    if prestamo is None:
        flash('El préstamo indicado no existe.', 'danger')
        return redirect(url_for('bibliotecario.listado_devoluciones'))

    operacion = resumen_operacion(prestamos_de_operacion(prestamo))
    form = DevolucionLoteForm()

    def _pantalla():
        return render_template(
            'bibliotecario/devolucion_operacion.html',
            form=form, operacion=operacion, hoy=date.today(),
        )

    if operacion['pendientes'] == 0:
        flash('Todos los libros de esta operación ya fueron devueltos.', 'info')
        return redirect(url_for('bibliotecario.listado_devoluciones'))

    if form.validate_on_submit():
        seleccionados = request.form.getlist('prestamos')
        pendientes = {str(p.id): p for p in operacion['prestamos'] if p.estado != 'devuelto'}

        ids = [pid for pid in seleccionados if pid in pendientes]
        if not ids:
            flash('Selecciona al menos un libro para registrar la devolución.', 'danger')
            return _pantalla()

        total_multa = Decimal('0')
        try:
            for pid in ids:
                pendiente = pendientes[pid]
                estado_ejemplar = (request.form.get(f'estado_{pid}') or 'bueno').strip()
                if estado_ejemplar not in ESTADOS_EJEMPLAR:
                    raise ValueError(f'Estado del ejemplar no válido para {pendiente.codigo_prestamo}.')

                observaciones = (request.form.get(f'observacion_{pid}') or '').strip()
                if len(observaciones) > LARGO_MAXIMO_OBSERVACION:
                    raise ValueError(
                        f'La observación de {pendiente.codigo_prestamo} no puede superar '
                        f'los {LARGO_MAXIMO_OBSERVACION} caracteres.'
                    )

                devolucion = _registrar_devolucion_prestamo(
                    pendiente, estado_ejemplar, observaciones or None
                )
                total_multa += Decimal(devolucion.multa_generada or 0)

            db.session.commit()
        except ValueError as error:
            db.session.rollback()
            flash(str(error), 'danger')
            return _pantalla()
        except Exception:
            db.session.rollback()
            flash('No se pudo registrar la devolución. No se guardó ningún libro.', 'danger')
            return _pantalla()

        restantes = operacion['pendientes'] - len(ids)
        if restantes > 0:
            mensaje = (
                f'Devolución parcial registrada: {len(ids)} libro(s) devuelto(s), '
                f'{restantes} pendiente(s).'
            )
            categoria = 'warning'
        else:
            mensaje = f'Devolución completada: {len(ids)} libro(s) devuelto(s).'
            categoria = 'success'

        if total_multa > 0:
            mensaje += f' Multa generada: ${total_multa}.'
            categoria = 'warning'

        flash(mensaje, categoria)
        return redirect(url_for('bibliotecario.listado_devoluciones'))

    return _pantalla()


@bibliotecario_bp.route('/devoluciones/registrar/<int:prestamo_id>', methods=['GET', 'POST'])
@login_required
@requiere_rol('bibliotecario')
def registrar_devolucion(prestamo_id):
    """Devolucion individual (ruta historica). Se conserva para no romper enlaces."""
    prestamo = Prestamo.query.filter(
        Prestamo.id == prestamo_id, Prestamo.estado.in_(ESTADOS_PENDIENTES)
    ).first()
    if prestamo is None:
        flash('El préstamo indicado no existe o ya fue devuelto.', 'danger')
        return redirect(url_for('bibliotecario.listado_devoluciones'))

    form = DevolucionForm()

    if form.validate_on_submit():
        observaciones = (form.observaciones.data or '').strip() or None
        try:
            devolucion = _registrar_devolucion_prestamo(
                prestamo, form.estado_ejemplar.data, observaciones
            )
            multa = devolucion.multa_generada
            dias_retraso = devolucion.dias_retraso
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash('No se pudo registrar la devolución. Intenta nuevamente.', 'danger')
            return render_template('bibliotecario/devolucion_form.html', form=form, prestamo=prestamo)

        if multa and multa > 0:
            flash(
                f'Devolución registrada. Días de retraso: {dias_retraso}. Multa generada: ${multa}.',
                'warning'
            )
        else:
            flash('Devolución registrada correctamente, sin multa.', 'success')

        return redirect(url_for('bibliotecario.listado_devoluciones'))

    return render_template('bibliotecario/devolucion_form.html', form=form, prestamo=prestamo)
