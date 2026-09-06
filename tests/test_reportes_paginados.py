"""
Pruebas de paginacion/filtros de los reportes extensos del gerente
(prestamos activos, multas pendientes, estudiantes con deuda, inventario
actual y libros mas prestados). El historial de movimientos ya tiene su
propia suite en tests/test_resumen_y_reportes.py y no se toca aqui.

Dependen de database/setup.sql (funciones/triggers/vistas), que
tests/conftest.py aplica automaticamente sobre TEST_DATABASE_URL.
"""
from datetime import date

import pytest

from app.models import (
    CategoriaLibro, ConfiguracionSistema, Devolucion, Editorial, Ejemplar,
    Estudiante, Facultad, Carrera, Libro, Prestamo,
)

pytestmark = pytest.mark.requiere_setup_sql


@pytest.fixture
def gerente_logueado(login, usuario_gerente):
    login('test_gerente', 'ClaveSegura123')
    return usuario_gerente


@pytest.fixture
def configuracion(db):
    for clave, valor in [
        ('plazo_prestamo_dias', '7'), ('multa_diaria', '0.50'),
        ('max_prestamos_activos', '50'),
    ]:
        db.session.add(ConfiguracionSistema(clave=clave, valor=valor))
    db.session.commit()


@pytest.fixture
def datos_base(db):
    editorial = Editorial(nombre='Editorial Reportes')
    categoria = CategoriaLibro(nombre='Categoria Reportes')
    facultad = Facultad(nombre='Facultad Reportes')
    db.session.add_all([editorial, categoria, facultad])
    db.session.flush()
    carrera = Carrera(nombre='Carrera Reportes', facultad_id=facultad.id)
    db.session.add(carrera)
    db.session.commit()
    return editorial, categoria, carrera


@pytest.fixture
def crear_estudiante(db, datos_base):
    _, _, carrera = datos_base

    def _crear(cedula, nombres, apellidos):
        estudiante = Estudiante(
            cedula=cedula, nombres=nombres, apellidos=apellidos,
            correo=f'{cedula}@uteq.edu.ec', carrera_id=carrera.id,
        )
        db.session.add(estudiante)
        db.session.commit()
        return estudiante
    return _crear


@pytest.fixture
def crear_prestamo(db, datos_base, usuario_bibliotecario):
    editorial, categoria, _ = datos_base
    contador = {'n': 0}

    def _crear(estudiante, titulo=None, isbn=None):
        contador['n'] += 1
        indice = contador['n']
        libro = Libro(
            isbn=isbn or f'97850000{indice:05d}', titulo=titulo or f'Libro Reporte {indice}',
            editorial_id=editorial.id, categoria_id=categoria.id,
            stock_total=1, stock_disponible=1,
        )
        db.session.add(libro)
        db.session.flush()
        ejemplar = Ejemplar(libro_id=libro.id, codigo_ejemplar=f'EJR-{indice:04d}', fecha_adquisicion=date.today())
        db.session.add(ejemplar)
        db.session.flush()
        prestamo = Prestamo(
            codigo_prestamo=f'P-REP-{indice:04d}', estudiante_id=estudiante.id,
            ejemplar_id=ejemplar.id, bibliotecario_id=usuario_bibliotecario.id,
        )
        db.session.add(prestamo)
        db.session.commit()
        return prestamo, libro
    return _crear


def _devolver_con_multa(db, usuario_bibliotecario, prestamo, monto):
    """Crea la Devolucion directo (sin pasar por calcular_multa) para fijar un monto exacto."""
    db.session.add(Devolucion(
        prestamo_id=prestamo.id, bibliotecario_id=usuario_bibliotecario.id,
        estado_ejemplar='bueno', dias_retraso=10, multa_generada=monto, multa_pagada=False,
    ))
    db.session.commit()


# --------------------------------------------------------- prestamos activos

def test_prestamos_activos_limita_a_10_y_conserva_orden(
    client, db, gerente_logueado, configuracion, crear_estudiante, crear_prestamo
):
    estudiante = crear_estudiante('0900000001', 'Ana', 'Reportes')
    for _ in range(12):
        crear_prestamo(estudiante)

    respuesta = client.get('/gerente/reportes/prestamos-activos')
    assert respuesta.status_code == 200
    texto = respuesta.get_data(as_text=True)
    assert 'Mostrando 1-10 de 12 registros' in texto

    pagina2 = client.get('/gerente/reportes/prestamos-activos?page=2').get_data(as_text=True)
    assert 'Mostrando 11-12 de 12 registros' in pagina2


