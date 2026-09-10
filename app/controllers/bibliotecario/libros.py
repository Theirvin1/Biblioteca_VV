import os
from datetime import date

from flask import current_app, jsonify, redirect, render_template, request, url_for, flash
from flask_login import login_required

from app.controllers.bibliotecario import bibliotecario_bp
from app.controllers.decoradores import requiere_rol
from app.extensions import db
from app.forms import LibroForm
from app.models import Autor, CategoriaLibro, Editorial, Ejemplar, Libro, LibroAutor
from app.paginacion import (
    POR_PAGINA, argumentos_activos, entero_filtro, id_nuevo, opcion_filtro,
    pagina_actual, texto_filtro,
)
from app.portadas import CARPETA_RELATIVA, PortadaInvalida, guardar_portada, url_portada
from app.validators import es_solo_letras


# Igual que Autor.nombres / Autor.apellidos (VARCHAR(100)). Sin este tope, un
# nombre mas largo llegaba intacto al INSERT y PostgreSQL respondia con un
# error de truncamiento que nadie atrapaba: error 500 con traceback.
LARGO_MAXIMO_NOMBRE_AUTOR = 100


def _carpeta_portadas_absoluta():
    return os.path.join(current_app.static_folder, *CARPETA_RELATIVA.split('/'))


def _siguiente_numero_ejemplar():
    # Solo se consideran los codigos con formato numerico EJ-NNNNNN: otros
    # formatos heredados o de carga masiva (p. ej. 'EJ-M0024-1') se ignoran
    # para no reventar el CAST con error 500.
    resultado = db.session.execute(
        db.text(
            "SELECT COALESCE(MAX(CAST(SUBSTRING(codigo_ejemplar FROM 4) AS INTEGER)), 0) "
            "FROM ejemplares WHERE codigo_ejemplar ~ '^EJ-[0-9]+$'"
        )
    ).scalar()
    return resultado or 0


def _obtener_o_crear_editorial(nombre):
    nombre = nombre.strip()
    editorial = Editorial.query.filter(db.func.lower(Editorial.nombre) == nombre.lower()).first()
    if editorial:
        return editorial

    editorial = Editorial(nombre=nombre)
    db.session.add(editorial)
    db.session.flush()
    return editorial


@bibliotecario_bp.route('/libros')
@login_required
@requiere_rol('bibliotecario')
def listado_libros():
    termino = texto_filtro(request, 'q')
    categoria_id = entero_filtro(request, 'categoria')
    disponibilidad = opcion_filtro(request, 'disponibilidad', ('disponibles', 'agotados'))

    consulta = Libro.query
    if termino:
        patron = f'%{termino}%'
        # El autor vive en otra tabla: se busca con un subquery para no
        # duplicar filas del libro cuando tiene varios autores.
        libros_del_autor = (
            db.session.query(LibroAutor.libro_id)
            .join(Autor, Autor.id == LibroAutor.autor_id)
            .filter(db.or_(
                Autor.nombres.ilike(patron),
                Autor.apellidos.ilike(patron),
                (Autor.nombres + ' ' + Autor.apellidos).ilike(patron),
            ))
        )
        consulta = consulta.filter(db.or_(
            Libro.titulo.ilike(patron),
            Libro.isbn.ilike(patron),
            Libro.id.in_(libros_del_autor),
        ))
    if categoria_id:
        consulta = consulta.filter(Libro.categoria_id == categoria_id)
    if disponibilidad == 'disponibles':
        consulta = consulta.filter(Libro.stock_disponible > 0)
    elif disponibilidad == 'agotados':
        consulta = consulta.filter(Libro.stock_disponible == 0)

    # Lo mas reciente primero: el ultimo libro registrado encabeza la lista.
    paginacion = consulta.order_by(Libro.id.desc()).paginate(
        page=pagina_actual(request), per_page=POR_PAGINA, error_out=False
    )

    return render_template(
        'bibliotecario/libros_lista.html',
        paginacion=paginacion,
        libros=paginacion.items,
        categorias=CategoriaLibro.query.order_by(CategoriaLibro.nombre).all(),
        filtros={'q': termino, 'categoria': categoria_id, 'disponibilidad': disponibilidad},
        argumentos=argumentos_activos(
            q=termino, categoria=categoria_id, disponibilidad=disponibilidad
        ),
        nuevo_id=id_nuevo(request),
    )


