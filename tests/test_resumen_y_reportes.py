"""
Pruebas de la fase de resumen/sinopsis, dashboard/reportes del gerente y
paginacion del historial del estudiante.

Dependen de database/setup.sql (funciones/vistas), que tests/conftest.py
aplica automaticamente sobre TEST_DATABASE_URL.
"""
from datetime import date

import pytest

from app.models import (
    CategoriaLibro, ConfiguracionSistema, Editorial, Ejemplar, Estudiante,
    Libro, Prestamo,
)

pytestmark = pytest.mark.requiere_setup_sql


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
def gerente_logueado(login, usuario_gerente):
    login('test_gerente', 'ClaveSegura123')
    return usuario_gerente


@pytest.fixture
def catalogo_base(db):
    editorial = Editorial(nombre='Editorial Resumen')
    categoria = CategoriaLibro(nombre='Categoria Resumen')
    db.session.add_all([editorial, categoria])
    db.session.commit()
    return editorial, categoria


def _datos_libro_validos(**overrides):
    datos = {
        'isbn': '9780306406157',  # ISBN-13 con digito verificador valido
        'titulo': 'Libro de prueba con resumen',
        'subtitulo': '',
        'editorial_nombre': 'Editorial Nueva',
        'categoria_id': '',
        'anio_publicacion': '2020',
        'edicion': '',
        'num_paginas': '150',
        'idioma': 'Español',
        'stock_inicial': '2',
        'resumen': 'Una sinopsis de prueba con dos lineas.\nSegunda linea.',
        'autores_ids': '',
    }
    datos.update(overrides)
    return datos


# --------------------------------------------------------------- resumen

def test_resumen_se_guarda_correctamente(client, db, bibliotecario_logueado):
    categoria = CategoriaLibro(nombre='Categoria Prueba Resumen')
    db.session.add(categoria)
    db.session.commit()

    from app.models import Autor
    autor = Autor(nombres='Julio', apellidos='Cortazar')
    db.session.add(autor)
    db.session.commit()

    respuesta = client.post('/bibliotecario/libros/nuevo', data=_datos_libro_validos(
        categoria_id=str(categoria.id), autores_ids=str(autor.id),
    ))
    assert respuesta.status_code == 302

    libro = Libro.query.filter_by(isbn='9780306406157').first()
    assert libro is not None
    assert libro.resumen == 'Una sinopsis de prueba con dos lineas.\nSegunda linea.'


def test_libro_sin_resumen_sigue_funcionando(client, db, bibliotecario_logueado, catalogo_base):
    editorial, categoria = catalogo_base
    libro = Libro(
        isbn='9780000000099', titulo='Libro sin resumen',
        editorial_id=editorial.id, categoria_id=categoria.id,
        stock_total=1, stock_disponible=1,
    )
    db.session.add(libro)
    db.session.commit()

    respuesta = client.get('/bibliotecario/libros')
    assert respuesta.status_code == 200
    texto = respuesta.get_data(as_text=True)
    # El boton existe igual (data-resumen queda vacio) y el listado no truena.
    assert 'data-accion="ver-resumen"' in texto
    assert 'Libro sin resumen' in texto


def test_boton_y_modal_de_resumen_en_listado_bibliotecario(client, db, bibliotecario_logueado, catalogo_base):
    editorial, categoria = catalogo_base
    libro = Libro(
        isbn='9780000000098', titulo='Libro con resumen',
        editorial_id=editorial.id, categoria_id=categoria.id,
        stock_total=1, stock_disponible=1, resumen='Sinopsis visible en el modal.',
    )
    db.session.add(libro)
    db.session.commit()

    texto = client.get('/bibliotecario/libros').get_data(as_text=True)
    assert 'id="modal-resumen-libro"' in texto
    assert 'data-resumen="Sinopsis visible en el modal."' in texto
    assert 'js/resumen_libro.js' in texto