def test_prestamos_activos_filtra_por_estudiante_y_por_cedula(
    client, db, gerente_logueado, configuracion, crear_estudiante, crear_prestamo
):
    ana = crear_estudiante('0900000002', 'Ana', 'Perez')
    luis = crear_estudiante('0900000003', 'Luis', 'Gomez')
    crear_prestamo(ana, titulo='Libro de Ana')
    crear_prestamo(luis, titulo='Libro de Luis')

    por_nombre = client.get('/gerente/reportes/prestamos-activos?q=Perez').get_data(as_text=True)
    assert 'Libro de Ana' in por_nombre
    assert 'Libro de Luis' not in por_nombre

    por_cedula = client.get('/gerente/reportes/prestamos-activos?q=0900000003').get_data(as_text=True)
    assert 'Libro de Luis' in por_cedula
    assert 'Libro de Ana' not in por_cedula

    # Tambien por libro, ISBN y codigo de prestamo (mismo buscador general).
    prestamo_ana, libro_ana = crear_prestamo(ana, titulo='Cien Anios', isbn='9780000000011')
    por_titulo = client.get('/gerente/reportes/prestamos-activos?q=Cien Anios').get_data(as_text=True)
    assert 'Cien Anios' in por_titulo

    por_isbn = client.get('/gerente/reportes/prestamos-activos?q=9780000000011').get_data(as_text=True)
    assert 'Cien Anios' in por_isbn

    por_codigo = client.get(f'/gerente/reportes/prestamos-activos?q={prestamo_ana.codigo_prestamo}').get_data(as_text=True)
    assert 'Cien Anios' in por_codigo


def test_prestamos_activos_conserva_filtro_al_cambiar_de_pagina(
    client, db, gerente_logueado, configuracion, crear_estudiante, crear_prestamo
):
    ana = crear_estudiante('0900000004', 'Ana', 'Multiples')
    for _ in range(12):
        crear_prestamo(ana)
    otro = crear_estudiante('0900000005', 'Otro', 'Estudiante')
    crear_prestamo(otro, titulo='Libro que no debe aparecer')

    respuesta = client.get('/gerente/reportes/prestamos-activos?q=Multiples&page=2')
    assert respuesta.status_code == 200
    texto = respuesta.get_data(as_text=True)
    assert 'Libro que no debe aparecer' not in texto
    assert 'Mostrando 11-12 de 12 registros' in texto
    # El enlace "Anterior" conserva el filtro q.
    assert 'q=Multiples' in texto


# ----------------------------------------------------------- multas pendientes

def test_multas_pendientes_limita_a_10(
    client, db, gerente_logueado, configuracion, crear_estudiante, crear_prestamo, usuario_bibliotecario
):
    for indice in range(12):
        estudiante = crear_estudiante(f'091000{indice:04d}', f'Deudor{indice}', 'Apellido')
        prestamo, _ = crear_prestamo(estudiante)
        _devolver_con_multa(db, usuario_bibliotecario, prestamo, 5.00)

    respuesta = client.get('/gerente/reportes/multas-pendientes')
    texto = respuesta.get_data(as_text=True)
    assert 'Mostrando 1-10 de 12 registros' in texto


def test_multas_pendientes_filtra_por_cedula_y_nombre(
    client, db, gerente_logueado, configuracion, crear_estudiante, crear_prestamo, usuario_bibliotecario
):
    ana = crear_estudiante('0920000001', 'Ana', 'Deudora')
    luis = crear_estudiante('0920000002', 'Luis', 'Deudor')
    prestamo_ana, _ = crear_prestamo(ana)
    prestamo_luis, _ = crear_prestamo(luis)
    _devolver_con_multa(db, usuario_bibliotecario, prestamo_ana, 10.00)
    _devolver_con_multa(db, usuario_bibliotecario, prestamo_luis, 20.00)

    por_cedula = client.get('/gerente/reportes/multas-pendientes?q=0920000002').get_data(as_text=True)
    assert 'Luis Deudor' in por_cedula
    assert 'Ana Deudora' not in por_cedula

    por_nombre = client.get('/gerente/reportes/multas-pendientes?q=Ana Deudora').get_data(as_text=True)
    assert 'Ana Deudora' in por_nombre
    assert 'Luis Deudor' not in por_nombre