@bibliotecario_bp.route('/libros/nuevo', methods=['GET', 'POST'])
@login_required
@requiere_rol('bibliotecario')
def nuevo_libro():
    form = LibroForm()
    form.categoria_id.choices = [(0, '-- Selecciona una categoría --')] + [
        (categoria.id, categoria.nombre)
        for categoria in CategoriaLibro.query.order_by(CategoriaLibro.nombre)
    ]
    editoriales = Editorial.query.order_by(Editorial.nombre).all()

    if form.validate_on_submit():
        autores_ids = sorted({
            int(valor) for valor in (form.autores_ids.data or '').split(',')
            if valor.strip().isdigit()
        })

        if not autores_ids:
            flash('Debes agregar al menos un autor.', 'danger')
            return render_template('bibliotecario/libros_nuevo.html', form=form, editoriales=editoriales)

        autores_validos = Autor.query.filter(Autor.id.in_(autores_ids)).count()
        if autores_validos != len(autores_ids):
            flash('Uno o más autores seleccionados no son válidos.', 'danger')
            return render_template('bibliotecario/libros_nuevo.html', form=form, editoriales=editoriales)

        if Libro.query.filter_by(isbn=form.isbn.data).first():
            flash('Ya existe un libro registrado con ese ISBN.', 'danger')
            return render_template('bibliotecario/libros_nuevo.html', form=form, editoriales=editoriales)

        try:
            ruta_portada = guardar_portada(form.portada.data, _carpeta_portadas_absoluta())
        except PortadaInvalida as error:
            flash(str(error), 'danger')
            return render_template('bibliotecario/libros_nuevo.html', form=form, editoriales=editoriales)

        editorial = _obtener_o_crear_editorial(form.editorial_nombre.data)

        libro = Libro(
            isbn=form.isbn.data.strip(),
            titulo=form.titulo.data.strip(),
            subtitulo=(form.subtitulo.data or '').strip() or None,
            editorial_id=editorial.id,
            categoria_id=form.categoria_id.data,
            anio_publicacion=form.anio_publicacion.data,
            edicion=(form.edicion.data or '').strip() or None,
            num_paginas=form.num_paginas.data,
            idioma=form.idioma.data.strip(),
            stock_total=form.stock_inicial.data,
            stock_disponible=form.stock_inicial.data,
            portada_archivo=ruta_portada,
            resumen=(form.resumen.data or '').strip() or None,
        )
        db.session.add(libro)
        db.session.flush()

        for autor_id in autores_ids:
            db.session.add(LibroAutor(libro_id=libro.id, autor_id=autor_id))

        siguiente = _siguiente_numero_ejemplar()
        hoy = date.today()
        for i in range(1, form.stock_inicial.data + 1):
            codigo = f'EJ-{siguiente + i:06d}'
            db.session.add(Ejemplar(
                libro_id=libro.id,
                codigo_ejemplar=codigo,
                fecha_adquisicion=hoy,
            ))

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash('No se pudo registrar el libro. Verifica los datos ingresados.', 'danger')
            return render_template('bibliotecario/libros_nuevo.html', form=form, editoriales=editoriales)

        flash(
            f'Libro "{libro.titulo}" registrado con {form.stock_inicial.data} ejemplar(es).',
            'success'
        )
        # `nuevo` pinta el badge "Nuevo" en el listado; no se guarda en la BD.
        return redirect(url_for('bibliotecario.listado_libros', nuevo=libro.id))

    return render_template('bibliotecario/libros_nuevo.html', form=form, editoriales=editoriales)


@bibliotecario_bp.route('/api/libros/buscar')
@login_required
@requiere_rol('bibliotecario')
def api_buscar_libros():
    termino = (request.args.get('q') or '').strip()
    consulta = Libro.query
    if termino:
        patron = f'%{termino}%'
        consulta = consulta.filter(
            db.or_(Libro.titulo.ilike(patron), Libro.isbn.ilike(patron))
        )
    libros = consulta.order_by(Libro.titulo).limit(30).all()

    return jsonify([
        {
            'id': libro.id,
            'titulo': libro.titulo,
            'isbn': libro.isbn,
            'editorial': libro.editorial.nombre if libro.editorial else '',
            'categoria': libro.categoria.nombre if libro.categoria else '',
            'stock_disponible': libro.stock_disponible,
            'stock_total': libro.stock_total,
            'portada_url': url_portada(libro.portada_archivo),
        }
        for libro in libros
    ])