def test_boton_resumen_en_catalogo_estudiante(client, db, usuario_estudiante, login, catalogo_base):
    editorial, categoria = catalogo_base
    libro = Libro(
        isbn='9780000000097', titulo='Libro del catalogo',
        editorial_id=editorial.id, categoria_id=categoria.id,
        stock_total=1, stock_disponible=1, resumen='Sinopsis del catalogo.',
    )
    db.session.add(libro)
    db.session.commit()

    login('1234567899', 'ClaveSegura123')
    texto = client.get('/estudiante/catalogo').get_data(as_text=True)
    assert 'data-accion="ver-resumen"' in texto
    assert 'id="modal-resumen-libro"' in texto

    # API AJAX del catalogo tambien expone el resumen (lo usan las tarjetas dinamicas).
    datos = client.get('/estudiante/api/catalogo/buscar').get_json()
    assert any(item['isbn'] == '9780000000097' and item['resumen'] == 'Sinopsis del catalogo.' for item in datos)

    # El detalle del libro muestra el resumen directamente (sin modal).
    detalle = client.get('/estudiante/catalogo/9780000000097').get_data(as_text=True)
    assert 'Sinopsis del catalogo.' in detalle


def test_detalle_estudiante_sin_resumen_muestra_mensaje(client, db, usuario_estudiante, login, catalogo_base):
    editorial, categoria = catalogo_base
    libro = Libro(
        isbn='9780000000096', titulo='Libro sin sinopsis',
        editorial_id=editorial.id, categoria_id=categoria.id,
        stock_total=1, stock_disponible=1,
    )
    db.session.add(libro)
    db.session.commit()

    login('1234567899', 'ClaveSegura123')
    detalle = client.get('/estudiante/catalogo/9780000000096').get_data(as_text=True)
    assert 'No hay un resumen disponible para este libro.' in detalle


# --------------------------------------------------------- gerente dashboard

def test_dashboard_gerente_carga_con_nuevos_indicadores_y_graficos(
    client, db, gerente_logueado, configuracion, catalogo_base
):
    respuesta = client.get('/gerente/dashboard')
    assert respuesta.status_code == 200
    texto = respuesta.get_data(as_text=True)

    assert 'Préstamos vencidos' in texto
    assert 'Libros con stock disponible' in texto
    assert 'Multas pendientes de pago' in texto
    assert 'grafico-prestamos-estado' in texto
    assert 'grafico-libros-prestados' in texto
    assert 'grafico-prestamos-periodo' in texto
    assert 'grafico-top-deudores' in texto
    assert 'chart.js' in texto.lower()


# ------------------------------------------------------ historial gerente

def test_historial_movimientos_pagina_filtra_y_grafica(
    client, db, gerente_logueado, usuario_bibliotecario, configuracion, catalogo_base
):
    # Nota: se usa `usuario_bibliotecario` (sin iniciar sesion) solo para tener
    # un Usuario valido como bibliotecario_id de los prestamos; la sesion
    # activa del cliente debe seguir siendo la del gerente (`gerente_logueado`),
    # que es quien puede ver este reporte.
    editorial, categoria = catalogo_base

    from app.models import Carrera, Facultad
    facultad = Facultad(nombre='Facultad Historial')
    db.session.add(facultad)
    db.session.flush()
    carrera = Carrera(nombre='Carrera Historial', facultad_id=facultad.id)
    db.session.add(carrera)
    db.session.flush()

    estudiante = Estudiante(
        cedula='0955555555', nombres='Historial', apellidos='Pruebas',
        correo='historial@uteq.edu.ec', carrera_id=carrera.id,
    )
    db.session.add(estudiante)
    db.session.flush()

    libros_creados = []
    for indice in range(1, 13):
        libro = Libro(
            isbn=f'978200000{indice:04d}', titulo=f'Historial Libro {indice}',
            editorial_id=editorial.id, categoria_id=categoria.id,
            stock_total=1, stock_disponible=1,
        )
        db.session.add(libro)
        db.session.flush()
        ejemplar = Ejemplar(libro_id=libro.id, codigo_ejemplar=f'EJH-{indice:04d}', fecha_adquisicion=date.today())
        db.session.add(ejemplar)
        db.session.flush()
        prestamo = Prestamo(
            codigo_prestamo=f'P-HIST-{indice:04d}', estudiante_id=estudiante.id,
            ejemplar_id=ejemplar.id, bibliotecario_id=usuario_bibliotecario.id,
        )
        db.session.add(prestamo)
        libros_creados.append(libro)
    db.session.commit()

    # 12 movimientos de tipo prestamo -> pagina 10 + pagina 2 con 2.
    pagina1 = client.get('/gerente/reportes/historial-movimientos').get_data(as_text=True)
    assert 'Historial Libro 12' in pagina1  # recientes primero
    assert 'Historial Libro 1<' not in pagina1

    pagina2 = client.get('/gerente/reportes/historial-movimientos?page=2').get_data(as_text=True)
    assert 'Historial Libro 1' in pagina2

    # Filtro por titulo/isbn.
    filtrado = client.get('/gerente/reportes/historial-movimientos?q=Historial Libro 3').get_data(as_text=True)
    assert 'Historial Libro 3' in filtrado
    assert 'Historial Libro 4' not in filtrado

    # Filtro por tipo de movimiento (todos son prestamos, ninguno devolucion).
    solo_devoluciones = client.get(
        '/gerente/reportes/historial-movimientos?tipo_movimiento=devolucion'
    ).get_data(as_text=True)
    assert 'No hay movimientos' in solo_devoluciones

    # Parametros invalidos no rompen la pagina.
    for url in (
        '/gerente/reportes/historial-movimientos?page=abc',
        '/gerente/reportes/historial-movimientos?tipo_movimiento=<script>',
        '/gerente/reportes/historial-movimientos?fecha_desde=no-es-fecha',
    ):
        assert client.get(url).status_code == 200, url


