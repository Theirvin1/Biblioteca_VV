"""
Registro de prestamos del bibliotecario.

Un registro puede incluir VARIOS libros para un mismo estudiante. Cada libro
genera su propio Prestamo (trazabilidad, fecha limite, multa y devolucion
individuales), y todos los prestamos creados en la misma accion comparten el
codigo de operacion `Prestamo.grupo_prestamo` (ver comun.py). El lote completo
se guarda en UNA sola transaccion: si falla un libro, no se guarda ninguno.
"""
from datetime import date

from flask import jsonify, redirect, render_template, request, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import text

from app.controllers.bibliotecario import bibliotecario_bp
from app.controllers.bibliotecario.comun import (
    ESTADOS_OPERACION, calcular_cupos, calcular_edad, contar_prestamos_vencidos,
    generar_codigo_grupo, iniciales, max_prestamos_activos, paginar_operaciones,
    prestamos_de_operacion, resumen_operacion,
)
from app.controllers.decoradores import requiere_rol
from app.extensions import db
from app.forms import PrestamoForm
from app.models import Ejemplar, Estudiante, Libro, Prestamo
from app.paginacion import (
    POR_PAGINA, argumentos_activos, id_nuevo, opcion_filtro, pagina_actual,
    texto_filtro,
)
from app.portadas import url_portada


def _validar_prestamo_bd(cedula, isbn):
    """Validacion autoritativa en BD (funcion validar_prestamo de setup.sql)."""
    return db.session.execute(
        text('SELECT codigo_resultado, mensaje FROM validar_prestamo(:cedula, :isbn)'),
        {'cedula': cedula, 'isbn': isbn},
    ).fetchone()


def _generar_codigo_prestamo():
    return db.session.execute(text('SELECT generar_codigo_prestamo()')).scalar()


def _max_prestamos_activos():
    return max_prestamos_activos()


def _cedula_valida(cedula):
    return len(cedula) == 10 and cedula.isdigit()


def _isbn_valido(isbn):
    return len(isbn) == 13 and isbn.isdigit()


def _autores_de(libro):
    nombres = [
        f'{enlace.autor.nombres} {enlace.autor.apellidos}'.strip()
        for enlace in getattr(libro, 'libro_autor', []) if enlace.autor
    ]
    return ', '.join(nombres)


def _ejemplar_disponible(libro_id, excluidos=()):
    consulta = Ejemplar.query.filter(
        Ejemplar.libro_id == libro_id,
        Ejemplar.estado == 'disponible',
    )
    if excluidos:
        consulta = consulta.filter(~Ejemplar.id.in_(excluidos))
    return consulta.order_by(Ejemplar.id).first()


# ---------------------------------------------------------------------------
# Evaluacion de estudiante y libro. Se usa igual en los endpoints AJAX de las
# tarjetas y en el POST final: el navegador nunca es la unica validacion.
# ---------------------------------------------------------------------------

def _evaluar_estudiante(cedula):
    """Devuelve (estudiante_o_None, datos_para_la_tarjeta)."""
    if not _cedula_valida(cedula):
        return None, {'ok': False, 'mensaje': 'La cédula debe contener exactamente 10 dígitos.'}

    estudiante = Estudiante.query.filter_by(cedula=cedula).first()
    if estudiante is None:
        return None, {'ok': False, 'mensaje': 'Estudiante no registrado.'}

    activos, maximo, cupos = calcular_cupos(estudiante.id)
    vencidos = contar_prestamos_vencidos(estudiante.id)

    datos = {
        'ok': True,
        'mensaje': 'Estudiante encontrado.',
        'nombre_completo': f'{estudiante.nombres} {estudiante.apellidos}',
        'iniciales': iniciales(estudiante.nombres, estudiante.apellidos),
        'cedula': estudiante.cedula,
        'edad': calcular_edad(estudiante.fecha_nacimiento),
        'carrera': estudiante.carrera.nombre if estudiante.carrera else 'Sin carrera',
        'estado': estudiante.estado,
        'prestamos_activos': activos,
        'max_prestamos': maximo,
        'cupos_disponibles': cupos,
        'prestamos_vencidos': vencidos,
        'advertencia': None,
    }

    if estudiante.estado != 'activo':
        datos['ok'] = False
        datos['mensaje'] = f'El estudiante está {estudiante.estado} y no puede llevar libros.'
    elif vencidos > 0:
        datos['ok'] = False
        datos['mensaje'] = (
            f'El estudiante tiene {vencidos} préstamo(s) vencido(s) pendiente(s). '
            'Debe regularizarlos antes de un nuevo préstamo.'
        )
        datos['advertencia'] = datos['mensaje']
    elif cupos is not None and cupos <= 0:
        datos['ok'] = False
        datos['mensaje'] = f'El estudiante alcanzó el máximo de {maximo} préstamos activos.'
    elif cupos is not None:
        datos['mensaje'] = f'Estudiante encontrado. Dispone de {cupos} cupo(s) para préstamos.'

    return estudiante, datos


