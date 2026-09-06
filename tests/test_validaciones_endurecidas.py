"""
Pruebas de las validaciones endurecidas tras la auditoria de entradas.

Cubren tres cosas distintas, que conviene no mezclar al leerlas:

1. Backend como proteccion real: longitud del autor, año de publicacion
   alineado con el CHECK de la BD, observacion de la devolucion por lote
   (que NO pasa por WTForms) y normalizacion del correo.
2. Robustez de parametros GET: una pagina absurda no debe reventar.
3. Atributos UX del HTML: maxlength/inputmode que impiden escribir de mas.
   Se comprueban porque son justamente los que se pierden sin querer al
   editar una plantilla; nunca sustituyen a los del punto 1.

Todos los formularios llevan `novalidate`, asi que el navegador no bloquea
nada: cada caso invalido de este archivo llega de verdad al servidor.
"""
import re
from datetime import date, timedelta

import pytest
from flask import Flask, request as peticion_actual

from app.models import (
    Autor, CategoriaLibro, ConfiguracionSistema, Devolucion, Editorial,
    Ejemplar, Estudiante, Libro, Prestamo,
)
from app.paginacion import MAX_PAGINA, pagina_actual
from app.validators import ANIO_MINIMO_PUBLICACION


def _etiqueta_input(html, id_input):
    """Devuelve la etiqueta <input> completa con ese id (para revisar sus atributos)."""
    patron = r'<input[^>]*\bid="' + re.escape(id_input) + r'"[^>]*>'
    encontrado = re.search(patron, html)
    assert encontrado, 'No se encontro el input con id="{}" en la pantalla.'.format(id_input)
    return encontrado.group(0)