def test_historial_movimientos_busca_por_cedula_del_estudiante(
    client, db, gerente_logueado, usuario_bibliotecario, configuracion, catalogo_base
):
    """El buscador general (mismo campo 'q') tambien debe encontrar por cedula."""
    editorial, categoria = catalogo_base

    from app.models import Carrera, Facultad
    facultad = Facultad(nombre='Facultad Cedula')
    db.session.add(facultad)
    db.session.flush()
    carrera = Carrera(nombre='Carrera Cedula', facultad_id=facultad.id)
    db.session.add(carrera)
    db.session.flush()

    estudiante_objetivo = Estudiante(
        cedula='0977777777', nombres='Cedula', apellidos='Objetivo',
        correo='cedula.objetivo@uteq.edu.ec', carrera_id=carrera.id,
    )
    estudiante_otro = Estudiante(
        cedula='0988888888', nombres='Otro', apellidos='Estudiante',
        correo='cedula.otro@uteq.edu.ec', carrera_id=carrera.id,
    )
    db.session.add_all([estudiante_objetivo, estudiante_otro])
    db.session.flush()

    def _crear_prestamo(estudiante, indice):
        libro = Libro(
            isbn=f'978400000{indice:04d}', titulo=f'Libro Cedula {indice}',
            editorial_id=editorial.id, categoria_id=categoria.id,
            stock_total=1, stock_disponible=1,
        )
        db.session.add(libro)
        db.session.flush()
        ejemplar = Ejemplar(libro_id=libro.id, codigo_ejemplar=f'EJC-{indice:04d}', fecha_adquisicion=date.today())
        db.session.add(ejemplar)
        db.session.flush()
        prestamo = Prestamo(
            codigo_prestamo=f'P-CED-{indice:04d}', estudiante_id=estudiante.id,
            ejemplar_id=ejemplar.id, bibliotecario_id=usuario_bibliotecario.id,
        )
        db.session.add(prestamo)
        return libro

    libro_objetivo = _crear_prestamo(estudiante_objetivo, 1)
    libro_otro = _crear_prestamo(estudiante_otro, 2)
    db.session.commit()

    respuesta = client.get('/gerente/reportes/historial-movimientos?q=0977777777')
    assert respuesta.status_code == 200
    texto = respuesta.get_data(as_text=True)

    # Encuentra el movimiento del estudiante buscado por cedula...
    assert libro_objetivo.titulo in texto
    assert 'Cedula Objetivo' in texto
    # ...y no mezcla resultados de otro estudiante.
    assert libro_otro.titulo not in texto
    assert 'Otro Estudiante' not in texto

    # Sigue funcionando la busqueda por libro, ISBN y nombre (no se rompio nada).
    por_libro = client.get('/gerente/reportes/historial-movimientos?q=Libro Cedula 2').get_data(as_text=True)
    assert libro_otro.titulo in por_libro

    por_isbn = client.get(f'/gerente/reportes/historial-movimientos?q={libro_objetivo.isbn}').get_data(as_text=True)
    assert libro_objetivo.titulo in por_isbn

    por_nombre = client.get('/gerente/reportes/historial-movimientos?q=Otro Estudiante').get_data(as_text=True)
    assert libro_otro.titulo in por_nombre

    # Compatible con el resto de filtros y con la paginacion.
    combinado = client.get(
        '/gerente/reportes/historial-movimientos?q=0977777777&tipo_movimiento=prestamo&page=1'
    ).get_data(as_text=True)
    assert libro_objetivo.titulo in combinado