@bibliotecario_bp.route('/api/autores/buscar')
@login_required
@requiere_rol('bibliotecario')
def api_buscar_autores():
    termino = (request.args.get('q') or '').strip()
    if len(termino) < 2:
        return jsonify([])

    patron = f'%{termino}%'
    autores = (
        Autor.query.filter(
            db.or_(Autor.nombres.ilike(patron), Autor.apellidos.ilike(patron))
        )
        .order_by(Autor.apellidos)
        .limit(10)
        .all()
    )
    return jsonify([
        {'id': autor.id, 'nombre': f'{autor.nombres} {autor.apellidos}'}
        for autor in autores
    ])


@bibliotecario_bp.route('/api/autores', methods=['POST'])
@login_required
@requiere_rol('bibliotecario')
def api_crear_autor():
    # El cuerpo JSON lo elige por completo quien llama, asi que se comprueba
    # su forma antes de usarlo: un array o un numero en la raiz no tiene .get()
    # y un valor no textual en nombres/apellidos no tiene .strip(). En ambos
    # casos el AttributeError salia como error 500 con traceback.
    # `or {}` conserva el comportamiento previo cuando no llega cuerpo o no es
    # JSON valido: se sigue respondiendo "obligatorios", no un error de tipo.
    datos = request.get_json(silent=True) or {}
    if not isinstance(datos, dict):
        return jsonify({'error': 'El cuerpo de la petición debe ser un objeto JSON.'}), 400

    nombres = datos.get('nombres')
    apellidos = datos.get('apellidos')

    # Se rechaza el tipo en vez de convertirlo: 123 no es un nombre, y
    # pasarlo a "123" solo lo disfrazaria de valido para las reglas de abajo.
    # isinstance(True, str) es False, asi que los booleanos tambien caen aqui.
    for valor in (nombres, apellidos):
        if valor is not None and not isinstance(valor, str):
            return jsonify({'error': 'Nombres y apellidos deben enviarse como texto.'}), 400

    nombres = (nombres or '').strip()
    apellidos = (apellidos or '').strip()

    if not nombres or not apellidos:
        return jsonify({'error': 'Nombres y apellidos son obligatorios.'}), 400

    if len(nombres) < 2 or len(apellidos) < 2:
        return jsonify({'error': 'Nombres y apellidos deben tener al menos 2 caracteres.'}), 400

    if len(nombres) > LARGO_MAXIMO_NOMBRE_AUTOR or len(apellidos) > LARGO_MAXIMO_NOMBRE_AUTOR:
        return jsonify({
            'error': f'Nombres y apellidos no pueden superar los {LARGO_MAXIMO_NOMBRE_AUTOR} caracteres.',
        }), 400

    if not es_solo_letras(nombres) or not es_solo_letras(apellidos):
        return jsonify({'error': 'Nombres y apellidos solo pueden contener letras y espacios.'}), 400

    autor_existente = Autor.query.filter(
        db.func.lower(Autor.nombres) == nombres.lower(),
        db.func.lower(Autor.apellidos) == apellidos.lower(),
    ).first()
    if autor_existente:
        return jsonify({
            'id': autor_existente.id,
            'nombre': f'{autor_existente.nombres} {autor_existente.apellidos}',
        })

    autor = Autor(nombres=nombres, apellidos=apellidos)
    db.session.add(autor)

    # Red de seguridad: aunque las validaciones de arriba ya cubren longitud y
    # formato, cualquier rechazo de la BD (constraint, carrera entre dos
    # peticiones) debe volver como JSON de error, nunca como traceback. El
    # rollback deja la sesion utilizable para la siguiente peticion.
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'No se pudo registrar el autor. Verifica los datos ingresados.'}), 400

    return jsonify({'id': autor.id, 'nombre': f'{autor.nombres} {autor.apellidos}'}), 201
