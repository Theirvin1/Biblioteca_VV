from flask import jsonify, redirect, render_template, request, url_for, flash
from flask_login import login_required

from app.controllers.decoradores import requiere_rol
from app.controllers.estudiante import estudiante_bp
from app.models import CategoriaLibro, Libro
from app.portadas import url_portada


@estudiante_bp.route('/catalogo')
@login_required
@requiere_rol('estudiante')
def listado_catalogo():
    categorias = CategoriaLibro.query.order_by(CategoriaLibro.nombre).all()
    libros = Libro.query.filter_by(activo=True).order_by(Libro.titulo).all()
    return render_template('estudiante/catalogo.html', libros=libros, categorias=categorias)


@estudiante_bp.route('/api/catalogo/buscar')
@login_required
@requiere_rol('estudiante')
def api_buscar_catalogo():
    termino = (request.args.get('q') or '').strip()
    categoria_id = request.args.get('categoria_id', type=int)

    consulta = Libro.query.filter_by(activo=True)
    if termino:
        consulta = consulta.filter(Libro.titulo.ilike(f'%{termino}%'))
    if categoria_id:
        consulta = consulta.filter(Libro.categoria_id == categoria_id)

    libros = consulta.order_by(Libro.titulo).limit(50).all()

    return jsonify([
        {
            'isbn': libro.isbn,
            'titulo': libro.titulo,
            'editorial': libro.editorial.nombre if libro.editorial else '',
            'categoria': libro.categoria.nombre if libro.categoria else '',
            'stock_disponible': libro.stock_disponible,
            'portada_url': url_portada(libro.portada_archivo),
            'autores': ', '.join(
                f'{la.autor.nombres} {la.autor.apellidos}' for la in libro.libro_autor if la.autor
            ) or 'Autor no registrado',
            'resumen': libro.resumen or '',
        }
        for libro in libros
    ])


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
