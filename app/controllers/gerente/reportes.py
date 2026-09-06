from flask import redirect, render_template, request, url_for, flash
from flask_login import login_required
from sqlalchemy import text

from app.controllers.decoradores import requiere_rol
from app.controllers.gerente import gerente_bp
from app.extensions import db
from app.models import Devolucion, Ejemplar, Estudiante, Libro, Prestamo, Usuario
from app.paginacion import (
    POR_PAGINA, PaginacionManual, argumentos_activos, fecha_filtro, opcion_filtro,
    pagina_actual, paginar_select, texto_filtro,
)

# Lista blanca fija: el parámetro <tipo> de la URL solo se usa para
# buscar en este diccionario. El nombre real de la vista SQL que se
# ejecuta nunca proviene directamente de la petición del usuario.
REPORTES = {
    'prestamos-activos': {
        'titulo': 'Préstamos activos',
        'vista': 'vista_prestamos_activos',
    },
    'multas-pendientes': {
        'titulo': 'Multas pendientes',
        'vista': 'vista_multas_pendientes',
    },
    'libros-mas-prestados': {
        'titulo': 'Libros más prestados',
        'vista': 'vista_libros_mas_prestados',
    },
    'estudiantes-con-deuda': {
        'titulo': 'Estudiantes con deuda',
        'vista': 'vista_estudiantes_con_deuda',
    },
    'inventario-actual': {
        'titulo': 'Inventario actual',
        'vista': 'vista_inventario_actual',
    },
    'historial-movimientos': {
        'titulo': 'Historial de movimientos',
        'vista': 'vista_historial_movimientos',
    },
}

TIPOS_MOVIMIENTO = ('prestamo', 'devolucion')


@gerente_bp.route('/reportes')
@login_required
@requiere_rol('gerente')
def listado_reportes():
    return render_template('gerente/reportes.html', reportes=REPORTES)


@gerente_bp.route('/reportes/<tipo>')
@login_required
@requiere_rol('gerente')
def ver_reporte(tipo):
    reporte = REPORTES.get(tipo)
    if reporte is None:
        flash('El reporte solicitado no existe.', 'warning')
        return redirect(url_for('gerente.listado_reportes'))

    # Cada reporte extenso tiene su propio manejador (filtros + paginacion).
    # MANEJADORES se arma al final del archivo, una vez definidas las
    # funciones; el nombre se resuelve recien cuando se llama a esta vista.
    return MANEJADORES[tipo]()


def _consulta_historial():
    """
    Equivalente en ORM a vista_historial_movimientos (union de prestamos y
    devoluciones), con columnas reales que la vista no tenia: ISBN del libro,
    usuario/responsable que registro el movimiento y cedula del estudiante
    (esta ultima solo para busqueda; no se muestra como columna en la tabla).
    Se construye en ORM (no sobre la vista) para poder filtrar, paginar y
    agregar en backend.
    """
    bibliotecario_prestamo = db.aliased(Usuario)
    bibliotecario_devolucion = db.aliased(Usuario)

    # `orden_desempate` complementa a `fecha`: varios prestamos de una misma
    # operacion (prestamo multiple) comparten el now() de la transaccion, asi
    # que ordenar solo por fecha no garantiza "el mas reciente primero".
    prestamos = (
        db.select(
            db.literal('prestamo').label('tipo_movimiento'),
            Prestamo.fecha_prestamo.label('fecha'),
            Prestamo.id.label('orden_desempate'),
            (Estudiante.nombres + ' ' + Estudiante.apellidos).label('nombre_estudiante'),
            Estudiante.cedula.label('cedula_estudiante'),
            Libro.titulo.label('titulo_libro'),
            Libro.isbn.label('isbn_libro'),
            bibliotecario_prestamo.username.label('responsable'),
            Prestamo.estado.label('resultado'),
        )
        .select_from(Prestamo)
        .join(Estudiante, Estudiante.id == Prestamo.estudiante_id)
        .join(Ejemplar, Ejemplar.id == Prestamo.ejemplar_id)
        .join(Libro, Libro.id == Ejemplar.libro_id)
        .join(bibliotecario_prestamo, bibliotecario_prestamo.id == Prestamo.bibliotecario_id)
    )
    devoluciones = (
        db.select(
            db.literal('devolucion').label('tipo_movimiento'),
            Devolucion.fecha_devolucion.label('fecha'),
            Devolucion.id.label('orden_desempate'),
            (Estudiante.nombres + ' ' + Estudiante.apellidos).label('nombre_estudiante'),
            Estudiante.cedula.label('cedula_estudiante'),
            Libro.titulo.label('titulo_libro'),
            Libro.isbn.label('isbn_libro'),
            bibliotecario_devolucion.username.label('responsable'),
            Devolucion.estado_ejemplar.label('resultado'),
        )
        .select_from(Devolucion)
        .join(Prestamo, Prestamo.id == Devolucion.prestamo_id)
        .join(Estudiante, Estudiante.id == Prestamo.estudiante_id)
        .join(Ejemplar, Ejemplar.id == Prestamo.ejemplar_id)
        .join(Libro, Libro.id == Ejemplar.libro_id)
        .join(bibliotecario_devolucion, bibliotecario_devolucion.id == Devolucion.bibliotecario_id)
    )
    return db.union_all(prestamos, devoluciones).subquery()


