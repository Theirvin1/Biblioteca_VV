"""
Pruebas del prestamo de varios libros en una sola operacion y de las
devoluciones parciales/totales.

Dependen de database/setup.sql (funciones validar_prestamo,
generar_codigo_prestamo, calcular_multa y los triggers de stock), que
tests/conftest.py aplica automaticamente sobre TEST_DATABASE_URL.

El limite de prestamos NO se asume: cada prueba escribe el valor que necesita
en configuracion_sistema.max_prestamos_activos y comprueba que el sistema lo
respeta.
"""
from datetime import date, timedelta

import pytest

from app.models import (
    CategoriaLibro, ConfiguracionSistema, Editorial, Ejemplar, Estudiante,
    Libro, Prestamo,
)

pytestmark = pytest.mark.requiere_setup_sql


# ---------------------------------------------------------------- fixtures

def _configurar(db, clave, valor):
    fila = ConfiguracionSistema.query.filter_by(clave=clave).first()
    if fila is None:
        db.session.add(ConfiguracionSistema(clave=clave, valor=str(valor)))
    else:
        fila.valor = str(valor)
    db.session.commit()


@pytest.fixture
def configuracion(db):
    """Configuracion minima que necesitan los triggers y el calculo de multa."""
    _configurar(db, 'plazo_prestamo_dias', 7)
    _configurar(db, 'multa_diaria', '0.50')
    _configurar(db, 'max_prestamos_activos', 5)

    return lambda clave, valor: _configurar(db, clave, valor)


@pytest.fixture
def estudiante(db, carrera_prueba):
    registro = Estudiante(
        cedula='0912345678',
        nombres='Ana',
        apellidos='Lopez',
        correo='ana.lopez@uteq.edu.ec',
        carrera_id=carrera_prueba.id,
        fecha_nacimiento=date(2003, 5, 20),
    )
    db.session.add(registro)
    db.session.commit()
    return registro


@pytest.fixture
def crear_libro(db):
    """Crea un libro con sus ejemplares disponibles y devuelve el Libro."""
    editorial = Editorial(nombre='Editorial de Pruebas VV')
    categoria = CategoriaLibro(nombre='Categoria de Pruebas VV')
    db.session.add_all([editorial, categoria])
    db.session.commit()

    contador = {'n': 0}

    def _crear(isbn, titulo, ejemplares=1):
        libro = Libro(
            isbn=isbn,
            titulo=titulo,
            editorial_id=editorial.id,
            categoria_id=categoria.id,
            stock_total=ejemplares,
            stock_disponible=ejemplares,
        )
        db.session.add(libro)
        db.session.flush()

        for _ in range(ejemplares):
            contador['n'] += 1
            db.session.add(Ejemplar(
                libro_id=libro.id,
                codigo_ejemplar=f'EJ-TEST-{contador["n"]:04d}',
                fecha_adquisicion=date.today(),
            ))
        db.session.commit()
        return libro

    return _crear


@pytest.fixture
def bibliotecario_logueado(login, usuario_bibliotecario):
    login('test_bibliotecario', 'ClaveSegura123')
    return usuario_bibliotecario


def _registrar_prestamo(client, cedula, isbns, observaciones=''):
    return client.post('/bibliotecario/prestamos/nuevo', data={
        'cedula': cedula,
        'isbns': ','.join(isbns),
        'observaciones': observaciones,
    }, follow_redirects=True)


# ---------------------------------------------------------------- prestamo

def test_prestamo_de_varios_libros_crea_una_operacion(
    client, db, bibliotecario_logueado, configuracion, estudiante, crear_libro
):
    """Tres libros en un registro: tres prestamos individuales, un solo grupo."""
    libros = [
        crear_libro('9780000000001', 'Libro Uno', ejemplares=2),
        crear_libro('9780000000002', 'Libro Dos', ejemplares=1),
        crear_libro('9780000000003', 'Libro Tres', ejemplares=3),
    ]

    respuesta = _registrar_prestamo(
        client, estudiante.cedula, [libro.isbn for libro in libros]
    )
    assert respuesta.status_code == 200

    prestamos = Prestamo.query.order_by(Prestamo.id).all()
    assert len(prestamos) == 3

    grupos = {prestamo.grupo_prestamo for prestamo in prestamos}
    assert len(grupos) == 1
    assert grupos.pop().startswith(f'GRP-{date.today().year}-')

    # Cada prestamo conserva su propio codigo y su propio ejemplar.
    assert len({p.codigo_prestamo for p in prestamos}) == 3
    assert len({p.ejemplar_id for p in prestamos}) == 3
    assert all(p.estado == 'activo' for p in prestamos)