@pytest.fixture
def bibliotecario_logueado(login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')
    return usuario_bibliotecario


@pytest.fixture
def catalogo_base(db):
    """Editorial, categoria y autor minimos para poder registrar un libro."""
    editorial = Editorial(nombre='Editorial Endurecida VV')
    categoria = CategoriaLibro(nombre='Categoria Endurecida VV')
    autor = Autor(nombres='Autor', apellidos='De Prueba')
    db.session.add_all([editorial, categoria, autor])
    db.session.commit()
    return {'editorial': editorial, 'categoria': categoria, 'autor': autor}


@pytest.fixture
def prestamo_devolvible(db, client, bibliotecario_logueado, carrera_prueba):
    """
    Un prestamo activo listo para devolver, creado por la ruta real.

    Devuelve el Prestamo. Necesita database/setup.sql (validar_prestamo,
    generar_codigo_prestamo y los triggers de stock/ejemplar).
    """
    db.session.add_all([
        ConfiguracionSistema(clave='plazo_prestamo_dias', valor='7'),
        ConfiguracionSistema(clave='multa_diaria', valor='0.50'),
        ConfiguracionSistema(clave='max_prestamos_activos', valor='5'),
    ])

    estudiante = Estudiante(
        cedula='0912345678',
        nombres='Ana',
        apellidos='Lopez',
        correo='ana.lopez@uteq.edu.ec',
        carrera_id=carrera_prueba.id,
        fecha_nacimiento=date(2003, 5, 20),
    )
    editorial = Editorial(nombre='Editorial Devolucion VV')
    categoria = CategoriaLibro(nombre='Categoria Devolucion VV')
    db.session.add_all([estudiante, editorial, categoria])
    db.session.commit()

    libro = Libro(
        isbn='9780306406157',
        titulo='Libro devolucion',
        editorial_id=editorial.id,
        categoria_id=categoria.id,
        stock_total=1,
        stock_disponible=1,
    )
    db.session.add(libro)
    db.session.flush()
    db.session.add(Ejemplar(
        libro_id=libro.id, codigo_ejemplar='EJ-OBS-0001', fecha_adquisicion=date.today(),
    ))
    db.session.commit()

    client.post('/bibliotecario/prestamos/nuevo', data={
        'cedula': '0912345678',
        'isbns': '9780306406157',
        'observaciones': '',
    }, follow_redirects=True)

    return Prestamo.query.one()


def _datos_libro(catalogo, **overrides):
    datos = {
        'isbn': '9780306406157',  # ISBN-13 con digito verificador valido
        'titulo': 'Libro para validaciones',
        'editorial_nombre': 'Editorial Endurecida VV',
        'categoria_id': str(catalogo['categoria'].id),
        'idioma': 'Español',
        'stock_inicial': '1',
        'autores_ids': str(catalogo['autor'].id),
    }
    datos.update(overrides)
    return datos


def _datos_estudiante(**overrides):
    datos = {
        'cedula': '1710034065',  # cedula ecuatoriana con digito verificador valido
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


# ----------------------------------------------------- autor nuevo (el 500)

def test_autor_con_nombres_muy_largos_no_produce_500_ni_se_guarda(
    client, db, bibliotecario_logueado
):
    """
    Antes: >100 caracteres llegaban al INSERT contra un VARCHAR(100),
    PostgreSQL rechazaba la escritura y nadie atrapaba el error -> 500.
    Ahora se responde 400 con un mensaje y no se escribe nada.
    """
    respuesta = client.post('/bibliotecario/api/autores', json={
        'nombres': 'A' * 150,
        'apellidos': 'Perez',
    })

    assert respuesta.status_code == 400
    assert '100 caracteres' in respuesta.get_json()['error']
    assert Autor.query.count() == 0


def test_autor_con_apellidos_muy_largos_tampoco_se_guarda(client, db, bibliotecario_logueado):
    respuesta = client.post('/bibliotecario/api/autores', json={
        'nombres': 'Ana',
        'apellidos': 'B' * 101,  # justo un caracter por encima del limite
    })

    assert respuesta.status_code == 400
    assert Autor.query.count() == 0


def test_autor_de_exactamente_100_caracteres_si_se_guarda(client, db, bibliotecario_logueado):
    """El limite es inclusivo: 100 caracteres caben en la columna."""
    respuesta = client.post('/bibliotecario/api/autores', json={
        'nombres': 'A' * 100,
        'apellidos': 'Perez',
    })

    assert respuesta.status_code == 201
    assert Autor.query.count() == 1


def test_autor_valido_sigue_funcionando(client, db, bibliotecario_logueado):
    respuesta = client.post('/bibliotecario/api/autores', json={
        'nombres': 'Gabriel',
        'apellidos': 'García Márquez',
    })

    assert respuesta.status_code == 201
    datos = respuesta.get_json()
    assert datos['nombre'] == 'Gabriel García Márquez'
    assert Autor.query.count() == 1

    # Pedir el mismo autor otra vez lo reutiliza en vez de duplicarlo.
    repetido = client.post('/bibliotecario/api/autores', json={
        'nombres': 'Gabriel',
        'apellidos': 'García Márquez',
    })
    assert repetido.status_code == 200
    assert repetido.get_json()['id'] == datos['id']
    assert Autor.query.count() == 1


# --------------------------------- autor nuevo (tipos del JSON manipulado)

@pytest.mark.parametrize('nombres_invalidos', [
    123,            # numero
    12.5,           # decimal
    True,           # booleano (isinstance(True, str) es False)
    ['Ana'],        # lista
    {'a': 'Ana'},   # objeto
])
def test_autor_con_nombres_no_textuales_da_400_y_no_500(
    client, db, bibliotecario_logueado, nombres_invalidos
):
    """
    Un JSON manipulado con un valor no textual reventaba en el .strip() con
    AttributeError, que salia como error 500 con traceback.
    """
    respuesta = client.post('/bibliotecario/api/autores', json={
        'nombres': nombres_invalidos,
        'apellidos': 'Perez',
    })

    assert respuesta.status_code == 400
    assert 'texto' in respuesta.get_json()['error']
    assert Autor.query.count() == 0


@pytest.mark.parametrize('apellidos_invalidos', [123, ['Perez'], {'a': 'Perez'}, False])
def test_autor_con_apellidos_no_textuales_da_400_y_no_500(
    client, db, bibliotecario_logueado, apellidos_invalidos
):
    respuesta = client.post('/bibliotecario/api/autores', json={
        'nombres': 'Ana',
        'apellidos': apellidos_invalidos,
    })

    assert respuesta.status_code == 400
    assert 'texto' in respuesta.get_json()['error']
    assert Autor.query.count() == 0


def test_autor_no_convierte_numeros_a_texto(client, db, bibliotecario_logueado):
    """
    Se rechaza el tipo, no se convierte: un 123 no debe colarse como el
    nombre "123" (que ademas fallaria despues en es_solo_letras, pero con
    otro mensaje y por otra razon).
    """
    respuesta = client.post('/bibliotecario/api/autores', json={
        'nombres': 12345678,
        'apellidos': 87654321,
    })

    assert respuesta.status_code == 400
    assert 'texto' in respuesta.get_json()['error']
    assert Autor.query.filter_by(nombres='12345678').count() == 0
    assert Autor.query.count() == 0


def test_autor_con_cuerpo_json_que_no_es_objeto_da_400(client, db, bibliotecario_logueado):
    """Un array o un escalar en la raiz no tiene .get(): mismo AttributeError."""
    for cuerpo in ([1, 2, 3], 'Ana Perez', 42):
        respuesta = client.post('/bibliotecario/api/autores', json=cuerpo)
        assert respuesta.status_code == 400, cuerpo
        assert 'error' in respuesta.get_json()

    assert Autor.query.count() == 0


def test_autor_sin_campos_sigue_dando_el_mensaje_de_obligatorios(
    client, db, bibliotecario_logueado
):
    """La respuesta para campos ausentes no cambia: sigue siendo "obligatorios"."""
    respuesta = client.post('/bibliotecario/api/autores', json={})

    assert respuesta.status_code == 400
    assert 'obligatorios' in respuesta.get_json()['error']


# ------------------------------------------------------ año de publicacion

def test_anio_publicacion_1799_lo_rechaza_el_backend(
    client, db, bibliotecario_logueado, catalogo_base
):
    """
    1799 pasaba WTForms (minimo 1000) y lo rechazaba despues
    chk_libros_anio_publicacion (BETWEEN 1800 ...), dejando un mensaje
    generico. Ahora lo rechaza el formulario con su propio mensaje.
    """
    respuesta = client.post(
        '/bibliotecario/libros/nuevo',
        data=_datos_libro(catalogo_base, anio_publicacion='1799'),
    )

    assert respuesta.status_code == 200
    assert 'año de publicación válido' in respuesta.get_data(as_text=True)
    assert Libro.query.count() == 0


def test_anio_publicacion_actual_si_se_acepta(
    client, db, bibliotecario_logueado, catalogo_base
):
    respuesta = client.post(
        '/bibliotecario/libros/nuevo',
        data=_datos_libro(catalogo_base, anio_publicacion=str(date.today().year)),
    )

    assert respuesta.status_code == 302
    assert Libro.query.count() == 1


def test_anio_publicacion_minimo_1800_se_acepta(
    client, db, bibliotecario_logueado, catalogo_base
):
    """El limite inferior es inclusivo y coincide con el CHECK de la BD."""
    respuesta = client.post(
        '/bibliotecario/libros/nuevo',
        data=_datos_libro(catalogo_base, anio_publicacion=str(ANIO_MINIMO_PUBLICACION)),
    )

    assert respuesta.status_code == 302
    assert Libro.query.one().anio_publicacion == ANIO_MINIMO_PUBLICACION


# ------------------------------------------------------------------ correo

def test_correo_con_espacios_se_normaliza_al_guardar(
    client, db, bibliotecario_logueado, carrera_prueba
):
    respuesta = client.post('/bibliotecario/estudiantes/nuevo', data=_datos_estudiante(
        correo='   maria.perez@uteq.edu.ec  ',
        carrera_id=str(carrera_prueba.id),
    ))

    assert respuesta.status_code == 200
    assert 'Estudiante registrado correctamente' in respuesta.get_data(as_text=True)
    assert Estudiante.query.one().correo == 'maria.perez@uteq.edu.ec'


def test_correo_con_espacios_se_detecta_como_duplicado(
    client, db, bibliotecario_logueado, carrera_prueba
):
    """
    El duplicado se busca con el correo ya normalizado: antes, el mismo
    correo con espacios esquivaba esta comprobacion y chocaba despues contra
    el UNIQUE de la columna, mostrando un mensaje generico.
    """
    primero = client.post('/bibliotecario/estudiantes/nuevo', data=_datos_estudiante(
        carrera_id=str(carrera_prueba.id),
    ))
    assert 'Estudiante registrado correctamente' in primero.get_data(as_text=True)

    segundo = client.post('/bibliotecario/estudiantes/nuevo', data=_datos_estudiante(
        cedula='0912345675',  # otra cedula valida: el unico choque debe ser el correo
        correo='  maria.perez@uteq.edu.ec ',
        carrera_id=str(carrera_prueba.id),
    ))

    assert segundo.status_code == 200
    assert 'Ya existe un estudiante registrado con ese correo' in segundo.get_data(as_text=True)
    assert Estudiante.query.count() == 1


# -------------------------------------------------------------- paginacion

@pytest.mark.parametrize('valor_page', ['abc', '-5', '0', '99999999999999999999', '1e9'])
def test_page_invalido_o_enorme_no_rompe_los_listados(
    client, bibliotecario_logueado, valor_page
):
    """
    Un entero por encima del rango de bigint llegaba tal cual al OFFSET y
    PostgreSQL respondia con un error -> 500 cambiando solo la URL.
    """
    rutas = ('/bibliotecario/libros', '/bibliotecario/estudiantes', '/bibliotecario/prestamos')
    for ruta in rutas:
        respuesta = client.get('{}?page={}'.format(ruta, valor_page))
        assert respuesta.status_code == 200, '{}?page={}'.format(ruta, valor_page)


def test_page_enorme_tambien_es_seguro_en_los_reportes(client, login, usuario_gerente):
    """Los reportes paginan con un LIMIT/OFFSET propio (paginar_select)."""
    login('test_gerente', 'ClaveSegura123')

    for tipo in ('prestamos-activos', 'multas-pendientes', 'historial-movimientos'):
        respuesta = client.get('/gerente/reportes/{}?page=99999999999999999999'.format(tipo))
        assert respuesta.status_code == 200, tipo


def test_page_queda_limitado_al_maximo():
    """La pagina se recorta a MAX_PAGINA en vez de propagarse a la consulta."""
    aplicacion = Flask(__name__)

    with aplicacion.test_request_context('/?page={}'.format(MAX_PAGINA * 1000)):
        assert pagina_actual(peticion_actual) == MAX_PAGINA

    with aplicacion.test_request_context('/?page={}'.format(MAX_PAGINA)):
        assert pagina_actual(peticion_actual) == MAX_PAGINA

    with aplicacion.test_request_context('/?page=abc'):
        assert pagina_actual(peticion_actual) == 1

    with aplicacion.test_request_context('/?page=-5'):
        assert pagina_actual(peticion_actual) == 1

    # La paginacion normal no cambia.
    with aplicacion.test_request_context('/?page=3'):
        assert pagina_actual(peticion_actual) == 3


# ------------------------------------------------- atributos UX del HTML

def test_telefono_tiene_maxlength_e_inputmode(client, bibliotecario_logueado):
    """Sin maxlength se podian teclear digitos sin limite (el backend igual los rechazaba)."""
    html = client.get('/bibliotecario/estudiantes/nuevo').get_data(as_text=True)
    etiqueta = _etiqueta_input(html, 'telefono')

    assert 'maxlength="10"' in etiqueta
    assert 'inputmode="numeric"' in etiqueta
    # Un telefono es un identificador, no una cantidad: nunca type="number".
    assert 'type="number"' not in etiqueta


def test_cedula_conserva_maxlength_y_gana_inputmode(client, bibliotecario_logueado):
    html = client.get('/bibliotecario/estudiantes/nuevo').get_data(as_text=True)
    etiqueta = _etiqueta_input(html, 'cedula')

    assert 'maxlength="10"' in etiqueta
    assert 'inputmode="numeric"' in etiqueta


def test_isbn_conserva_maxlength_y_gana_inputmode(client, bibliotecario_logueado):
    html = client.get('/bibliotecario/libros/nuevo').get_data(as_text=True)
    etiqueta = _etiqueta_input(html, 'isbn')

    assert 'maxlength="13"' in etiqueta
    assert 'inputmode="numeric"' in etiqueta


def test_cedula_del_prestamo_conserva_sus_atributos(client, bibliotecario_logueado):
    """La pantalla de prestamo ya los tenia: esta prueba evita perderlos."""
    html = client.get('/bibliotecario/prestamos/nuevo').get_data(as_text=True)
    etiqueta = _etiqueta_input(html, 'cedula')

    assert 'maxlength="10"' in etiqueta
    assert 'inputmode="numeric"' in etiqueta


def test_inputs_de_autor_nuevo_tienen_maxlength(client, bibliotecario_logueado):
    html = client.get('/bibliotecario/libros/nuevo').get_data(as_text=True)

    assert 'maxlength="100"' in _etiqueta_input(html, 'nuevo-autor-nombres')
    assert 'maxlength="100"' in _etiqueta_input(html, 'nuevo-autor-apellidos')


def test_anio_publicacion_expone_min_y_max_calculados(client, bibliotecario_logueado):
    html = client.get('/bibliotecario/libros/nuevo').get_data(as_text=True)
    etiqueta = _etiqueta_input(html, 'anio_publicacion')

    assert 'min="{}"'.format(ANIO_MINIMO_PUBLICACION) in etiqueta
    # El maximo se calcula en cada render: no puede quedarse en un año viejo.
    assert 'max="{}"'.format(date.today().year) in etiqueta


def test_correo_usa_type_email(client, bibliotecario_logueado):
    html = client.get('/bibliotecario/estudiantes/nuevo').get_data(as_text=True)
    etiqueta = _etiqueta_input(html, 'correo')

    assert 'type="email"' in etiqueta
    assert 'maxlength="150"' in etiqueta  # igual que la columna VARCHAR(150)


# -------------------------------------------------- fecha de nacimiento

def test_fecha_nacimiento_expone_min_y_max_coherentes_con_la_regla(
    client, bibliotecario_logueado
):
    """Los limites del date picker se derivan del mismo EdadEntre(15, 100) del servidor."""
    html = client.get('/bibliotecario/estudiantes/nuevo').get_data(as_text=True)
    etiqueta = _etiqueta_input(html, 'fecha_nacimiento')

    hoy = date.today()
    assert 'type="date"' in etiqueta
    assert 'max="{}"'.format(hoy.replace(year=hoy.year - 15).isoformat()) in etiqueta
    assert 'min="{}"'.format(hoy.replace(year=hoy.year - 100).isoformat()) in etiqueta


def test_fecha_nacimiento_mantiene_sus_reglas_de_backend(
    client, db, bibliotecario_logueado, carrera_prueba
):
    """
    El min/max del HTML es solo ayuda visual (los forms llevan novalidate):
    el servidor sigue rechazando fecha futura y edades fuera de 15-100.
    """
    hoy = date.today()

    futura = client.post('/bibliotecario/estudiantes/nuevo', data=_datos_estudiante(
        fecha_nacimiento=(hoy + timedelta(days=1)).isoformat(),
        carrera_id=str(carrera_prueba.id),
    ))
    assert 'no puede ser futura' in futura.get_data(as_text=True)

    demasiado_joven = client.post('/bibliotecario/estudiantes/nuevo', data=_datos_estudiante(
        fecha_nacimiento=hoy.replace(year=hoy.year - 14).isoformat(),
        carrera_id=str(carrera_prueba.id),
    ))
    assert 'entre 15 y 100 años' in demasiado_joven.get_data(as_text=True)

    demasiado_mayor = client.post('/bibliotecario/estudiantes/nuevo', data=_datos_estudiante(
        fecha_nacimiento=hoy.replace(year=hoy.year - 101).isoformat(),
        carrera_id=str(carrera_prueba.id),
    ))
    assert 'entre 15 y 100 años' in demasiado_mayor.get_data(as_text=True)

    assert Estudiante.query.count() == 0

    # El limite inferior exacto (15 años recien cumplidos) si se acepta.
    justo_15 = client.post('/bibliotecario/estudiantes/nuevo', data=_datos_estudiante(
        fecha_nacimiento=hoy.replace(year=hoy.year - 15).isoformat(),
        carrera_id=str(carrera_prueba.id),
    ))
    assert 'Estudiante registrado correctamente' in justo_15.get_data(as_text=True)


# --------------------------------- observacion de la devolucion por lote

@pytest.mark.requiere_setup_sql
def test_observacion_manipulada_por_post_no_supera_el_limite(
    client, db, prestamo_devolvible
):
    """
    Los campos por libro de la devolucion por lote se leen de request.form,
    no de WTForms: el maxlength="500" del HTML se salta con cualquier cliente
    HTTP. El limite real lo aplica ahora el controlador.
    """
    prestamo = prestamo_devolvible

    respuesta = client.post(
        '/bibliotecario/devoluciones/operacion/{}'.format(prestamo.id),
        data={
            'prestamos': str(prestamo.id),
            'estado_{}'.format(prestamo.id): 'bueno',
            'observacion_{}'.format(prestamo.id): 'X' * 501,
        },
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    assert 'no puede superar los 500 caracteres' in respuesta.get_data(as_text=True)
    # Rollback completo: ni la devolucion ni el cambio de estado se guardaron.
    assert Devolucion.query.count() == 0
    assert Prestamo.query.one().estado != 'devuelto'


@pytest.mark.requiere_setup_sql
def test_observacion_dentro_del_limite_se_guarda_normal(client, db, prestamo_devolvible):
    """Contraparte del caso anterior: 500 caracteres exactos siguen funcionando."""
    prestamo = prestamo_devolvible
    observacion = 'X' * 500

    respuesta = client.post(
        '/bibliotecario/devoluciones/operacion/{}'.format(prestamo.id),
        data={
            'prestamos': str(prestamo.id),
            'estado_{}'.format(prestamo.id): 'bueno',
            'observacion_{}'.format(prestamo.id): observacion,
        },
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    assert Devolucion.query.one().observaciones == observacion
