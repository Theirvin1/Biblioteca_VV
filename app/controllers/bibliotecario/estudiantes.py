from flask import jsonify, redirect, render_template, request, url_for, flash
from flask_login import login_required
from werkzeug.security import generate_password_hash

from app.controllers.bibliotecario import bibliotecario_bp
from app.controllers.decoradores import requiere_rol
from app.extensions import db
from app.forms import EditarEstudianteForm, EstudianteForm
from app.models import Carrera, Estudiante, Usuario
from app.paginacion import (
    POR_PAGINA, argumentos_activos, entero_filtro, id_nuevo, opcion_filtro,
    pagina_actual, texto_filtro,
)
from app.seguridad import generar_password_temporal, respuesta_sin_cache
from app.validators import es_cedula_ecuatoriana_valida


@bibliotecario_bp.route('/estudiantes')
@login_required
@requiere_rol('bibliotecario')
def listado_estudiantes():
    termino = texto_filtro(request, 'q')
    estado = opcion_filtro(request, 'estado', ('activo', 'suspendido'))
    carrera_id = entero_filtro(request, 'carrera')

    consulta = Estudiante.query
    if termino:
        patron = f'%{termino}%'
        consulta = consulta.filter(db.or_(
            Estudiante.cedula.ilike(patron),
            Estudiante.nombres.ilike(patron),
            Estudiante.apellidos.ilike(patron),
            (Estudiante.nombres + ' ' + Estudiante.apellidos).ilike(patron),
            Estudiante.correo.ilike(patron),
        ))
    if estado:
        consulta = consulta.filter(Estudiante.estado == estado)
    if carrera_id:
        consulta = consulta.filter(Estudiante.carrera_id == carrera_id)

    # Lo mas reciente primero: el ultimo estudiante registrado encabeza la lista.
    paginacion = consulta.order_by(Estudiante.id.desc()).paginate(
        page=pagina_actual(request), per_page=POR_PAGINA, error_out=False
    )

    return render_template(
        'bibliotecario/estudiantes_lista.html',
        paginacion=paginacion,
        estudiantes=paginacion.items,
        carreras=Carrera.query.order_by(Carrera.nombre).all(),
        filtros={'q': termino, 'estado': estado, 'carrera': carrera_id},
        argumentos=argumentos_activos(q=termino, estado=estado, carrera=carrera_id),
        nuevo_id=id_nuevo(request),
    )


@bibliotecario_bp.route('/estudiantes/nuevo', methods=['GET', 'POST'])
@login_required
@requiere_rol('bibliotecario')
def nuevo_estudiante():
    form = EstudianteForm()
    form.carrera_id.choices = [(0, '-- Selecciona una carrera --')] + [
        (carrera.id, f'{carrera.nombre} ({carrera.facultad.nombre})')
        for carrera in Carrera.query.join(Carrera.facultad).order_by(Carrera.nombre)
    ]

    if form.validate_on_submit():
        # El correo se normaliza ANTES de buscar duplicados y no solo al
        # guardar: si no, " ana@uteq.edu.ec " no encontraba al ana@uteq.edu.ec
        # ya registrado, se insertaba ya recortado y chocaba con el UNIQUE de
        # la columna, dando un error generico en vez del mensaje de duplicado.
        correo = form.correo.data.strip()

        if Estudiante.query.filter_by(cedula=form.cedula.data).first():
            flash('Ya existe un estudiante registrado con esa cédula.', 'danger')
            return render_template('bibliotecario/estudiantes_nuevo.html', form=form)

        if Estudiante.query.filter_by(correo=correo).first():
            flash('Ya existe un estudiante registrado con ese correo.', 'danger')
            return render_template('bibliotecario/estudiantes_nuevo.html', form=form)

        if Usuario.query.filter_by(username=form.cedula.data).first():
            flash('Ya existe una cuenta de usuario con esa cédula.', 'danger')
            return render_template('bibliotecario/estudiantes_nuevo.html', form=form)

        password_temporal = generar_password_temporal()

        usuario = Usuario(
            username=form.cedula.data,
            password_hash=generate_password_hash(password_temporal),
            rol='estudiante',
            debe_cambiar_password=True,
        )
        db.session.add(usuario)
        db.session.flush()

        estudiante = Estudiante(
            cedula=form.cedula.data,
            nombres=form.nombres.data.strip(),
            apellidos=form.apellidos.data.strip(),
            correo=correo,
            telefono=(form.telefono.data or '').strip() or None,
            carrera_id=form.carrera_id.data,
            fecha_nacimiento=form.fecha_nacimiento.data,
            genero=form.genero.data or None,
            usuario_id=usuario.id,
        )
        db.session.add(estudiante)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash('No se pudo registrar el estudiante. Verifica los datos ingresados.', 'danger')
            return render_template('bibliotecario/estudiantes_nuevo.html', form=form)

        # Se renderiza directamente la pantalla de credenciales (sin redirect):
        # la clave temporal solo existe en memoria durante esta peticion, no se
        # guarda en BD ni en session, y no hay ruta GET que pueda recuperarla.
        # El enlace "Ver en el listado" de esa pantalla conserva ?nuevo=<id>
        # para seguir marcando el registro recien creado, y su JS reemplaza la
        # URL del POST por ese GET para que un F5 no reenvie el formulario.
        # La respuesta va con no-store: ningun cache debe guardar la clave.
        return respuesta_sin_cache(render_template(
            'bibliotecario/estudiantes_credenciales.html',
            usuario=usuario,
            estudiante=estudiante,
            password_temporal=password_temporal,
        ))

    return render_template('bibliotecario/estudiantes_nuevo.html', form=form)


