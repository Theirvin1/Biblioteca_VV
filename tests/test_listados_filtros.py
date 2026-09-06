"""
Pruebas de los listados del bibliotecario: orden (lo mas nuevo arriba),
paginacion de 10, filtros de busqueda, indicador "Nuevo" y las pestañas
Pendientes / Completadas / Todas de devoluciones.

Dependen de database/setup.sql (triggers de stock y fecha limite), que
tests/conftest.py aplica automaticamente sobre TEST_DATABASE_URL.
"""
from datetime import date

import pytest

from app.models import (
    Autor, CategoriaLibro, ConfiguracionSistema, Editorial, Ejemplar,
    Estudiante, Libro, LibroAutor, Prestamo,
)

pytestmark = pytest.mark.requiere_setup_sql


# ---------------------------------------------------------------- fixtures

@pytest.fixture
def configuracion(db):
    for clave, valor in [
        ('plazo_prestamo_dias', '7'), ('multa_diaria', '0.50'),
        ('max_prestamos_activos', '50'),
    ]:
        db.session.add(ConfiguracionSistema(clave=clave, valor=valor))
    db.session.commit()


@pytest.fixture
def bibliotecario_logueado(login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')
    return usuario_bibliotecario


@pytest.fixture
def crear_estudiante(db, carrera_prueba):
    def _crear(indice, nombres='Estudiante', apellidos='Apellido', estado='activo'):
        estudiante = Estudiante(
            cedula=f'09{indice:08d}',
            nombres=nombres,
            apellidos=apellidos,
            correo=f'estudiante{indice}@uteq.edu.ec',
            carrera_id=carrera_prueba.id,
            estado=estado,
        )
        db.session.add(estudiante)
        db.session.commit()
        return estudiante
    return _crear


@pytest.fixture
def crear_libro(db):
    editorial = Editorial(nombre='Editorial Listados')
    categoria = CategoriaLibro(nombre='Categoria Listados')
    db.session.add_all([editorial, categoria])
    db.session.commit()

    def _crear(indice, titulo=None, autor=None, ejemplares=1):
        libro = Libro(
            isbn=f'978100{indice:07d}',
            titulo=titulo or f'Libro {indice}',
            editorial_id=editorial.id,
            categoria_id=categoria.id,
            stock_total=ejemplares,
            stock_disponible=ejemplares,
        )
        db.session.add(libro)
        db.session.flush()

        if autor:
            nombres, apellidos = autor
            registro = Autor(nombres=nombres, apellidos=apellidos)
            db.session.add(registro)
            db.session.flush()
            db.session.add(LibroAutor(libro_id=libro.id, autor_id=registro.id))

        for numero in range(ejemplares):
            db.session.add(Ejemplar(
                libro_id=libro.id,
                codigo_ejemplar=f'EJL-{indice:04d}-{numero}',
                fecha_adquisicion=date.today(),
            ))
        db.session.commit()
        return libro
    return _crear


def _registrar_prestamo(client, cedula, isbns):
    return client.post('/bibliotecario/prestamos/nuevo', data={
        'cedula': cedula,
        'isbns': ','.join(isbns),
        'observaciones': '',
    }, follow_redirects=False)


def _drenar_flashes(client):
    """Consume los flash pendientes para que no aparezcan en el GET que se evalua."""
    client.get('/bibliotecario/inicio')


def _filas(respuesta, marcador):
    """Cuenta cuantas veces aparece un marcador de fila en el HTML devuelto."""
    return respuesta.get_data(as_text=True).count(marcador)


# ------------------------------------------------------- estudiantes

def test_estudiantes_pagina_de_10_y_mas_reciente_primero(
    client, db, bibliotecario_logueado, crear_estudiante
):
    for indice in range(1, 15):
        crear_estudiante(indice, apellidos=f'Apellido{indice:02d}')

    respuesta = client.get('/bibliotecario/estudiantes')
    texto = respuesta.get_data(as_text=True)

    assert respuesta.status_code == 200
    assert _filas(respuesta, 'estudiante') >= 10
    assert 'Mostrando 1-10 de 14 estudiantes' in texto

    # El ultimo registrado encabeza la lista y el primero no cabe en la pagina 1.
    assert 'Apellido14' in texto
    assert 'Apellido01' not in texto

    segunda = client.get('/bibliotecario/estudiantes?page=2').get_data(as_text=True)
    assert 'Apellido01' in segunda
    assert 'Mostrando 11-14 de 14 estudiantes' in segunda


def test_estudiantes_filtro_por_cedula_y_por_nombre(
    client, db, bibliotecario_logueado, crear_estudiante
):
    crear_estudiante(1, nombres='Gabriel', apellidos='Garcia')
    crear_estudiante(2, nombres='Luis', apellidos='Mendoza')

    por_cedula = client.get('/bibliotecario/estudiantes?q=0900000001').get_data(as_text=True)
    assert 'Garcia' in por_cedula
    assert 'Mendoza' not in por_cedula

    por_nombre = client.get('/bibliotecario/estudiantes?q=mendoza').get_data(as_text=True)
    assert 'Mendoza' in por_nombre
    assert 'Garcia' not in por_nombre


def test_estudiantes_filtro_por_estado(client, db, bibliotecario_logueado, crear_estudiante):
    crear_estudiante(1, apellidos='Vigente')
    crear_estudiante(2, apellidos='Bloqueado', estado='suspendido')

    texto = client.get('/bibliotecario/estudiantes?estado=suspendido').get_data(as_text=True)
    assert 'Bloqueado' in texto
    assert 'Vigente' not in texto


def test_estudiante_recien_creado_se_marca_como_nuevo(
    client, db, bibliotecario_logueado, carrera_prueba
):
    respuesta = client.post('/bibliotecario/estudiantes/nuevo', data={
        'cedula': '1710034065',
        'nombres': 'Nuevo',
        'apellidos': 'Estudiante',
        'correo': 'nuevo.estudiante@uteq.edu.ec',
        'telefono': '0991234567',
        'carrera_id': str(carrera_prueba.id),
        'fecha_nacimiento': '2003-05-20',
        'genero': 'M',
    })

    estudiante = Estudiante.query.filter_by(cedula='1710034065').first()
    assert estudiante is not None
    # El registro ya no redirige: responde la pantalla de credenciales, cuyo
    # enlace "Ver en el listado" conserva el marcado ?nuevo=<id>.
    assert respuesta.status_code == 200
    assert f'nuevo={estudiante.id}' in respuesta.get_data(as_text=True)

    con_badge = client.get(f'/bibliotecario/estudiantes?nuevo={estudiante.id}').get_data(as_text=True)
    assert 'Nuevo</span>' in con_badge

    # El indicador es solo de la vista: no existe ninguna columna en la BD...
    assert not hasattr(estudiante, 'nuevo')
    # ...y al navegar normalmente desaparece.
    sin_badge = client.get('/bibliotecario/estudiantes').get_data(as_text=True)
    assert 'Nuevo</span>' not in sin_badge


# ------------------------------------------------------------- libros

def test_libros_paginados_y_filtro_por_isbn_titulo_y_autor(
    client, db, bibliotecario_logueado, crear_libro
):
    for indice in range(1, 13):
        crear_libro(indice, titulo=f'Titulo {indice:02d}')
    crear_libro(99, titulo='Cien años de soledad', autor=('Gabriel', 'Garcia Marquez'))

    listado = client.get('/bibliotecario/libros')
    texto = listado.get_data(as_text=True)
    assert 'Mostrando 1-10 de 13 libros' in texto
    # Lo mas reciente primero: el ultimo libro creado encabeza la lista.
    assert 'Cien años de soledad' in texto
    assert 'Titulo 01' not in texto

    por_isbn = client.get('/bibliotecario/libros?q=9781000000099').get_data(as_text=True)
    assert 'Cien años de soledad' in por_isbn
    assert 'Titulo 05' not in por_isbn

    por_titulo = client.get('/bibliotecario/libros?q=Titulo 05').get_data(as_text=True)
    assert 'Titulo 05' in por_titulo
    assert 'Cien años de soledad' not in por_titulo

    por_autor = client.get('/bibliotecario/libros?q=marquez').get_data(as_text=True)
    assert 'Cien años de soledad' in por_autor
    assert 'Titulo 05' not in por_autor


def test_libros_filtro_por_disponibilidad(client, db, bibliotecario_logueado, crear_libro):
    disponible = crear_libro(1, titulo='LibroConEjemplares')
    agotado = crear_libro(2, titulo='LibroAgotado')
    agotado.stock_disponible = 0
    db.session.commit()

    con_stock = client.get('/bibliotecario/libros?disponibilidad=disponibles').get_data(as_text=True)
    assert 'LibroConEjemplares' in con_stock
    assert 'LibroAgotado' not in con_stock

    sin_stock = client.get('/bibliotecario/libros?disponibilidad=agotados').get_data(as_text=True)
    assert 'LibroAgotado' in sin_stock
    assert disponible.titulo not in sin_stock


# ---------------------------------------------------------- prestamos

def test_prestamos_paginados_por_operacion_y_mas_reciente_primero(
    client, db, bibliotecario_logueado, configuracion, crear_estudiante, crear_libro
):
    estudiante = crear_estudiante(1, apellidos='Prestatario')
    for indice in range(1, 13):
        libro = crear_libro(indice)
        _registrar_prestamo(client, estudiante.cedula, [libro.isbn])

    respuesta = client.get('/bibliotecario/prestamos')
    texto = respuesta.get_data(as_text=True)

    assert 'Mostrando 1-10 de 12 operaciones' in texto
    # La operacion mas reciente (ultimo codigo generado) va primero.
    codigos = Prestamo.query.order_by(Prestamo.id.desc()).all()
    assert codigos[0].codigo_prestamo in texto
    assert codigos[-1].codigo_prestamo not in texto

    segunda = client.get('/bibliotecario/prestamos?page=2').get_data(as_text=True)
    assert codigos[-1].codigo_prestamo in segunda


def test_prestamos_filtro_por_cedula_y_por_codigo_de_operacion(
    client, db, bibliotecario_logueado, configuracion, crear_estudiante, crear_libro
):
    uno = crear_estudiante(1, apellidos='Primero')
    otro = crear_estudiante(2, apellidos='Segundo')
    _registrar_prestamo(client, uno.cedula, [crear_libro(1).isbn, crear_libro(2).isbn])
    _registrar_prestamo(client, otro.cedula, [crear_libro(3).isbn])

    grupo = Prestamo.query.filter(Prestamo.grupo_prestamo.isnot(None)).first().grupo_prestamo
    _drenar_flashes(client)

    por_cedula = client.get(f'/bibliotecario/prestamos?q={otro.cedula}').get_data(as_text=True)
    assert 'Segundo' in por_cedula
    assert 'Primero' not in por_cedula

    # Al buscar por el codigo de operacion se ve el grupo completo (2 libros).
    por_grupo = client.get(f'/bibliotecario/prestamos?q={grupo}').get_data(as_text=True)
    assert grupo in por_grupo
    assert 'Primero' in por_grupo
    assert 'Segundo' not in por_grupo


def test_pagina_invalida_no_rompe_el_listado(client, db, bibliotecario_logueado, crear_estudiante):
    crear_estudiante(1)

    for url in (
        '/bibliotecario/estudiantes?page=abc',
        '/bibliotecario/estudiantes?page=-3',
        '/bibliotecario/estudiantes?page=999',
        '/bibliotecario/libros?categoria=xyz&disponibilidad=inventado',
        '/bibliotecario/prestamos?estado=inventado&page=0',
        '/bibliotecario/devoluciones?estado=<script>',
    ):
        assert client.get(url).status_code == 200, url


def test_prestamo_recien_creado_se_marca_como_nuevo(
    client, db, bibliotecario_logueado, configuracion, crear_estudiante, crear_libro
):
    estudiante = crear_estudiante(1)
    isbns = [crear_libro(1).isbn, crear_libro(2).isbn]

    respuesta = _registrar_prestamo(client, estudiante.cedula, isbns)

    # Se marca la OPERACION (primer prestamo del grupo), no cada libro.
    primero = Prestamo.query.order_by(Prestamo.id).first()
    assert respuesta.headers['Location'].endswith(f'?nuevo={primero.id}')

    texto = client.get(f'/bibliotecario/prestamos?nuevo={primero.id}').get_data(as_text=True)
    assert texto.count('Nuevo</span>') == 1


# -------------------------------------------------------- devoluciones

def _devolver(client, representante_id, prestamos):
    datos = {'prestamos': [str(p.id) for p in prestamos]}
    for prestamo in prestamos:
        datos[f'estado_{prestamo.id}'] = 'bueno'
    return client.post(
        f'/bibliotecario/devoluciones/operacion/{representante_id}',
        data=datos, follow_redirects=True,
    )


def test_devoluciones_pendientes_completadas_y_todas(
    client, db, bibliotecario_logueado, configuracion, crear_estudiante, crear_libro
):
    estudiante = crear_estudiante(1, apellidos='Devolvedor')

    # Operacion A (2 libros) se devuelve completa; operacion B (1 libro) queda pendiente.
    _registrar_prestamo(client, estudiante.cedula, [crear_libro(1).isbn, crear_libro(2).isbn])
    grupo_a = Prestamo.query.filter(Prestamo.grupo_prestamo.isnot(None)).all()
    _registrar_prestamo(client, estudiante.cedula, [crear_libro(3).isbn])
    prestamo_b = Prestamo.query.filter(Prestamo.grupo_prestamo.is_(None)).first()

    _devolver(client, grupo_a[0].id, grupo_a)
    codigo_a = grupo_a[0].grupo_prestamo

    pendientes = client.get('/bibliotecario/devoluciones?estado=pendientes').get_data(as_text=True)
    assert prestamo_b.codigo_prestamo in pendientes
    assert codigo_a not in pendientes

    completadas = client.get('/bibliotecario/devoluciones?estado=completadas').get_data(as_text=True)
    assert codigo_a in completadas
    assert 'Devolución completa' in completadas
    assert prestamo_b.codigo_prestamo not in completadas

    todas = client.get('/bibliotecario/devoluciones?estado=todas').get_data(as_text=True)
    assert codigo_a in todas
    assert prestamo_b.codigo_prestamo in todas
    assert 'Mostrando 1-2 de 2 operaciones' in todas


def test_devolucion_parcial_sigue_en_pendientes_con_su_conteo(
    client, db, bibliotecario_logueado, configuracion, crear_estudiante, crear_libro
):
    estudiante = crear_estudiante(1)
    _registrar_prestamo(client, estudiante.cedula, [
        crear_libro(1).isbn, crear_libro(2).isbn, crear_libro(3).isbn,
    ])
    prestamos = Prestamo.query.order_by(Prestamo.id).all()

    _devolver(client, prestamos[0].id, prestamos[:1])

    pendientes = client.get('/bibliotecario/devoluciones?estado=pendientes').get_data(as_text=True)
    assert prestamos[0].grupo_prestamo in pendientes
    assert 'Devolución parcial' in pendientes


def test_operacion_completa_no_permite_devolver_de_nuevo(
    client, db, bibliotecario_logueado, configuracion, crear_estudiante, crear_libro
):
    estudiante = crear_estudiante(1)
    _registrar_prestamo(client, estudiante.cedula, [crear_libro(1).isbn])
    prestamo = Prestamo.query.first()

    _devolver(client, prestamo.id, [prestamo])

    # El detalle historico sigue disponible y muestra el estado del ejemplar.
    detalle = client.get(f'/bibliotecario/prestamos/{prestamo.id}/detalle').get_data(as_text=True)
    assert 'Devolución completa' in detalle
    assert 'Bueno' in detalle

    # Pero la pantalla de devolucion ya no deja registrar nada mas.
    respuesta = client.get(
        f'/bibliotecario/devoluciones/operacion/{prestamo.id}', follow_redirects=True
    )
    assert 'ya fueron devueltos' in respuesta.get_data(as_text=True)


def test_prestamo_antiguo_sin_grupo_aparece_en_los_listados(
    client, db, bibliotecario_logueado, configuracion, crear_estudiante, crear_libro
):
    estudiante = crear_estudiante(1)
    libro = crear_libro(1)
    ejemplar = Ejemplar.query.filter_by(libro_id=libro.id).first()

    antiguo = Prestamo(
        codigo_prestamo='P-2025-9999',
        estudiante_id=estudiante.id,
        ejemplar_id=ejemplar.id,
        bibliotecario_id=bibliotecario_logueado.id,
        fecha_limite=date.today(),
        grupo_prestamo=None,
    )
    db.session.add(antiguo)
    db.session.commit()

    prestamos = client.get('/bibliotecario/prestamos').get_data(as_text=True)
    assert 'P-2025-9999' in prestamos
    assert 'Préstamo individual' in prestamos

    devoluciones = client.get('/bibliotecario/devoluciones?estado=pendientes').get_data(as_text=True)
    assert 'P-2025-9999' in devoluciones


# ------------------------------------------------------------- flash

def test_el_js_compartido_de_mensajes_esta_en_todas_las_pantallas(
    client, bibliotecario_logueado
):
    """El auto-ocultado se carga desde base.html, no pantalla por pantalla."""
    for url in ('/bibliotecario/inicio', '/bibliotecario/estudiantes', '/bibliotecario/libros'):
        assert 'js/mensajes.js' in client.get(url).get_data(as_text=True), url


def test_flash_de_exito_se_autocierra_y_el_de_error_no(
    client, db, bibliotecario_logueado, carrera_prueba
):
    # Se usa el registro de LIBRO para el caso de exito: el registro de
    # estudiante ya no emite flash, ahora responde la pantalla de credenciales
    # temporales (ver tests/test_gestion_usuarios.py).
    categoria = CategoriaLibro(nombre='Categoria Flash')
    autor = Autor(nombres='Autora', apellidos='Flash')
    db.session.add_all([categoria, autor])
    db.session.commit()

    exito = client.post('/bibliotecario/libros/nuevo', data={
        'isbn': '9780306406157',  # ISBN-13 con digito verificador valido
        'titulo': 'Libro para el flash',
        'editorial_nombre': 'Editorial Flash',
        'categoria_id': str(categoria.id),
        'idioma': 'Español',
        'stock_inicial': '1',
        'autores_ids': str(autor.id),
    }, follow_redirects=True).get_data(as_text=True)
    assert 'alert-success' in exito
    assert 'data-auto-cerrar' in exito

    # Un error (ISBN repetido) se queda hasta que el usuario lo cierre.
    error = client.post('/bibliotecario/libros/nuevo', data={
        'isbn': '9780306406157',  # el mismo de arriba
        'titulo': 'Otro libro con el mismo ISBN',
        'editorial_nombre': 'Editorial Flash',
        'categoria_id': str(categoria.id),
        'idioma': 'Español',
        'stock_inicial': '1',
        'autores_ids': str(autor.id),
    }).get_data(as_text=True)
    assert 'alert-danger' in error
    assert 'data-auto-cerrar' not in error