def test_otros_reportes_del_gerente_siguen_funcionando(client, db, gerente_logueado):
    """Los 5 reportes que no se tocaron en esta fase siguen accesibles."""
    for tipo in (
        'prestamos-activos', 'multas-pendientes', 'libros-mas-prestados',
        'estudiantes-con-deuda', 'inventario-actual',
    ):
        assert client.get(f'/gerente/reportes/{tipo}').status_code == 200, tipo


# ------------------------------------------------------ mis prestamos

def test_mis_prestamos_pagina_y_aisla_entre_estudiantes(client, db, login, configuracion, catalogo_base):
    editorial, categoria = catalogo_base
    from app.models import Carrera, Facultad, Usuario, Devolucion
    from werkzeug.security import generate_password_hash

    facultad = Facultad(nombre='Facultad Mis Prestamos')
    db.session.add(facultad)
    db.session.flush()
    carrera = Carrera(nombre='Carrera Mis Prestamos', facultad_id=facultad.id)
    db.session.add(carrera)
    db.session.flush()

    bibliotecario = Usuario(username='biblio_mp', password_hash=generate_password_hash('x'), rol='bibliotecario')
    db.session.add(bibliotecario)
    db.session.flush()

    def _crear_estudiante(cedula):
        usuario = Usuario(username=cedula, password_hash=generate_password_hash('ClaveSegura123'), rol='estudiante')
        db.session.add(usuario)
        db.session.flush()
        estudiante = Estudiante(
            cedula=cedula, nombres='Est', apellidos=cedula, correo=f'{cedula}@uteq.edu.ec',
            carrera_id=carrera.id, usuario_id=usuario.id,
        )
        db.session.add(estudiante)
        db.session.commit()
        return estudiante

    est_a = _crear_estudiante('0911111111')
    est_b = _crear_estudiante('0922222222')

    # 12 prestamos devueltos para est_a (para forzar 2 paginas), 1 para est_b.
    for indice in range(1, 13):
        libro = Libro(
            isbn=f'978300000{indice:04d}', titulo=f'Mis Prestamos Libro {indice}',
            editorial_id=editorial.id, categoria_id=categoria.id, stock_total=1, stock_disponible=1,
        )
        db.session.add(libro)
        db.session.flush()
        ejemplar = Ejemplar(libro_id=libro.id, codigo_ejemplar=f'EJMP-{indice:04d}', fecha_adquisicion=date.today())
        db.session.add(ejemplar)
        db.session.flush()
        prestamo = Prestamo(
            codigo_prestamo=f'P-MP-{indice:04d}', estudiante_id=est_a.id,
            ejemplar_id=ejemplar.id, bibliotecario_id=bibliotecario.id, estado='devuelto',
        )
        db.session.add(prestamo)
        db.session.flush()
        db.session.add(Devolucion(
            prestamo_id=prestamo.id, bibliotecario_id=bibliotecario.id,
            estado_ejemplar='bueno', dias_retraso=0, multa_generada=0,
        ))
    db.session.commit()

    libro_b = Libro(
        isbn='9783000009999', titulo='Libro exclusivo de est_b',
        editorial_id=editorial.id, categoria_id=categoria.id, stock_total=1, stock_disponible=1,
    )
    db.session.add(libro_b)
    db.session.flush()
    ejemplar_b = Ejemplar(libro_id=libro_b.id, codigo_ejemplar='EJMP-B', fecha_adquisicion=date.today())
    db.session.add(ejemplar_b)
    db.session.flush()
    prestamo_b = Prestamo(
        codigo_prestamo='P-MP-B', estudiante_id=est_b.id, ejemplar_id=ejemplar_b.id,
        bibliotecario_id=bibliotecario.id, estado='devuelto',
    )
    db.session.add(prestamo_b)
    db.session.flush()
    db.session.add(Devolucion(
        prestamo_id=prestamo_b.id, bibliotecario_id=bibliotecario.id,
        estado_ejemplar='bueno', dias_retraso=0, multa_generada=0,
    ))
    db.session.commit()

    login('0911111111', 'ClaveSegura123')
    pagina1 = client.get('/estudiante/prestamos').get_data(as_text=True)
    assert 'Mis Prestamos Libro 12' in pagina1
    assert 'Libro exclusivo de est_b' not in pagina1  # aislamiento entre estudiantes

    pagina2 = client.get('/estudiante/prestamos?page=2').get_data(as_text=True)
    assert 'Mis Prestamos Libro 1' in pagina2