def _evaluar_libro(isbn):
    """Devuelve (libro_o_None, datos_para_la_tarjeta)."""
    if not _isbn_valido(isbn):
        return None, {'ok': False, 'mensaje': 'El ISBN debe contener exactamente 13 dígitos.'}

    libro = Libro.query.filter_by(isbn=isbn).first()
    if libro is None:
        return None, {'ok': False, 'mensaje': 'Libro no registrado.'}

    datos = {
        'ok': True,
        'mensaje': 'Libro disponible.',
        'isbn': libro.isbn,
        'titulo': libro.titulo,
        'subtitulo': libro.subtitulo or '',
        'autores': _autores_de(libro) or 'Autor no registrado',
        'categoria': libro.categoria.nombre if libro.categoria else 'Sin categoría',
        'editorial': libro.editorial.nombre if libro.editorial else 'Sin editorial',
        'anio': libro.anio_publicacion,
        'stock_disponible': libro.stock_disponible,
        'stock_total': libro.stock_total,
        'portada_url': url_portada(libro.portada_archivo),
    }

    if not libro.activo:
        datos['ok'] = False
        datos['mensaje'] = 'El libro no está activo y no puede prestarse.'
    elif libro.stock_disponible <= 0:
        datos['ok'] = False
        datos['mensaje'] = 'No hay stock disponible de este libro.'
    elif _ejemplar_disponible(libro.id) is None:
        datos['ok'] = False
        datos['mensaje'] = 'No hay ejemplares disponibles para este libro en este momento.'

    return libro, datos


# ---------------------------------------------------------------------------
# Vistas
# ---------------------------------------------------------------------------

@bibliotecario_bp.route('/prestamos')
@login_required
@requiere_rol('bibliotecario')
def listado_prestamos():
    termino = texto_filtro(request, 'q')
    estado = opcion_filtro(request, 'estado', ESTADOS_OPERACION, por_defecto='pendientes')

    paginacion, operaciones = paginar_operaciones(
        termino=termino,
        estado=estado,
        page=pagina_actual(request),
        per_page=POR_PAGINA,
    )

    return render_template(
        'bibliotecario/prestamos_lista.html',
        paginacion=paginacion,
        operaciones=operaciones,
        filtros={'q': termino, 'estado': estado},
        argumentos=argumentos_activos(q=termino, estado=estado),
        nuevo_id=id_nuevo(request),
        hoy=date.today(),
    )


@bibliotecario_bp.route('/prestamos/<int:prestamo_id>/detalle')
@login_required
@requiere_rol('bibliotecario')
def detalle_prestamo(prestamo_id):
    prestamo = db.session.get(Prestamo, prestamo_id)
    if prestamo is None:
        flash('El préstamo indicado no existe.', 'danger')
        return redirect(url_for('bibliotecario.listado_prestamos'))

    operacion = resumen_operacion(prestamos_de_operacion(prestamo))
    _, datos_estudiante = _evaluar_estudiante(operacion['estudiante'].cedula)

    return render_template(
        'bibliotecario/prestamo_detalle.html',
        operacion=operacion,
        estudiante=datos_estudiante,
        hoy=date.today(),
    )


