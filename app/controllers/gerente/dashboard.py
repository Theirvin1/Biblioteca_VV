from datetime import date

from flask import render_template
from flask_login import login_required
from sqlalchemy import text

from app.controllers.decoradores import requiere_rol
from app.controllers.gerente import gerente_bp
from app.extensions import db
from app.models import Devolucion, Ejemplar, Estudiante, Libro, Prestamo


def _prestamos_por_estado():
    """Conteo real por estado, para el donut del dashboard."""
    conteos = dict(
        db.session.query(Prestamo.estado, db.func.count(Prestamo.id))
        .group_by(Prestamo.estado)
        .all()
    )
    return {
        'activo': conteos.get('activo', 0),
        'vencido': conteos.get('vencido', 0),
        'devuelto': conteos.get('devuelto', 0),
    }


def _libros_mas_prestados(limite=10):
    """Top de libros por cantidad de prestamos historicos."""
    return (
        db.session.query(Libro.titulo, db.func.count(Prestamo.id).label('total'))
        .join(Ejemplar, Ejemplar.libro_id == Libro.id)
        .join(Prestamo, Prestamo.ejemplar_id == Ejemplar.id)
        .group_by(Libro.id, Libro.titulo)
        .order_by(db.desc('total'))
        .limit(limite)
        .all()
    )


def _prestamos_por_mes(meses=6):
    """Prestamos registrados por mes, los ultimos `meses` (incluye el actual)."""
    hoy = date.today()
    mes, anio = hoy.month - (meses - 1), hoy.year
    while mes <= 0:
        mes += 12
        anio -= 1
    desde = date(anio, mes, 1)

    filas = (
        db.session.query(
            db.func.to_char(Prestamo.fecha_prestamo, 'YYYY-MM').label('periodo'),
            db.func.count(Prestamo.id),
        )
        .filter(Prestamo.fecha_prestamo >= desde)
        .group_by('periodo')
        .order_by('periodo')
        .all()
    )
    return dict(filas)


def _top_deudores(limite=5):
    """Estudiantes con mayor monto de multa pendiente (no pagada)."""
    return (
        db.session.query(
            (Estudiante.nombres + ' ' + Estudiante.apellidos).label('nombre'),
            db.func.sum(Devolucion.multa_generada).label('monto'),
        )
        .join(Prestamo, Prestamo.id == Devolucion.prestamo_id)
        .join(Estudiante, Estudiante.id == Prestamo.estudiante_id)
        .filter(Devolucion.multa_generada > 0, Devolucion.multa_pagada.is_(False))
        .group_by(Estudiante.id, Estudiante.nombres, Estudiante.apellidos)
        .order_by(db.desc('monto'))
        .limit(limite)
        .all()
    )


@gerente_bp.route('/dashboard')
@login_required
@requiere_rol('gerente')
def dashboard():
    fila = db.session.execute(text('SELECT * FROM obtener_indicadores_dashboard()')).fetchone()

    indicadores = {
        'total_libros': fila.total_libros if fila else 0,
        'prestamos_activos': fila.prestamos_activos if fila else 0,
        'devoluciones_con_multa': fila.devoluciones_con_multa if fila else 0,
        'estudiantes_con_vencidos': fila.estudiantes_con_vencidos if fila else 0,
        'prestamos_vencidos': Prestamo.query.filter_by(estado='vencido').count(),
        'libros_disponibles': Libro.query.filter(
            Libro.activo.is_(True), Libro.stock_disponible > 0
        ).count(),
        'multas_pendientes': db.session.query(
            db.func.coalesce(db.func.sum(Devolucion.multa_generada), 0)
        ).filter(Devolucion.multa_generada > 0, Devolucion.multa_pagada.is_(False)).scalar(),
    }

    por_mes = _prestamos_por_mes()
    top_libros = _libros_mas_prestados()
    top_deudores = _top_deudores()

    graficos = {
        'prestamos_estado': _prestamos_por_estado(),
        'libros_mas_prestados': {
            'labels': [titulo for titulo, _ in top_libros],
            'valores': [total for _, total in top_libros],
        },
        'prestamos_por_mes': {
            'labels': list(por_mes.keys()),
            'valores': list(por_mes.values()),
        },
        'top_deudores': {
            'labels': [nombre for nombre, _ in top_deudores],
            'valores': [float(monto) for _, monto in top_deudores],
        },
    }

    return render_template('gerente/dashboard.html', indicadores=indicadores, graficos=graficos)
