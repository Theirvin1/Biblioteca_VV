from datetime import date

from flask import render_template
from flask_login import login_required
from sqlalchemy import text

from app.controllers.bibliotecario import bibliotecario_bp
from app.controllers.decoradores import requiere_rol
from app.extensions import db
from app.models import Estudiante, Libro, Prestamo


@bibliotecario_bp.route('/inicio')
@login_required
@requiere_rol('bibliotecario')
def inicio():
    total_libros = Libro.query.filter_by(activo=True).count()
    prestamos_activos = Prestamo.query.filter_by(estado='activo').count()
    total_estudiantes = Estudiante.query.filter_by(estado='activo').count()

    prestamos_vencidos = db.session.execute(
        text('SELECT COUNT(*) FROM vista_prestamos_vencidos')
    ).scalar()

    ultimos_prestamos = (
        Prestamo.query.order_by(Prestamo.fecha_prestamo.desc()).limit(5).all()
    )

    return render_template(
        'bibliotecario/inicio.html',
        total_libros=total_libros,
        prestamos_activos=prestamos_activos,
        prestamos_vencidos=prestamos_vencidos,
        total_estudiantes=total_estudiantes,
        ultimos_prestamos=ultimos_prestamos,
        hoy=date.today(),
    )
