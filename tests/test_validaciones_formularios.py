"""
Pruebas de validacion de formularios.

Confirman que datos con formato invalido son rechazados por los
validadores del servidor (WTForms) antes de intentar escribir en la
base de datos o de llamar a validar_prestamo()/generar_codigo_prestamo().
No dependen de database/setup.sql.

Las pruebas de "creacion" (registrar estudiante, registrar libro) cubren
la validacion completa (digito verificador de cedula/ISBN, nombres solo
con letras, correo, telefono, fecha de nacimiento). Las pruebas de
"busqueda" (registrar prestamo) solo cubren formato, a proposito: ver la
nota en app/forms.py sobre por que PrestamoForm no exige el digito
verificador.
"""
from datetime import date

from app.models import Autor, CategoriaLibro


def _datos_estudiante_validos(**overrides):
    datos = {
        'cedula': '1710034065',  # cedula ecuatoriana de prueba, digito verificador valido
        'nombres': 'Maria Fernanda',
        'apellidos': 'Perez Lopez',
        'correo': 'maria.perez@uteq.edu.ec',
        'telefono': '0991234567',
        'carrera_id': '0',
        'fecha_nacimiento': '2000-05-15',
        'genero': '',
    }
    datos.update(overrides)
    return datos


def _datos_libro_validos(**overrides):
    datos = {
        'isbn': '9780306406157',  # ISBN-13 con digito verificador valido
        'titulo': 'Libro de prueba valido',
        'editorial_nombre': 'Editorial de prueba',
        'categoria_id': '0',
        'idioma': 'Español',
        'stock_inicial': '1',
        'autores_ids': '',
    }
    datos.update(overrides)
    return datos


