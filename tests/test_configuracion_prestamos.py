"""
Fallback de configuracion_sistema.max_prestamos_activos.

El valor configurado sigue mandando cuando es valido. Lo que se corrige aqui
es el caso contrario: antes, si la fila faltaba o tenia un valor invalido, el
helper devolvia None y el sistema lo interpretaba como "sin limite", saltandose
en silencio la regla de negocio. Ahora cae a MAX_PRESTAMOS_POR_DEFECTO.
"""
from datetime import date

import pytest

from app.controllers.bibliotecario.comun import (
    MAX_PRESTAMOS_POR_DEFECTO, max_prestamos_activos,
)
from app.models import (
    CategoriaLibro, ConfiguracionSistema, Editorial, Ejemplar, Estudiante,
    Libro, Prestamo,
)

pytestmark = pytest.mark.requiere_setup_sql


@pytest.fixture
def configurar(db):
    """Escribe (o deja ausente) la clave max_prestamos_activos."""
    def _configurar(valor):
        ConfiguracionSistema.query.filter_by(clave='max_prestamos_activos').delete()
        if valor is not None:
            db.session.add(ConfiguracionSistema(clave='max_prestamos_activos', valor=valor))
        db.session.commit()
    return _configurar


@pytest.fixture
def escenario_prestamo(db, carrera_prueba, usuario_bibliotecario):
    """Estudiante + libros disponibles, con el resto de la configuracion sembrada."""
    for clave, valor in [('plazo_prestamo_dias', '7'), ('multa_diaria', '0.50')]:
        db.session.add(ConfiguracionSistema(clave=clave, valor=valor))

    editorial = Editorial(nombre='Editorial Config')
    categoria = CategoriaLibro(nombre='Categoria Config')
    db.session.add_all([editorial, categoria])
    db.session.flush()

    estudiante = Estudiante(
        cedula='0912345678', nombres='Config', apellidos='Prueba',
        correo='config.prueba@uteq.edu.ec', carrera_id=carrera_prueba.id,
    )
    db.session.add(estudiante)
    db.session.flush()

    isbns = []
    for indice in range(6):
        libro = Libro(
            isbn=f'978700000{indice:04d}', titulo=f'Libro config {indice}',
            editorial_id=editorial.id, categoria_id=categoria.id,
            stock_total=1, stock_disponible=1,
        )
        db.session.add(libro)
        db.session.flush()
        db.session.add(Ejemplar(
            libro_id=libro.id, codigo_ejemplar=f'EJCF-{indice:04d}',
            fecha_adquisicion=date.today(),
        ))
        isbns.append(libro.isbn)
    db.session.commit()

    return estudiante, isbns


def _registrar_prestamo(client, cedula, isbns):
    return client.post('/bibliotecario/prestamos/nuevo', data={
        'cedula': cedula,
        'isbns': ','.join(isbns),
        'observaciones': '',
    }, follow_redirects=True)


# ------------------------------------------------------- valor del helper

def test_valor_valido_personalizado_se_respeta(db, configurar):
    configurar('5')
    assert max_prestamos_activos() == 5

    configurar('1')
    assert max_prestamos_activos() == 1


def test_fila_ausente_usa_el_fallback(db, configurar):
    configurar(None)  # no existe la clave
    assert max_prestamos_activos() == MAX_PRESTAMOS_POR_DEFECTO
    assert MAX_PRESTAMOS_POR_DEFECTO == 3


@pytest.mark.parametrize('valor_invalido', ['abc', '', '  ', '3.5', 'tres', '0', '-1', '-10'])
def test_valores_invalidos_usan_el_fallback(db, configurar, valor_invalido):
    """Texto, vacio, decimal, cero y negativos: nunca deben desactivar el limite."""
    configurar(valor_invalido)
    assert max_prestamos_activos() == MAX_PRESTAMOS_POR_DEFECTO


def test_el_helper_nunca_devuelve_none(db, configurar):
    """Antes devolvia None ("sin limite"); ahora siempre hay un tope efectivo."""
    for valor in (None, 'abc', '0', '-4', '7'):
        configurar(valor)
        assert max_prestamos_activos() is not None


# ------------------------------------------- efecto real sobre el prestamo

def test_sin_configuracion_no_se_puede_exceder_el_fallback(
    client, db, login, usuario_bibliotecario, configurar, escenario_prestamo
):
    """Sin la fila de configuracion, el limite efectivo debe ser 3 (no ilimitado)."""
    estudiante, isbns = escenario_prestamo
    configurar(None)

    login('test_bibliotecario', 'ClaveSegura123')
    respuesta = _registrar_prestamo(client, estudiante.cedula, isbns[:4])

    texto = respuesta.get_data(as_text=True)
    assert 'cupo' in texto
    assert Prestamo.query.count() == 0, 'no debia registrarse ningun prestamo'

    # Con 3 libros (el tope del fallback) si entra.
    respuesta = _registrar_prestamo(client, estudiante.cedula, isbns[:3])
    assert 'registrado correctamente' in respuesta.get_data(as_text=True)
    assert Prestamo.query.count() == 3


def test_configuracion_invalida_no_desactiva_el_limite(
    client, db, login, usuario_bibliotecario, configurar, escenario_prestamo
):
    estudiante, isbns = escenario_prestamo
    configurar('abc')

    login('test_bibliotecario', 'ClaveSegura123')
    respuesta = _registrar_prestamo(client, estudiante.cedula, isbns[:5])

    assert 'cupo' in respuesta.get_data(as_text=True)
    assert Prestamo.query.count() == 0


def test_configuracion_valida_sigue_mandando_sobre_el_fallback(
    client, db, login, usuario_bibliotecario, configurar, escenario_prestamo
):
    """Con un valor valido de 5 deben poder prestarse 5 libros, no solo 3."""
    estudiante, isbns = escenario_prestamo
    configurar('5')

    login('test_bibliotecario', 'ClaveSegura123')
    respuesta = _registrar_prestamo(client, estudiante.cedula, isbns[:5])

    assert 'registrado correctamente' in respuesta.get_data(as_text=True)
    assert Prestamo.query.count() == 5