def _reporte_historial():
    columna = _consulta_historial()
    condiciones = []

    # Buscador general: libro, ISBN, nombre/apellidos o cedula del estudiante.
    termino = texto_filtro(request, 'q')
    if termino:
        patron = f'%{termino}%'
        condiciones.append(db.or_(
            columna.c.titulo_libro.ilike(patron),
            columna.c.isbn_libro.ilike(patron),
            columna.c.nombre_estudiante.ilike(patron),
            columna.c.cedula_estudiante.ilike(patron),
        ))

    filtro_tipo_movimiento = opcion_filtro(request, 'tipo_movimiento', TIPOS_MOVIMIENTO)
    if filtro_tipo_movimiento:
        condiciones.append(columna.c.tipo_movimiento == filtro_tipo_movimiento)

    fecha_desde = fecha_filtro(request, 'fecha_desde')
    if fecha_desde:
        condiciones.append(db.func.date(columna.c.fecha) >= fecha_desde)

    fecha_hasta = fecha_filtro(request, 'fecha_hasta')
    if fecha_hasta:
        condiciones.append(db.func.date(columna.c.fecha) <= fecha_hasta)

    pagina = pagina_actual(request)
    consulta_base = db.select(columna).where(*condiciones)
    filas_crudas, paginacion = paginar_select(
        consulta_base,
        orden=(columna.c.fecha.desc(), columna.c.orden_desempate.desc()),
        page=pagina,
        per_page=POR_PAGINA,
    )

    columnas = ['tipo_movimiento', 'fecha', 'nombre_estudiante', 'titulo_libro', 'isbn_libro', 'responsable', 'resultado']
    filas = [
        (
            fila.tipo_movimiento.capitalize(),
            fila.fecha.strftime('%d/%m/%Y %H:%M') if fila.fecha else '-',
            fila.nombre_estudiante,
            fila.titulo_libro,
            fila.isbn_libro,
            fila.responsable,
            fila.resultado,
        )
        for fila in filas_crudas
    ]
    paginacion.items = filas

    # El grafico refleja el MISMO filtro aplicado (no solo la pagina actual).
    conteo_tipo = dict(
        db.session.execute(
            db.select(columna.c.tipo_movimiento, db.func.count())
            .where(*condiciones)
            .group_by(columna.c.tipo_movimiento)
        ).all()
    )
    grafico = {
        'labels': ['Préstamos', 'Devoluciones'],
        'valores': [conteo_tipo.get('prestamo', 0), conteo_tipo.get('devolucion', 0)],
    }

    filtros = {
        'q': termino,
        'tipo_movimiento': filtro_tipo_movimiento,
        'fecha_desde': fecha_desde.isoformat() if fecha_desde else '',
        'fecha_hasta': fecha_hasta.isoformat() if fecha_hasta else '',
    }

    return render_template(
        'gerente/reporte_historial.html',
        titulo='Historial de movimientos',
        tipo='historial-movimientos',
        reportes=REPORTES,
        columnas=columnas,
        filas=filas,
        paginacion=paginacion,
        filtros=filtros,
        argumentos=argumentos_activos(**filtros),
        grafico=grafico,
    )


