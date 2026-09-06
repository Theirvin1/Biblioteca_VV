"""
Pruebas de la subida de portada de libros.

Cubren: registrar un libro sin portada debe seguir funcionando igual que
antes de este cambio; registrar uno con portada valida debe guardar el
libro y la ruta de la portada; un archivo con extension invalida debe
rechazarse (sin crear el libro); y el catalogo del estudiante debe cargar
sin romperse aunque un libro no tenga portada (usa el placeholder).
"""
import io
import os

from app.models import Autor, CategoriaLibro, Editorial, Libro


def _borrar_si_existe(ruta_relativa_static):
    """Limpia los archivos que las pruebas escriben de verdad en disco,
    para no acumular imagenes de prueba entre corridas (ya estan
    ignoradas en git, pero no hace falta dejarlas en el disco tampoco)."""
    if not ruta_relativa_static:
        return
    ruta_absoluta = os.path.join('app', 'static', *ruta_relativa_static.split('/'))
    if os.path.isfile(ruta_absoluta):
        os.remove(ruta_absoluta)


def _datos_libro_validos(**overrides):
    datos = {
        'isbn': '9780306406157',
        'titulo': 'Libro de prueba con portada',
        'editorial_nombre': 'Editorial de prueba',
        'categoria_id': '0',
        'idioma': 'Español',
        'stock_inicial': '1',
        'autores_ids': '',
    }
    datos.update(overrides)
    return datos


def _autor_y_categoria(db):
    autor = Autor(nombres='Julio', apellidos='Cortazar')
    categoria = CategoriaLibro(nombre='Categoría portadas VV')
    db.session.add_all([autor, categoria])
    db.session.commit()
    return autor, categoria


def test_registrar_libro_sin_portada_sigue_funcionando(client, login, usuario_bibliotecario, db):
    login('test_bibliotecario', 'ClaveSegura123')
    autor, categoria = _autor_y_categoria(db)

    respuesta = client.post(
        '/bibliotecario/libros/nuevo',
        data=_datos_libro_validos(categoria_id=str(categoria.id), autores_ids=str(autor.id)),
        content_type='multipart/form-data',
    )

    assert respuesta.status_code == 302
    # El redirect agrega ?nuevo=<id> para marcar el registro recien creado.
    assert respuesta.headers['Location'].startswith('/bibliotecario/libros')

    libro = Libro.query.filter_by(isbn='9780306406157').first()
    assert libro is not None
    assert libro.portada_archivo is None


def test_registrar_libro_con_portada_valida(client, login, usuario_bibliotecario, db):
    login('test_bibliotecario', 'ClaveSegura123')
    autor, categoria = _autor_y_categoria(db)

    contenido_png = b'\x89PNG\r\n\x1a\n' + b'0' * 50  # firma real de PNG + relleno
    datos = _datos_libro_validos(categoria_id=str(categoria.id), autores_ids=str(autor.id))
    datos['portada'] = (io.BytesIO(contenido_png), 'portada.png')

    respuesta = client.post(
        '/bibliotecario/libros/nuevo', data=datos, content_type='multipart/form-data'
    )

    assert respuesta.status_code == 302

    libro = Libro.query.filter_by(isbn='9780306406157').first()
    assert libro is not None
    assert libro.portada_archivo is not None
    assert libro.portada_archivo.startswith('uploads/portadas/')
    assert libro.portada_archivo.endswith('.png')

    # El listado (con la miniatura real, no el placeholder) debe renderizar sin errores.
    listado = client.get('/bibliotecario/libros')
    assert listado.status_code == 200
    assert libro.portada_archivo in listado.get_data(as_text=True)

    _borrar_si_existe(libro.portada_archivo)


def test_formulario_nuevo_libro_renderiza_con_campo_portada(client, login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')

    respuesta = client.get('/bibliotecario/libros/nuevo')

    assert respuesta.status_code == 200
    contenido = respuesta.get_data(as_text=True)
    assert 'enctype="multipart/form-data"' in contenido
    assert 'name="portada"' in contenido


def test_registrar_libro_con_extension_invalida_se_rechaza(client, login, usuario_bibliotecario, db):
    login('test_bibliotecario', 'ClaveSegura123')
    autor, categoria = _autor_y_categoria(db)

    datos = _datos_libro_validos(categoria_id=str(categoria.id), autores_ids=str(autor.id))
    datos['portada'] = (io.BytesIO(b'esto no es una imagen'), 'portada.txt')

    respuesta = client.post(
        '/bibliotecario/libros/nuevo', data=datos, content_type='multipart/form-data'
    )

    # No redirige: el formulario se vuelve a mostrar con el error.
    assert respuesta.status_code == 200
    assert 'imagen JPG, PNG o WEBP' in respuesta.get_data(as_text=True)
    assert Libro.query.filter_by(isbn='9780306406157').first() is None


def test_catalogo_carga_sin_portada(client, login, usuario_estudiante, db):
    autor = Autor(nombres='Isabel', apellidos='Allende')
    categoria = CategoriaLibro(nombre='Categoría sin portada VV')
    editorial = Editorial(nombre='Editorial sin portada VV')
    db.session.add_all([autor, categoria, editorial])
    db.session.flush()

    libro = Libro(
        isbn='9780132350884',
        titulo='Libro sin portada',
        editorial_id=editorial.id,
        categoria_id=categoria.id,
        idioma='Español',
        stock_total=1,
        stock_disponible=1,
        activo=True,
    )
    db.session.add(libro)
    db.session.commit()

    login('1234567899', 'ClaveSegura123')

    respuesta = client.get('/estudiante/catalogo')

    assert respuesta.status_code == 200
    assert 'Libro sin portada' in respuesta.get_data(as_text=True)
    assert 'book-placeholder.svg' in respuesta.get_data(as_text=True)

    # El detalle del mismo libro tambien debe cargar y mostrar el placeholder.
    detalle = client.get(f'/estudiante/catalogo/{libro.isbn}')
    assert detalle.status_code == 200
    assert 'book-placeholder.svg' in detalle.get_data(as_text=True)