# ------------------------------------------------------ estudiantes con deuda

def test_estudiantes_con_deuda_filtra_por_cedula(
    client, db, gerente_logueado, configuracion, crear_estudiante, crear_prestamo, usuario_bibliotecario
):
    ana = crear_estudiante('0930000001', 'Ana', 'ConDeuda')
    luis = crear_estudiante('0930000002', 'Luis', 'ConDeuda')
    prestamo_ana, _ = crear_prestamo(ana)
    prestamo_luis, _ = crear_prestamo(luis)
    _devolver_con_multa(db, usuario_bibliotecario, prestamo_ana, 8.00)
    _devolver_con_multa(db, usuario_bibliotecario, prestamo_luis, 40.00)

    por_cedula = client.get('/gerente/reportes/estudiantes-con-deuda?q=0930000001').get_data(as_text=True)
    assert 'Ana ConDeuda' in por_cedula
    assert 'Luis ConDeuda' not in por_cedula

    # Orden razonable: deuda mayor primero.
    respuesta = client.get('/gerente/reportes/estudiantes-con-deuda').get_data(as_text=True)
    assert respuesta.find('Luis ConDeuda') < respuesta.find('Ana ConDeuda')


def test_estudiantes_con_deuda_pagina_de_10(
    client, db, gerente_logueado, configuracion, crear_estudiante, crear_prestamo, usuario_bibliotecario
):
    for indice in range(11):
        estudiante = crear_estudiante(f'094000{indice:04d}', f'Deuda{indice}', 'Apellido')
        prestamo, _ = crear_prestamo(estudiante)
        _devolver_con_multa(db, usuario_bibliotecario, prestamo, 3.00)

    texto = client.get('/gerente/reportes/estudiantes-con-deuda').get_data(as_text=True)
    assert 'Mostrando 1-10 de 11 registros' in texto


# --------------------------------------------------------- inventario actual

def test_inventario_actual_limita_a_10_y_filtra_por_titulo(
    client, db, gerente_logueado, configuracion, crear_prestamo, crear_estudiante
):
    """
    vista_inventario_actual no expone ISBN ni categoria (solo id/titulo/stock/
    ejemplares por estado), asi que el buscador general solo filtra por
    titulo: no se inventa un campo que la vista no devuelve.
    """
    estudiante = crear_estudiante('0940000099', 'Solo', 'Referencia')
    for indice in range(12):
        crear_prestamo(estudiante, titulo=f'Inventario Libro {indice}', isbn=f'9789990{indice:06d}')

    respuesta = client.get('/gerente/reportes/inventario-actual')
    texto = respuesta.get_data(as_text=True)
    assert 'Mostrando 1-10 de 12 registros' in texto

    por_titulo = client.get('/gerente/reportes/inventario-actual?q=Inventario Libro 5').get_data(as_text=True)
    assert 'Inventario Libro 5' in por_titulo
    assert 'Inventario Libro 6' not in por_titulo


def test_inventario_actual_filtra_por_disponibilidad(
    client, db, gerente_logueado, configuracion, crear_prestamo, crear_estudiante
):
    estudiante = crear_estudiante('0940000098', 'Otro', 'Referencia')
    # crear_prestamo presta el unico ejemplar creado, asi que ambos libros
    # quedan con stock_disponible=0; se ajusta el stock a mano para simular
    # uno con ejemplares libres y otro realmente agotado.
    _, libro_disponible = crear_prestamo(estudiante, titulo='Con stock disponible')
    libro_disponible.stock_total = 2
    libro_disponible.stock_disponible = 1
    _, libro_agotado = crear_prestamo(estudiante, titulo='Sin stock disponible')
    db.session.commit()

    con_stock = client.get('/gerente/reportes/inventario-actual?disponibilidad=disponibles').get_data(as_text=True)
    assert 'Con stock disponible' in con_stock
    assert 'Sin stock disponible' not in con_stock

    sin_stock = client.get('/gerente/reportes/inventario-actual?disponibilidad=agotados').get_data(as_text=True)
    assert 'Sin stock disponible' in sin_stock
    assert 'Con stock disponible' not in sin_stock