# ---------------------------------------------------------------------------
# Prestamos activos
# ---------------------------------------------------------------------------

def _reporte_prestamos_activos():
    """
    Reconstruye vista_prestamos_activos en ORM (mismas columnas visibles,
    mismos datos) para poder buscar tambien por cedula del estudiante e ISBN
    del libro: son datos reales de las tablas ya unidas en la vista, solo que
    esta no los seleccionaba. Ambas quedan ocultas (no se agregan a la tabla)
    para no cambiar el diseño actual del reporte.
    """
    consulta = (
        db.select(
            Prestamo.id,
            Prestamo.codigo_prestamo,
            (Estudiante.nombres + ' ' + Estudiante.apellidos).label('nombre_estudiante'),
            Libro.titulo.label('titulo_libro'),
            Ejemplar.codigo_ejemplar,
            Prestamo.fecha_prestamo,
            Prestamo.fecha_limite,
        )
        .select_from(Prestamo)
        .join(Estudiante, Estudiante.id == Prestamo.estudiante_id)
        .join(Ejemplar, Ejemplar.id == Prestamo.ejemplar_id)
        .join(Libro, Libro.id == Ejemplar.libro_id)
        .where(Prestamo.estado == 'activo')
    )

    # Buscador general: estudiante, cedula, libro, ISBN o codigo de prestamo.
    termino = texto_filtro(request, 'q')
    if termino:
        patron = f'%{termino}%'
        consulta = consulta.where(db.or_(
            (Estudiante.nombres + ' ' + Estudiante.apellidos).ilike(patron),
            Estudiante.cedula.ilike(patron),
            Libro.titulo.ilike(patron),
            Libro.isbn.ilike(patron),
            Prestamo.codigo_prestamo.ilike(patron),
        ))

    pagina = pagina_actual(request)
    filas_crudas, paginacion = paginar_select(
        consulta, orden=(Prestamo.id.desc(),), page=pagina, per_page=POR_PAGINA,
    )

    columnas = [
        'id', 'codigo_prestamo', 'nombre_estudiante', 'titulo_libro',
        'codigo_ejemplar', 'fecha_prestamo', 'fecha_limite',
    ]
    filas = [
        (
            fila.id, fila.codigo_prestamo, fila.nombre_estudiante, fila.titulo_libro,
            fila.codigo_ejemplar, fila.fecha_prestamo, fila.fecha_limite,
        )
        for fila in filas_crudas
    ]
    paginacion.items = filas

    filtros = {'q': termino}
    return render_template(
        'gerente/reporte_detalle.html',
        titulo=REPORTES['prestamos-activos']['titulo'],
        tipo='prestamos-activos',
        reportes=REPORTES,
        columnas=columnas,
        filas=filas,
        paginacion=paginacion,
        filtros=filtros,
        argumentos=argumentos_activos(**filtros),
    )


# ---------------------------------------------------------------------------
# Multas pendientes
# ---------------------------------------------------------------------------

