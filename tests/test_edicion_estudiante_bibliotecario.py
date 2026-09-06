"""
Pruebas de la edicion administrativa de un estudiante por el bibliotecario
(bibliotecario.editar_estudiante).

Politica que se verifica aqui:
- El bibliotecario puede corregir nombres, apellidos, carrera, correo y
  telefono de un estudiante YA registrado.
- NUNCA puede cambiar la cedula desde esta pantalla: EditarEstudianteForm no
  tiene ese campo, asi que no hay ningun valor de cedula que un POST
  manipulado pueda usar.
- Tampoco toca Usuario (username/password/rol/activo): ese formulario ni
  siquiera existe en esta ruta.
"""
from werkzeug.security import generate_password_hash

from app.models import Estudiante, Usuario


def _login_bibliotecario(login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')
    return usuario_bibliotecario


def _datos_edicion(**overrides):
    datos = {
        'nombres': 'Maria Fernanda',
        'apellidos': 'Perez Lopez',
        'correo': 'maria.editada@uteq.edu.ec',
        'telefono': '0991234567',
        'carrera_id': '0',
    }
    datos.update(overrides)
    return datos


def _otra_carrera(db, facultad_id, nombre):
    from app.models import Carrera
    carrera = Carrera(nombre=nombre, facultad_id=facultad_id)
    db.session.add(carrera)
    db.session.commit()
    return carrera


def test_bibliotecario_puede_editar_nombres_y_apellidos(
    client, db, login, usuario_bibliotecario, usuario_estudiante, carrera_prueba
):
    _login_bibliotecario(login, usuario_bibliotecario)
    estudiante = usuario_estudiante.estudiante

    respuesta = client.post(
        f'/bibliotecario/estudiantes/{estudiante.id}/editar',
        data=_datos_edicion(
            nombres='Nombre Nuevo', apellidos='Apellido Nuevo',
            correo=estudiante.correo, carrera_id=str(carrera_prueba.id),
        ),
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    assert 'Estudiante actualizado correctamente' in respuesta.get_data(as_text=True)

    db.session.refresh(estudiante)
    assert estudiante.nombres == 'Nombre Nuevo'
    assert estudiante.apellidos == 'Apellido Nuevo'


def test_bibliotecario_puede_editar_carrera(
    client, db, login, usuario_bibliotecario, usuario_estudiante, carrera_prueba
):
    _login_bibliotecario(login, usuario_bibliotecario)
    estudiante = usuario_estudiante.estudiante
    nueva_carrera = _otra_carrera(db, carrera_prueba.facultad_id, 'Carrera Nueva VV')

    respuesta = client.post(
        f'/bibliotecario/estudiantes/{estudiante.id}/editar',
        data=_datos_edicion(
            nombres=estudiante.nombres, apellidos=estudiante.apellidos,
            correo=estudiante.correo, carrera_id=str(nueva_carrera.id),
        ),
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    db.session.refresh(estudiante)
    assert estudiante.carrera_id == nueva_carrera.id


def test_bibliotecario_puede_editar_correo(
    client, db, login, usuario_bibliotecario, usuario_estudiante, carrera_prueba
):
    _login_bibliotecario(login, usuario_bibliotecario)
    estudiante = usuario_estudiante.estudiante

    respuesta = client.post(
        f'/bibliotecario/estudiantes/{estudiante.id}/editar',
        data=_datos_edicion(
            nombres=estudiante.nombres, apellidos=estudiante.apellidos,
            correo='  nuevo.correo@uteq.edu.ec  ', carrera_id=str(carrera_prueba.id),
        ),
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    db.session.refresh(estudiante)
    assert estudiante.correo == 'nuevo.correo@uteq.edu.ec'  # normalizado (strip)


def test_bibliotecario_puede_editar_telefono(
    client, db, login, usuario_bibliotecario, usuario_estudiante, carrera_prueba
):
    _login_bibliotecario(login, usuario_bibliotecario)
    estudiante = usuario_estudiante.estudiante

    respuesta = client.post(
        f'/bibliotecario/estudiantes/{estudiante.id}/editar',
        data=_datos_edicion(
            nombres=estudiante.nombres, apellidos=estudiante.apellidos,
            correo=estudiante.correo, carrera_id=str(carrera_prueba.id),
            telefono='0987654321',
        ),
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    db.session.refresh(estudiante)
    assert estudiante.telefono == '0987654321'


def test_bibliotecario_puede_dejar_telefono_vacio(
    client, db, login, usuario_bibliotecario, usuario_estudiante, carrera_prueba
):
    """Telefono es opcional tambien en esta edicion: vacio debe borrarlo (NULL)."""
    _login_bibliotecario(login, usuario_bibliotecario)
    estudiante = usuario_estudiante.estudiante
    estudiante.telefono = '0991234567'
    db.session.commit()

    respuesta = client.post(
        f'/bibliotecario/estudiantes/{estudiante.id}/editar',
        data=_datos_edicion(
            nombres=estudiante.nombres, apellidos=estudiante.apellidos,
            correo=estudiante.correo, carrera_id=str(carrera_prueba.id),
            telefono='',
        ),
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    assert 'Estudiante actualizado correctamente' in respuesta.get_data(as_text=True)
    db.session.refresh(estudiante)
    assert estudiante.telefono is None


def test_bibliotecario_no_puede_editar_la_cedula(
    client, db, login, usuario_bibliotecario, usuario_estudiante, carrera_prueba
):
    """
    EditarEstudianteForm no tiene campo cedula: aunque el POST incluya uno,
    el formulario no lo lee y el controlador nunca lo usa. La cedula sigue
    siendo la del registro existente.
    """
    _login_bibliotecario(login, usuario_bibliotecario)
    estudiante = usuario_estudiante.estudiante
    cedula_original = estudiante.cedula

    respuesta = client.post(
        f'/bibliotecario/estudiantes/{estudiante.id}/editar',
        data=_datos_edicion(
            nombres=estudiante.nombres, apellidos=estudiante.apellidos,
            correo=estudiante.correo, carrera_id=str(carrera_prueba.id),
            cedula='9999999999',
        ),
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    db.session.refresh(estudiante)
    assert estudiante.cedula == cedula_original

    # El username de la cuenta (= cedula) tampoco se toco.
    usuario = Usuario.query.filter_by(id=usuario_estudiante.id).first()
    assert usuario.username == cedula_original

    # La cedula tampoco se puede colar como campo escondido: no aparece
    # ningun input editable con ese name en la pantalla de edicion.
    html = client.get(f'/bibliotecario/estudiantes/{estudiante.id}/editar').get_data(as_text=True)
    assert 'name="cedula"' not in html
    assert cedula_original in html  # se muestra, pero solo como texto/readonly


def test_correo_duplicado_se_rechaza_correctamente(
    client, db, login, usuario_bibliotecario, usuario_estudiante, carrera_prueba
):
    _login_bibliotecario(login, usuario_bibliotecario)
    estudiante = usuario_estudiante.estudiante

    otro_usuario = Usuario(
        username='0955555555', password_hash=generate_password_hash('x'), rol='estudiante',
    )
    db.session.add(otro_usuario)
    db.session.flush()
    otro_estudiante = Estudiante(
        cedula='0955555555', nombres='Otro', apellidos='Correo',
        correo='ocupado@uteq.edu.ec', carrera_id=carrera_prueba.id, usuario_id=otro_usuario.id,
    )
    db.session.add(otro_estudiante)
    db.session.commit()

    respuesta = client.post(
        f'/bibliotecario/estudiantes/{estudiante.id}/editar',
        data=_datos_edicion(
            nombres=estudiante.nombres, apellidos=estudiante.apellidos,
            correo='ocupado@uteq.edu.ec', carrera_id=str(carrera_prueba.id),
        ),
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    assert 'Ya existe otro estudiante registrado con ese correo' in respuesta.get_data(as_text=True)

    db.session.refresh(estudiante)
    assert estudiante.correo != 'ocupado@uteq.edu.ec'  # no se aplico el cambio


def test_conservar_el_propio_correo_no_se_detecta_como_duplicado(
    client, db, login, usuario_bibliotecario, usuario_estudiante, carrera_prueba
):
    """Editar otros campos sin tocar el correo no debe disparar el chequeo de duplicado."""
    _login_bibliotecario(login, usuario_bibliotecario)
    estudiante = usuario_estudiante.estudiante

    respuesta = client.post(
        f'/bibliotecario/estudiantes/{estudiante.id}/editar',
        data=_datos_edicion(
            nombres='Otro Nombre', apellidos=estudiante.apellidos,
            correo=estudiante.correo, carrera_id=str(carrera_prueba.id),
        ),
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    assert 'Estudiante actualizado correctamente' in respuesta.get_data(as_text=True)


def test_estudiante_no_puede_acceder_a_la_edicion_administrativa(
    client, db, login, usuario_estudiante
):
    """Reafirma la proteccion por rol desde el lado de la ruta del bibliotecario."""
    login('1234567899', 'ClaveSegura123')

    respuesta = client.get(
        f'/bibliotecario/estudiantes/{usuario_estudiante.estudiante.id}/editar'
    )
    assert respuesta.status_code == 302


def test_gerente_no_puede_acceder_a_la_edicion_del_bibliotecario(
    client, db, login, usuario_gerente, usuario_estudiante
):
    """
    El gerente administra Usuario (estado/rol/password), no la ficha
    academica del estudiante: esta ruta sigue reservada al bibliotecario.
    """
    login('test_gerente', 'ClaveSegura123')

    respuesta = client.get(
        f'/bibliotecario/estudiantes/{usuario_estudiante.estudiante.id}/editar'
    )
    assert respuesta.status_code == 302
