from flask import redirect, render_template, request, url_for, flash
from flask_login import login_required

from app.controllers.decoradores import requiere_rol
from app.controllers.estudiante import estudiante_bp
from app.models import CategoriaLibro, Libro
from app.paginacion import (
    POR_PAGINA_CATALOGO, argumentos_activos, entero_filtro, pagina_actual,
    texto_filtro,
)


@estudiante_bp.route('/catalogo')
@login_required
@requiere_rol('estudiante')
def listado_catalogo():
    termino = texto_filtro(request, 'q')
    categoria_id = entero_filtro(request, 'categoria_id')

    consulta = Libro.query.filter_by(activo=True)
    if termino:
        consulta = consulta.filter(Libro.titulo.ilike(f'%{termino}%'))
    if categoria_id:
        consulta = consulta.filter(Libro.categoria_id == categoria_id)

    paginacion = consulta.order_by(Libro.titulo).paginate(
        page=pagina_actual(request), per_page=POR_PAGINA_CATALOGO, error_out=False
    )

    filtros = {'q': termino, 'categoria_id': categoria_id}
    return render_template(
        'estudiante/catalogo.html',
        libros=paginacion.items,
        categorias=CategoriaLibro.query.order_by(CategoriaLibro.nombre).all(),
        paginacion=paginacion,
        filtros=filtros,
        argumentos=argumentos_activos(**filtros),
    )


@estudiante_bp.route('/catalogo/<isbn>')
@login_required
@requiere_rol('estudiante')
def detalle_libro(isbn):
    libro = Libro.query.filter_by(isbn=isbn, activo=True).first()
    if libro is None:
        flash('El libro solicitado no existe o no está disponible.', 'warning')
        return redirect(url_for('estudiante.listado_catalogo'))

    autores = [f'{la.autor.nombres} {la.autor.apellidos}' for la in libro.libro_autor]
    return render_template('estudiante/libro_detalle.html', libro=libro, autores=autores)