def _reporte_multas_pendientes():
    """
    Reconstruye vista_multas_pendientes en ORM para poder buscar tambien por
    cedula (la vista no la expone, pero es un dato real de estudiantes). No
    se agrega codigo de prestamo: este reporte agrega multas POR ESTUDIANTE
    (puede sumar varias devoluciones distintas), no existe un unico codigo de
    prestamo por fila.
    """
    consulta = (
        db.select(
            Estudiante.id.label('estudiante_id'),
            (Estudiante.nombres + ' ' + Estudiante.apellidos).label('nombre_estudiante'),
            db.func.sum(Devolucion.multa_generada).label('monto_total'),
        )
        .select_from(Devolucion)
        .join(Prestamo, Prestamo.id == Devolucion.prestamo_id)
        .join(Estudiante, Estudiante.id == Prestamo.estudiante_id)
        .where(Devolucion.multa_generada > 0, Devolucion.multa_pagada.is_(False))
    )

    termino = texto_filtro(request, 'q')
    if termino:
        patron = f'%{termino}%'
        consulta = consulta.where(db.or_(
            (Estudiante.nombres + ' ' + Estudiante.apellidos).ilike(patron),
            Estudiante.cedula.ilike(patron),
        ))

    consulta = consulta.group_by(Estudiante.id, Estudiante.nombres, Estudiante.apellidos)

    pagina = pagina_actual(request)
    filas_crudas, paginacion = paginar_select(
        consulta, orden=(db.desc('monto_total'),), page=pagina, per_page=POR_PAGINA,
    )

    columnas = ['estudiante_id', 'nombre_estudiante', 'monto_total']
    filas = [(fila.estudiante_id, fila.nombre_estudiante, fila.monto_total) for fila in filas_crudas]
    paginacion.items = filas

    filtros = {'q': termino}
    return render_template(
        'gerente/reporte_detalle.html',
        titulo=REPORTES['multas-pendientes']['titulo'],
        tipo='multas-pendientes',
        reportes=REPORTES,
        columnas=columnas,
        filas=filas,
        paginacion=paginacion,
        filtros=filtros,
        argumentos=argumentos_activos(**filtros),
    )


# ---------------------------------------------------------------------------
# Reportes cuya vista YA expone todas las columnas necesarias para filtrar
# (estudiantes-con-deuda tiene cedula; inventario-actual tiene stock). No
# hace falta bypasearlas con joins propios: se envuelven con un WHERE armado
# a mano (nombres de columna fijos, nunca provistos por el usuario) y se
# pagina con LIMIT/OFFSET.
# ---------------------------------------------------------------------------

def _paginar_vista(vista, condiciones_sql, parametros, orden, page):
    where = f" WHERE {' AND '.join(condiciones_sql)}" if condiciones_sql else ''
    base_sql = f"SELECT * FROM {vista}{where}"

    total = db.session.execute(text(f"SELECT COUNT(*) FROM ({base_sql}) c"), parametros).scalar()
    resultado = db.session.execute(
        text(f"{base_sql} ORDER BY {orden} LIMIT :limit OFFSET :offset"),
        dict(parametros, limit=POR_PAGINA, offset=(page - 1) * POR_PAGINA),
    )
    columnas = list(resultado.keys())
    filas = resultado.fetchall()
    return columnas, filas, PaginacionManual(items=filas, total=total, page=page, per_page=POR_PAGINA)


def _reporte_estudiantes_con_deuda():
    termino = texto_filtro(request, 'q')
    condiciones, parametros = [], {}
    if termino:
        condiciones.append('(nombre_estudiante ILIKE :patron OR cedula ILIKE :patron)')
        parametros['patron'] = f'%{termino}%'

    pagina = pagina_actual(request)
    columnas, filas, paginacion = _paginar_vista(
        'vista_estudiantes_con_deuda', condiciones, parametros,
        orden='monto_adeudado DESC', page=pagina,
    )

    filtros = {'q': termino}
    return render_template(
        'gerente/reporte_detalle.html',
        titulo=REPORTES['estudiantes-con-deuda']['titulo'],
        tipo='estudiantes-con-deuda',
        reportes=REPORTES,
        columnas=columnas,
        filas=filas,
        paginacion=paginacion,
        filtros=filtros,
        argumentos=argumentos_activos(**filtros),
    )