def test_inventario_actual_conserva_filtro_al_cambiar_de_pagina(
    client, db, gerente_logueado, configuracion, crear_prestamo, crear_estudiante
):
    estudiante = crear_estudiante('0940000097', 'Pagina', 'Dos')
    for indice in range(12):
        crear_prestamo(estudiante, titulo=f'Filtrado {indice}')
    crear_prestamo(estudiante, titulo='Libro que no debe aparecer')

    respuesta = client.get('/gerente/reportes/inventario-actual?q=Filtrado&page=2')
    texto = respuesta.get_data(as_text=True)
    assert 'Libro que no debe aparecer' not in texto
    assert 'Mostrando 11-12 de 12 registros' in texto
    assert 'q=Filtrado' in texto


# ------------------------------------------------------- libros mas prestados

def test_libros_mas_prestados_pagina_si_lista_todos_los_libros(
    client, db, gerente_logueado, configuracion, crear_prestamo, crear_estudiante
):
    """
    La vista (vista_libros_mas_prestados) no aplica LIMIT: devuelve TODOS los
    libros con al menos un prestamo, no un Top N fijo. Por eso debe paginar.
    """
    estudiante = crear_estudiante('0950000001', 'Lector', 'Frecuente')
    for indice in range(11):
        crear_prestamo(estudiante, titulo=f'Prestado {indice}')

    respuesta = client.get('/gerente/reportes/libros-mas-prestados')
    texto = respuesta.get_data(as_text=True)
    assert 'Mostrando 1-10 de 11 registros' in texto

    pagina2 = client.get('/gerente/reportes/libros-mas-prestados?page=2').get_data(as_text=True)
    assert 'Mostrando 11-11 de 11 registros' in pagina2


def test_libros_mas_prestados_filtra_por_titulo_y_conserva_orden_descendente(
    client, db, gerente_logueado, configuracion, crear_prestamo, crear_estudiante
):
    estudiante = crear_estudiante('0950000002', 'Otro', 'Lector')
    prestamo_a, libro_a = crear_prestamo(estudiante, titulo='Libro Popular')
    prestamo_b, libro_b = crear_prestamo(estudiante, titulo='Libro Poco Prestado')

    # Un segundo prestamo al mismo libro para que tenga mas total_prestamos
    # (el trigger de stock exige que haya un ejemplar disponible primero).
    libro_a.stock_total = 2
    libro_a.stock_disponible = 1
    ejemplar_extra = Ejemplar(libro_id=libro_a.id, codigo_ejemplar='EJR-EXTRA', fecha_adquisicion=date.today())
    db.session.add(ejemplar_extra)
    db.session.flush()
    otro_prestamo = Prestamo(
        codigo_prestamo='P-REP-EXTRA', estudiante_id=estudiante.id,
        ejemplar_id=ejemplar_extra.id, bibliotecario_id=prestamo_a.bibliotecario_id,
    )
    db.session.add(otro_prestamo)
    db.session.commit()

    respuesta = client.get('/gerente/reportes/libros-mas-prestados')
    texto = respuesta.get_data(as_text=True)
    # Orden descendente por total de prestamos: el mas prestado aparece primero.
    assert texto.find('Libro Popular') < texto.find('Libro Poco Prestado')

    filtrado = client.get('/gerente/reportes/libros-mas-prestados?q=Poco').get_data(as_text=True)
    assert 'Libro Poco Prestado' in filtrado
    assert 'Libro Popular' not in filtrado


# --------------------------------------------------- parametros invalidos

def test_parametros_invalidos_no_rompen_los_reportes(client, db, gerente_logueado):
    for url in (
        '/gerente/reportes/prestamos-activos?page=abc',
        '/gerente/reportes/prestamos-activos?page=-3',
        '/gerente/reportes/multas-pendientes?page=999',
        '/gerente/reportes/estudiantes-con-deuda?q=' + '%3Cscript%3E',
        '/gerente/reportes/inventario-actual?disponibilidad=<script>',
        '/gerente/reportes/libros-mas-prestados?page=0',
    ):
        assert client.get(url).status_code == 200, url


def test_historial_movimientos_no_se_rompio_con_el_helper_compartido(
    client, db, gerente_logueado, configuracion, crear_estudiante, crear_prestamo
):
    """paginar_select ahora lo usan varios reportes: confirma que el historial sigue intacto."""
    estudiante = crear_estudiante('0960000001', 'Verifica', 'Historial')
    crear_prestamo(estudiante, titulo='Libro Verificacion')

    respuesta = client.get('/gerente/reportes/historial-movimientos')
    assert respuesta.status_code == 200
    texto = respuesta.get_data(as_text=True)
    assert 'Libro Verificacion' in texto
    assert 'grafico-historial-tipo' in texto