def test_stock_disminuye_por_cada_libro_prestado(
    client, db, bibliotecario_logueado, configuracion, estudiante, crear_libro
):
    libro_a = crear_libro('9780000000011', 'Libro A', ejemplares=3)
    libro_b = crear_libro('9780000000012', 'Libro B', ejemplares=2)

    _registrar_prestamo(client, estudiante.cedula, [libro_a.isbn, libro_b.isbn])

    db.session.expire_all()
    assert Libro.query.filter_by(isbn='9780000000011').first().stock_disponible == 2
    assert Libro.query.filter_by(isbn='9780000000012').first().stock_disponible == 1
    assert Ejemplar.query.filter_by(estado='prestado').count() == 2


def test_no_permite_superar_el_maximo_de_prestamos_activos(
    client, db, bibliotecario_logueado, configuracion, estudiante, crear_libro
):
    configuracion('max_prestamos_activos', 2)

    isbns = [
        crear_libro('9780000000021', 'Libro 1').isbn,
        crear_libro('9780000000022', 'Libro 2').isbn,
        crear_libro('9780000000023', 'Libro 3').isbn,
    ]

    respuesta = _registrar_prestamo(client, estudiante.cedula, isbns)
    texto = respuesta.get_data(as_text=True)

    assert 'cupo' in texto
    assert Prestamo.query.count() == 0


def test_no_permite_isbn_duplicado_en_el_mismo_lote(
    client, db, bibliotecario_logueado, configuracion, estudiante, crear_libro
):
    libro = crear_libro('9780000000031', 'Libro repetido', ejemplares=4)

    respuesta = _registrar_prestamo(client, estudiante.cedula, [libro.isbn, libro.isbn])

    assert 'ya fue agregado' in respuesta.get_data(as_text=True)
    assert Prestamo.query.count() == 0


def test_rollback_completo_si_falla_uno_de_los_libros(
    client, db, monkeypatch, bibliotecario_logueado, configuracion, estudiante, crear_libro
):
    """Si el tercer libro revienta al guardarse, no debe quedar ninguno."""
    from app.controllers.bibliotecario import prestamos as controlador

    isbns = [
        crear_libro('9780000000041', 'Libro 1').isbn,
        crear_libro('9780000000042', 'Libro 2').isbn,
        crear_libro('9780000000043', 'Libro 3').isbn,
    ]

    original = controlador._generar_codigo_prestamo
    llamadas = {'n': 0}

    def _falla_en_el_tercero():
        llamadas['n'] += 1
        if llamadas['n'] == 3:
            raise RuntimeError('fallo simulado al guardar el tercer libro')
        return original()

    monkeypatch.setattr(controlador, '_generar_codigo_prestamo', _falla_en_el_tercero)

    respuesta = _registrar_prestamo(client, estudiante.cedula, isbns)

    assert 'No se guardó ningún libro' in respuesta.get_data(as_text=True)

    db.session.expire_all()
    assert Prestamo.query.count() == 0
    assert Ejemplar.query.filter_by(estado='prestado').count() == 0
    for isbn in isbns:
        assert Libro.query.filter_by(isbn=isbn).first().stock_disponible == 1


def test_no_permite_registrar_una_lista_vacia(
    client, db, bibliotecario_logueado, configuracion, estudiante
):
    respuesta = _registrar_prestamo(client, estudiante.cedula, [])

    assert 'al menos un libro' in respuesta.get_data(as_text=True)
    assert Prestamo.query.count() == 0


# -------------------------------------------------------------- devolucion

def test_devolucion_parcial_y_luego_total(
    client, db, bibliotecario_logueado, configuracion, estudiante, crear_libro
):
    isbns = [
        crear_libro('9780000000051', 'Libro 1').isbn,
        crear_libro('9780000000052', 'Libro 2').isbn,
        crear_libro('9780000000053', 'Libro 3').isbn,
    ]
    _registrar_prestamo(client, estudiante.cedula, isbns)

    prestamos = Prestamo.query.order_by(Prestamo.id).all()
    assert len(prestamos) == 3
    representante = prestamos[0].id

    # --- Devolucion PARCIAL: solo los dos primeros libros.
    respuesta = client.post(
        f'/bibliotecario/devoluciones/operacion/{representante}',
        data={
            'prestamos': [str(prestamos[0].id), str(prestamos[1].id)],
            f'estado_{prestamos[0].id}': 'bueno',
            f'estado_{prestamos[1].id}': 'bueno',
        },
        follow_redirects=True,
    )
    assert 'Devolución parcial registrada' in respuesta.get_data(as_text=True)

    db.session.expire_all()
    estados = {p.id: p.estado for p in Prestamo.query.all()}
    assert estados[prestamos[0].id] == 'devuelto'
    assert estados[prestamos[1].id] == 'devuelto'
    assert estados[prestamos[2].id] == 'activo'

    # El detalle refleja el estado derivado, sin columna extra en la BD.
    detalle = client.get(f'/bibliotecario/prestamos/{representante}/detalle')
    assert 'Devolución parcial' in detalle.get_data(as_text=True)

    # --- Devolucion TOTAL: el libro que quedaba.
    respuesta = client.post(
        f'/bibliotecario/devoluciones/operacion/{representante}',
        data={
            'prestamos': [str(prestamos[2].id)],
            f'estado_{prestamos[2].id}': 'bueno',
        },
        follow_redirects=True,
    )
    assert 'Devolución completada' in respuesta.get_data(as_text=True)

    db.session.expire_all()
    assert Prestamo.query.filter_by(estado='devuelto').count() == 3

    detalle = client.get(f'/bibliotecario/prestamos/{representante}/detalle')
    assert 'Devolución completa' in detalle.get_data(as_text=True)

    # El stock vuelve a estar completo tras devolver todo en buen estado.
    for isbn in isbns:
        libro = Libro.query.filter_by(isbn=isbn).first()
        assert libro.stock_disponible == libro.stock_total