@bibliotecario_bp.route('/prestamos/nuevo', methods=['GET', 'POST'])
@login_required
@requiere_rol('bibliotecario')
def nuevo_prestamo():
    form = PrestamoForm()

    def _volver_con_error(mensaje):
        flash(mensaje, 'danger')
        return render_template('bibliotecario/prestamos_nuevo.html', form=form)

    if form.validate_on_submit():
        cedula = form.cedula.data.strip()
        isbns = [parte.strip() for parte in (form.isbns.data or '').split(',') if parte.strip()]

        if not isbns:
            return _volver_con_error('Agrega al menos un libro al préstamo.')

        if len(set(isbns)) != len(isbns):
            return _volver_con_error('Este libro ya fue agregado: hay un ISBN repetido en la lista.')

        if any(not _isbn_valido(isbn) for isbn in isbns):
            return _volver_con_error('Uno de los ISBN de la lista no es válido.')

        # Revalidacion completa en el servidor: el estado pudo cambiar entre
        # que se armo la lista en pantalla y el envio del formulario.
        estudiante, datos_estudiante = _evaluar_estudiante(cedula)
        if estudiante is None or not datos_estudiante['ok']:
            return _volver_con_error(datos_estudiante['mensaje'])

        cupos = datos_estudiante['cupos_disponibles']
        if cupos is not None and len(isbns) > cupos:
            return _volver_con_error(
                f'El estudiante solo dispone de {cupos} cupo(s) y se intentan '
                f'prestar {len(isbns)} libro(s).'
            )

        observaciones = (form.observaciones.data or '').strip() or None
        grupo = generar_codigo_grupo() if len(isbns) > 1 else None
        ejemplares_usados = []
        titulos = []
        creados = []

        try:
            for isbn in isbns:
                resultado = _validar_prestamo_bd(cedula, isbn)
                if resultado is None or resultado.codigo_resultado != 0:
                    mensaje = resultado.mensaje if resultado else 'No se pudo validar el préstamo.'
                    raise ValueError(f'{mensaje} (ISBN {isbn}).')

                libro, datos_libro = _evaluar_libro(isbn)
                if libro is None or not datos_libro['ok']:
                    raise ValueError('{} (ISBN {}).'.format(datos_libro['mensaje'], isbn))

                ejemplar = _ejemplar_disponible(libro.id, excluidos=ejemplares_usados)
                if ejemplar is None:
                    raise ValueError(f'No hay ejemplares disponibles para el libro {libro.titulo}.')

                prestamo = Prestamo(
                    codigo_prestamo=_generar_codigo_prestamo(),
                    estudiante_id=estudiante.id,
                    ejemplar_id=ejemplar.id,
                    bibliotecario_id=current_user.id,
                    observaciones=observaciones,
                    grupo_prestamo=grupo,
                )
                db.session.add(prestamo)
                # flush por libro: dispara los triggers de stock/ejemplar y hace
                # que generar_codigo_prestamo() vea el codigo recien insertado.
                db.session.flush()

                ejemplares_usados.append(ejemplar.id)
                titulos.append(libro.titulo)
                creados.append(prestamo.id)

            db.session.commit()
        except ValueError as error:
            db.session.rollback()
            return _volver_con_error(str(error))
        except Exception:
            db.session.rollback()
            return _volver_con_error('No se pudo registrar el préstamo. No se guardó ningún libro.')

        # Representante de la operacion: el primer prestamo creado. Con el se
        # pinta el badge "Nuevo" sobre la operacion completa, no sobre cada libro.
        representante_id = creados[0]
        nombre = f'{estudiante.nombres} {estudiante.apellidos}'
        if grupo:
            flash(
                f'Préstamo registrado correctamente · Operación {grupo} · '
                f'{len(titulos)} libro(s) para {nombre}.',
                'success'
            )
        else:
            flash(
                f'Préstamo registrado correctamente para {nombre} · Libro: {titulos[0]}.',
                'success'
            )
        return redirect(url_for('bibliotecario.listado_prestamos', nuevo=representante_id))

    return render_template('bibliotecario/prestamos_nuevo.html', form=form)


# ---------------------------------------------------------------------------
# Endpoints AJAX de las tarjetas
# ---------------------------------------------------------------------------

@bibliotecario_bp.route('/api/prestamos/estudiante')
@login_required
@requiere_rol('bibliotecario')
def api_estudiante_prestamo():
    cedula = (request.args.get('cedula') or '').strip()
    _, datos = _evaluar_estudiante(cedula)
    return jsonify(datos)


@bibliotecario_bp.route('/api/prestamos/libro')
@login_required
@requiere_rol('bibliotecario')
def api_libro_prestamo():
    isbn = (request.args.get('isbn') or '').strip()
    _, datos = _evaluar_libro(isbn)
    return jsonify(datos)


@bibliotecario_bp.route('/api/prestamos/validar')
@login_required
@requiere_rol('bibliotecario')
def api_validar_prestamo():
    """Endpoint historico (cedula + isbn en una sola llamada). Se conserva."""
    cedula = (request.args.get('cedula') or '').strip()
    isbn = (request.args.get('isbn') or '').strip()

    if not _cedula_valida(cedula) or not _isbn_valido(isbn):
        return jsonify({
            'codigo_resultado': -1,
            'mensaje': 'Ingresa una cédula (10 dígitos) y un ISBN (13 dígitos) válidos.',
        })

    resultado = _validar_prestamo_bd(cedula, isbn)
    if resultado is None:
        return jsonify({'codigo_resultado': -1, 'mensaje': 'No se pudo validar el préstamo.'})

    respuesta = {'codigo_resultado': resultado.codigo_resultado, 'mensaje': resultado.mensaje}

    if resultado.codigo_resultado == 0:
        estudiante = Estudiante.query.filter_by(cedula=cedula).first()
        libro = Libro.query.filter_by(isbn=isbn).first()
        respuesta['estudiante'] = f'{estudiante.nombres} {estudiante.apellidos}' if estudiante else None
        respuesta['libro'] = libro.titulo if libro else None

    return jsonify(respuesta)