def test_registrar_libro_isbn_invalido(client, login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')

    respuesta = client.post('/bibliotecario/libros/nuevo', data=_datos_libro_validos(
        isbn='123',  # debe tener 13 digitos
    ))

    # No redirige: el formulario se vuelve a mostrar con el error.
    assert respuesta.status_code == 200
    assert '13 dígitos' in respuesta.get_data(as_text=True)


def test_registrar_libro_isbn_digito_verificador_invalido(client, login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')

    respuesta = client.post('/bibliotecario/libros/nuevo', data=_datos_libro_validos(
        isbn='9780306406150',  # 13 digitos, pero el digito verificador no coincide
    ))

    assert respuesta.status_code == 200
    assert 'no es válido' in respuesta.get_data(as_text=True)


def test_registrar_libro_titulo_solo_simbolos(client, login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')

    respuesta = client.post('/bibliotecario/libros/nuevo', data=_datos_libro_validos(
        titulo='!!! 12345',
    ))

    assert respuesta.status_code == 200
    assert 'solo números o símbolos' in respuesta.get_data(as_text=True)


def test_registrar_libro_valido_exitoso(client, login, usuario_bibliotecario, db):
    login('test_bibliotecario', 'ClaveSegura123')

    autor = Autor(nombres='Gabriel', apellidos='Garcia Marquez')
    categoria = CategoriaLibro(nombre='Categoría de prueba VV')
    db.session.add_all([autor, categoria])
    db.session.commit()

    respuesta = client.post('/bibliotecario/libros/nuevo', data=_datos_libro_validos(
        categoria_id=str(categoria.id),
        autores_ids=str(autor.id),
    ))

    assert respuesta.status_code == 302
    # El redirect agrega ?nuevo=<id> para marcar el registro recien creado.
    assert respuesta.headers['Location'].startswith('/bibliotecario/libros')

    listado = client.get('/bibliotecario/libros')
    assert 'Libro de prueba valido' in listado.get_data(as_text=True)


def test_registrar_prestamo_cedula_invalida(client, login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')

    respuesta = client.post('/bibliotecario/prestamos/nuevo', data={
        'cedula': '123',  # debe tener 10 digitos
        'isbn': '9789978000000',
        'observaciones': '',
    })

    assert respuesta.status_code == 200
    assert '10 dígitos' in respuesta.get_data(as_text=True)


def test_registrar_estudiante_cedula_invalida(client, login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')

    respuesta = client.post('/bibliotecario/estudiantes/nuevo', data=_datos_estudiante_validos(
        cedula='1710034066',  # 10 digitos, provincia valida, pero digito verificador incorrecto
    ))

    assert respuesta.status_code == 200
    assert 'no es válida' in respuesta.get_data(as_text=True)


def test_registrar_estudiante_nombres_con_numeros(client, login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')

    respuesta = client.post('/bibliotecario/estudiantes/nuevo', data=_datos_estudiante_validos(
        nombres='Maria123',
    ))

    assert respuesta.status_code == 200
    assert 'solo pueden contener letras y espacios' in respuesta.get_data(as_text=True)


def test_registrar_estudiante_correo_invalido(client, login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')

    respuesta = client.post('/bibliotecario/estudiantes/nuevo', data=_datos_estudiante_validos(
        correo='esto-no-es-un-correo',
    ))

    assert respuesta.status_code == 200
    assert 'Ingresa un correo válido' in respuesta.get_data(as_text=True)


def test_registrar_estudiante_telefono_con_letras(client, login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')

    respuesta = client.post('/bibliotecario/estudiantes/nuevo', data=_datos_estudiante_validos(
        telefono='09ABCD1234',  # 10 caracteres, pero con letras
    ))

    assert respuesta.status_code == 200
    assert 'El teléfono debe contener exactamente 10 dígitos.' in respuesta.get_data(as_text=True)


def test_registrar_estudiante_telefono_9_digitos(client, login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')

    respuesta = client.post('/bibliotecario/estudiantes/nuevo', data=_datos_estudiante_validos(
        telefono='099123456',  # 9 digitos: menos de 10
    ))

    assert respuesta.status_code == 200
    assert 'El teléfono debe contener exactamente 10 dígitos.' in respuesta.get_data(as_text=True)


def test_registrar_estudiante_telefono_11_digitos(client, login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')

    respuesta = client.post('/bibliotecario/estudiantes/nuevo', data=_datos_estudiante_validos(
        telefono='09912345678',  # 11 digitos: mas de 10
    ))

    assert respuesta.status_code == 200
    assert 'El teléfono debe contener exactamente 10 dígitos.' in respuesta.get_data(as_text=True)


def test_registrar_estudiante_telefono_10_digitos_valido(client, login, usuario_bibliotecario, carrera_prueba):
    login('test_bibliotecario', 'ClaveSegura123')

    respuesta = client.post('/bibliotecario/estudiantes/nuevo', data=_datos_estudiante_validos(
        telefono='0991234567',  # exactamente 10 digitos
        carrera_id=str(carrera_prueba.id),
    ))

    # El registro exitoso ya no redirige: responde 200 con la pantalla de
    # credenciales temporales (usuario + clave que se muestra una sola vez).
    assert respuesta.status_code == 200
    assert 'Estudiante registrado correctamente' in respuesta.get_data(as_text=True)


def test_registrar_estudiante_fecha_nacimiento_futura(client, login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')

    fecha_futura = date.today().replace(year=date.today().year + 1)
    respuesta = client.post('/bibliotecario/estudiantes/nuevo', data=_datos_estudiante_validos(
        fecha_nacimiento=fecha_futura.isoformat(),
    ))

    assert respuesta.status_code == 200
    assert 'no puede ser futura' in respuesta.get_data(as_text=True)


def test_registrar_estudiante_edad_fuera_de_rango(client, login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')

    fecha_muy_reciente = date.today().replace(year=date.today().year - 5)
    respuesta = client.post('/bibliotecario/estudiantes/nuevo', data=_datos_estudiante_validos(
        fecha_nacimiento=fecha_muy_reciente.isoformat(),
    ))

    assert respuesta.status_code == 200
    assert 'entre 15 y 100 años' in respuesta.get_data(as_text=True)


def test_registrar_estudiante_valido_exitoso(client, login, usuario_bibliotecario, carrera_prueba):
    login('test_bibliotecario', 'ClaveSegura123')

    respuesta = client.post('/bibliotecario/estudiantes/nuevo', data=_datos_estudiante_validos(
        carrera_id=str(carrera_prueba.id),
    ))

    # El registro exitoso ya no redirige: responde 200 con la pantalla de
    # credenciales temporales (usuario + clave que se muestra una sola vez).
    assert respuesta.status_code == 200
    assert 'Estudiante registrado correctamente' in respuesta.get_data(as_text=True)

    listado = client.get('/bibliotecario/estudiantes')
    assert 'Maria Fernanda' in listado.get_data(as_text=True)