def _reporte_inventario_actual():
    """
    Filtros limitados a lo que la vista realmente devuelve: titulo y
    disponibilidad (a partir de stock_disponible). La vista no expone ISBN
    ni categoria, asi que no se agregan esos filtros.
    """
    termino = texto_filtro(request, 'q')
    disponibilidad = opcion_filtro(request, 'disponibilidad', ('disponibles', 'agotados'))

    condiciones, parametros = [], {}
    if termino:
        condiciones.append('titulo ILIKE :patron')
        parametros['patron'] = f'%{termino}%'
    if disponibilidad == 'disponibles':
        condiciones.append('stock_disponible > 0')
    elif disponibilidad == 'agotados':
        condiciones.append('stock_disponible = 0')

    pagina = pagina_actual(request)
    columnas, filas, paginacion = _paginar_vista(
        'vista_inventario_actual', condiciones, parametros, orden='id DESC', page=pagina,
    )

    filtros = {'q': termino, 'disponibilidad': disponibilidad}
    return render_template(
        'gerente/reporte_detalle.html',
        titulo=REPORTES['inventario-actual']['titulo'],
        tipo='inventario-actual',
        reportes=REPORTES,
        columnas=columnas,
        filas=filas,
        paginacion=paginacion,
        filtros=filtros,
        argumentos=argumentos_activos(**filtros),
        filtro_extra={
            'nombre': 'disponibilidad',
            'etiqueta': 'Disponibilidad',
            'valor': disponibilidad,
            'opciones': [('disponibles', 'Con stock'), ('agotados', 'Sin stock')],
        },
    )


# ---------------------------------------------------------------------------
# Libros mas prestados
# ---------------------------------------------------------------------------

def _reporte_libros_mas_prestados():
    """
    CASO B: vista_libros_mas_prestados devuelve TODOS los libros con al menos
    un prestamo (sin LIMIT), ordenados por total_prestamos desc. No es un
    Top N fijo, asi que se pagina igual que cualquier listado extenso,
    conservando ese orden. Se agrega busqueda por titulo/ISBN (isbn queda
    oculto: la vista original solo mostraba id/titulo/total_prestamos).
    """
    consulta = (
        db.select(
            Libro.id,
            Libro.titulo,
            db.func.count(Prestamo.id).label('total_prestamos'),
        )
        .select_from(Libro)
        .join(Ejemplar, Ejemplar.libro_id == Libro.id)
        .join(Prestamo, Prestamo.ejemplar_id == Ejemplar.id)
    )

    termino = texto_filtro(request, 'q')
    if termino:
        patron = f'%{termino}%'
        consulta = consulta.where(db.or_(Libro.titulo.ilike(patron), Libro.isbn.ilike(patron)))

    consulta = consulta.group_by(Libro.id, Libro.titulo)

    pagina = pagina_actual(request)
    filas_crudas, paginacion = paginar_select(
        consulta, orden=(db.desc('total_prestamos'),), page=pagina, per_page=POR_PAGINA,
    )

    columnas = ['id', 'titulo', 'total_prestamos']
    filas = [(fila.id, fila.titulo, fila.total_prestamos) for fila in filas_crudas]
    paginacion.items = filas

    filtros = {'q': termino}
    return render_template(
        'gerente/reporte_detalle.html',
        titulo=REPORTES['libros-mas-prestados']['titulo'],
        tipo='libros-mas-prestados',
        reportes=REPORTES,
        columnas=columnas,
        filas=filas,
        paginacion=paginacion,
        filtros=filtros,
        argumentos=argumentos_activos(**filtros),
    )


MANEJADORES = {
    'prestamos-activos': _reporte_prestamos_activos,
    'multas-pendientes': _reporte_multas_pendientes,
    'libros-mas-prestados': _reporte_libros_mas_prestados,
    'estudiantes-con-deuda': _reporte_estudiantes_con_deuda,
    'inventario-actual': _reporte_inventario_actual,
    'historial-movimientos': _reporte_historial,
}