@bibliotecario_bp.route('/estudiantes/<int:estudiante_id>/editar', methods=['GET', 'POST'])
@login_required
@requiere_rol('bibliotecario')
def editar_estudiante(estudiante_id):
    """
    Edicion administrativa de un estudiante YA registrado: nombres,
    apellidos, carrera, correo y telefono. La cedula NUNCA se toca aqui:
    EditarEstudianteForm no tiene ese campo, asi que no hay ningun valor de
    cedula que pueda llegar por POST y usarse para nada. `estudiante.cedula`
    se sigue leyendo del registro existente en la plantilla.
    """
    estudiante = db.session.get(Estudiante, estudiante_id)
    if estudiante is None:
        flash('El estudiante indicado no existe.', 'danger')
        return redirect(url_for('bibliotecario.listado_estudiantes'))

    form = EditarEstudianteForm(obj=estudiante)
    form.carrera_id.choices = [(0, '-- Selecciona una carrera --')] + [
        (carrera.id, f'{carrera.nombre} ({carrera.facultad.nombre})')
        for carrera in Carrera.query.join(Carrera.facultad).order_by(Carrera.nombre)
    ]

    if form.validate_on_submit():
        # Mismo motivo que en nuevo_estudiante(): normalizar ANTES de buscar
        # duplicados. `Estudiante.id != estudiante.id` deja que el propio
        # correo del estudiante no se marque como "duplicado" de si mismo.
        correo = form.correo.data.strip()

        duplicado = Estudiante.query.filter(
            Estudiante.correo == correo, Estudiante.id != estudiante.id
        ).first()
        if duplicado:
            flash('Ya existe otro estudiante registrado con ese correo.', 'danger')
            return render_template(
                'bibliotecario/estudiantes_editar.html', form=form, estudiante=estudiante
            )

        estudiante.nombres = form.nombres.data.strip()
        estudiante.apellidos = form.apellidos.data.strip()
        estudiante.correo = correo
        estudiante.telefono = (form.telefono.data or '').strip() or None
        estudiante.carrera_id = form.carrera_id.data
        # cedula, estado y usuario_id no forman parte de este formulario:
        # quedan exactamente como estaban.

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash('No se pudo actualizar el estudiante. Verifica los datos ingresados.', 'danger')
            return render_template(
                'bibliotecario/estudiantes_editar.html', form=form, estudiante=estudiante
            )

        flash('Estudiante actualizado correctamente.', 'success')
        return redirect(url_for('bibliotecario.listado_estudiantes'))

    return render_template('bibliotecario/estudiantes_editar.html', form=form, estudiante=estudiante)


@bibliotecario_bp.route('/api/estudiantes/verificar-cedula')
@login_required
@requiere_rol('bibliotecario')
def api_verificar_cedula():
    cedula = (request.args.get('cedula') or '').strip()
    if not es_cedula_ecuatoriana_valida(cedula):
        return jsonify({'valida': False, 'existe': False, 'mensaje': 'La cédula ingresada no es válida.'})

    estudiante = Estudiante.query.filter_by(cedula=cedula).first()
    if estudiante:
        return jsonify({
            'valida': True,
            'existe': True,
            'mensaje': f'Ya existe un estudiante registrado: {estudiante.nombres} {estudiante.apellidos}.',
        })

    return jsonify({'valida': True, 'existe': False, 'mensaje': 'Cédula disponible.'})