def test_devolucion_con_estado_individual_por_libro(
    client, db, bibliotecario_logueado, configuracion, estudiante, crear_libro
):
    """Cada libro del lote lleva su propio estado: bueno / dañado / perdido."""
    isbns = [
        crear_libro('9780000000061', 'Libro bueno').isbn,
        crear_libro('9780000000062', 'Libro dañado').isbn,
        crear_libro('9780000000063', 'Libro perdido').isbn,
    ]
    _registrar_prestamo(client, estudiante.cedula, isbns)

    prestamos = Prestamo.query.order_by(Prestamo.id).all()
    representante = prestamos[0].id

    client.post(
        f'/bibliotecario/devoluciones/operacion/{representante}',
        data={
            'prestamos': [str(p.id) for p in prestamos],
            f'estado_{prestamos[0].id}': 'bueno',
            f'estado_{prestamos[1].id}': 'dañado',
            f'estado_{prestamos[2].id}': 'perdido',
            f'observacion_{prestamos[1].id}': 'Portada rota',
        },
        follow_redirects=True,
    )

    db.session.expire_all()
    estados = {p.ejemplar.libro.isbn: p.ejemplar.estado for p in Prestamo.query.all()}
    assert estados['9780000000061'] == 'disponible'
    assert estados['9780000000062'] == 'dañado'
    assert estados['9780000000063'] == 'baja'

    # El libro en buen estado vuelve al stock; el dañado y el perdido no.
    assert Libro.query.filter_by(isbn='9780000000061').first().stock_disponible == 1
    assert Libro.query.filter_by(isbn='9780000000062').first().stock_disponible == 0
    perdido = Libro.query.filter_by(isbn='9780000000063').first()
    assert perdido.stock_disponible == 0
    assert perdido.stock_total == 0


# ---------------------------------------------------- compatibilidad previa

def test_prestamo_antiguo_sin_grupo_sigue_funcionando(
    client, db, bibliotecario_logueado, configuracion, estudiante, crear_libro
):
    """Un prestamo con grupo_prestamo NULL se trata como operacion de un libro."""
    libro = crear_libro('9780000000071', 'Libro anterior a la funcionalidad')
    ejemplar = Ejemplar.query.filter_by(libro_id=libro.id).first()

    antiguo = Prestamo(
        codigo_prestamo='P-2025-0001',
        estudiante_id=estudiante.id,
        ejemplar_id=ejemplar.id,
        bibliotecario_id=bibliotecario_logueado.id,
        fecha_limite=date.today() + timedelta(days=7),
        grupo_prestamo=None,
    )
    db.session.add(antiguo)
    db.session.commit()

    listado = client.get('/bibliotecario/prestamos')
    assert 'P-2025-0001' in listado.get_data(as_text=True)

    detalle = client.get(f'/bibliotecario/prestamos/{antiguo.id}/detalle')
    texto = detalle.get_data(as_text=True)
    assert detalle.status_code == 200
    assert 'P-2025-0001' in texto
    assert 'Préstamo individual' in listado.get_data(as_text=True)

    respuesta = client.post(
        f'/bibliotecario/devoluciones/operacion/{antiguo.id}',
        data={'prestamos': [str(antiguo.id)], f'estado_{antiguo.id}': 'bueno'},
        follow_redirects=True,
    )
    assert 'Devolución completada' in respuesta.get_data(as_text=True)

    db.session.expire_all()
    assert db.session.get(Prestamo, antiguo.id).estado == 'devuelto'
