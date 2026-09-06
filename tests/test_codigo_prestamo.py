"""
Regresion del bug de generar_codigo_prestamo().

La version antigua extraia la parte numerica con SUBSTRING(... FROM 10), que
solo leia los DOS ULTIMOS digitos del codigo. Mientras los codigos iban de
0001 a 0099 funcionaba por casualidad ('01'..'99'), pero en cuanto existia
'P-<anio>-0100' esa expresion devolvia '00': el MAX se quedaba en 99 y la
funcion volvia a proponer 0100, un codigo ya usado -> violacion de la
restriccion unica de codigo_prestamo al registrar el siguiente prestamo.

Estas pruebas llaman a la FUNCION REAL de PostgreSQL (la que usa el
controlador), no a una reimplementacion en Python.
"""
from datetime import date

import pytest

from app.models import (
    CategoriaLibro, ConfiguracionSistema, Editorial, Ejemplar, Estudiante,
    Facultad, Carrera, Libro, Prestamo,
)

pytestmark = pytest.mark.requiere_setup_sql


ANIO = date.today().year


def _codigo(numero):
    return f'P-{ANIO}-{numero:04d}'


def _generar(db):
    """Llama a la funcion de PostgreSQL igual que lo hace el controlador."""
    return db.session.execute(db.text('SELECT generar_codigo_prestamo()')).scalar()


@pytest.fixture
def sembrar_codigos(db, datos_prestamo):
    """
    Inserta prestamos reales (con sus ejemplares) con codigos consecutivos.

    Se usan prestamos de verdad y no filas sueltas porque la funcion consulta
    la tabla `prestamos`; los triggers de stock exigen ejemplares disponibles.
    """
    estudiante, bibliotecario, editorial, categoria = datos_prestamo
    contador = {'n': 0}

    def _sembrar(desde, hasta):
        for numero in range(desde, hasta + 1):
            contador['n'] += 1
            indice = contador['n']
            libro = Libro(
                isbn=f'9786000{indice:06d}', titulo=f'Libro codigo {indice}',
                editorial_id=editorial.id, categoria_id=categoria.id,
                stock_total=1, stock_disponible=1,
            )
            db.session.add(libro)
            db.session.flush()
            ejemplar = Ejemplar(
                libro_id=libro.id, codigo_ejemplar=f'EJC-{indice:05d}',
                fecha_adquisicion=date.today(),
            )
            db.session.add(ejemplar)
            db.session.flush()
            db.session.add(Prestamo(
                codigo_prestamo=_codigo(numero),
                estudiante_id=estudiante.id,
                ejemplar_id=ejemplar.id,
                bibliotecario_id=bibliotecario.id,
            ))
            db.session.flush()
        db.session.commit()

    return _sembrar


@pytest.fixture
def datos_prestamo(db, usuario_bibliotecario):
    for clave, valor in [
        ('plazo_prestamo_dias', '7'), ('multa_diaria', '0.50'),
        ('max_prestamos_activos', '500'),
    ]:
        db.session.add(ConfiguracionSistema(clave=clave, valor=valor))

    facultad = Facultad(nombre='Facultad Codigo')
    editorial = Editorial(nombre='Editorial Codigo')
    categoria = CategoriaLibro(nombre='Categoria Codigo')
    db.session.add_all([facultad, editorial, categoria])
    db.session.flush()

    carrera = Carrera(nombre='Carrera Codigo', facultad_id=facultad.id)
    db.session.add(carrera)
    db.session.flush()

    estudiante = Estudiante(
        cedula='0912345678', nombres='Codigo', apellidos='Prueba',
        correo='codigo.prueba@uteq.edu.ec', carrera_id=carrera.id,
    )
    db.session.add(estudiante)
    db.session.commit()

    return estudiante, usuario_bibliotecario, editorial, categoria


# ------------------------------------------------------------ el bug

def test_de_0099_pasa_a_0100(db, sembrar_codigos):
    sembrar_codigos(1, 99)
    assert _generar(db) == _codigo(100)


def test_de_0100_pasa_a_0101_no_repite_0100(db, sembrar_codigos):
    """
    Este es el caso que fallaba: con 0100 ya insertado, la version antigua
    devolvia otra vez P-<anio>-0100 (SUBSTRING FROM 10 -> '00') y el INSERT
    reventaba por codigo_prestamo duplicado.
    """
    sembrar_codigos(1, 100)
    assert _generar(db) == _codigo(101)


def test_de_0101_pasa_a_0102(db, sembrar_codigos):
    sembrar_codigos(1, 101)
    assert _generar(db) == _codigo(102)


def test_de_0098_pasa_a_0099(db, sembrar_codigos):
    sembrar_codigos(1, 98)
    assert _generar(db) == _codigo(99)


def test_de_0999_pasa_a_1000_y_luego_a_1001(db, sembrar_codigos):
    """Cruce de los cuatro digitos: la parte numerica ya no cabe en 2 caracteres."""
    sembrar_codigos(1, 999)
    assert _generar(db) == _codigo(1000)

    sembrar_codigos(1000, 1000)
    assert _generar(db) == _codigo(1001)


def test_el_codigo_generado_no_choca_con_los_existentes(db, sembrar_codigos):
    """El codigo propuesto nunca puede ser uno ya usado (la columna es UNIQUE)."""
    sembrar_codigos(1, 105)

    codigo = _generar(db)
    existentes = {p.codigo_prestamo for p in Prestamo.query.all()}
    assert codigo not in existentes
    assert codigo == _codigo(106)


def test_ignora_codigos_de_otros_anios_y_sufijos_no_numericos(db, sembrar_codigos, datos_prestamo):
    """
    La numeracion es por anio y solo considera sufijos numericos: un codigo
    con sufijo no numerico no debe romper el CAST (antes daba error 500).
    """
    estudiante, bibliotecario, editorial, categoria = datos_prestamo
    sembrar_codigos(1, 5)

    libro = Libro(
        isbn='9786009999999', titulo='Libro raro',
        editorial_id=editorial.id, categoria_id=categoria.id,
        stock_total=2, stock_disponible=2,
    )
    db.session.add(libro)
    db.session.flush()

    for sufijo, codigo in (('A', f'P-{ANIO}-EXTRA'), ('B', f'P-{ANIO - 1}-9999')):
        ejemplar = Ejemplar(
            libro_id=libro.id, codigo_ejemplar=f'EJC-RARO-{sufijo}',
            fecha_adquisicion=date.today(),
        )
        db.session.add(ejemplar)
        db.session.flush()
        db.session.add(Prestamo(
            codigo_prestamo=codigo, estudiante_id=estudiante.id,
            ejemplar_id=ejemplar.id, bibliotecario_id=bibliotecario.id,
        ))
        db.session.flush()
    db.session.commit()

    assert _generar(db) == _codigo(6)


# ----------------------------------------------- concurrencia (advisory lock)

def _claves_del_lock(db):
    """Las mismas claves que usa la funcion: nombre + anio, no un numero magico."""
    return db.session.execute(db.text(
        "SELECT hashtext('generar_codigo_prestamo'), EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER"
    )).one()


def _conexion_cruda(db):
    """Conexion aparte de db.session, para simular otra transaccion real."""
    return db.engine.raw_connection()


def test_generar_codigo_toma_un_advisory_lock_transaccional(db, sembrar_codigos):
    """
    Mientras una transaccion esta generando el codigo, otra NO puede tomar el
    mismo lock; al terminar (COMMIT) queda libre.

    Se comprueba con pg_try_advisory_xact_lock, que responde al instante
    (true/false) en vez de bloquearse: la prueba es determinista, sin sleeps
    ni timeouts.
    """
    sembrar_codigos(1, 5)
    clave_funcion, clave_anio = _claves_del_lock(db)

    generadora = _conexion_cruda(db)
    observadora = _conexion_cruda(db)
    try:
        cursor_a = generadora.cursor()
        cursor_a.execute('SELECT generar_codigo_prestamo()')
        codigo_a = cursor_a.fetchone()[0]
        assert codigo_a == _codigo(6)

        # La transaccion A sigue abierta y retiene el lock.
        cursor_b = observadora.cursor()
        cursor_b.execute('SELECT pg_try_advisory_xact_lock(%s, %s)',
                         (clave_funcion, clave_anio))
        assert cursor_b.fetchone()[0] is False, 'la funcion no tomo el advisory lock'
        observadora.rollback()

        # Al cerrar A el lock se libera solo: es transaccional, no de sesion.
        generadora.commit()

        cursor_b = observadora.cursor()
        cursor_b.execute('SELECT pg_try_advisory_xact_lock(%s, %s)',
                         (clave_funcion, clave_anio))
        assert cursor_b.fetchone()[0] is True, 'el lock no se libero al hacer COMMIT'
        observadora.rollback()
    finally:
        generadora.close()
        observadora.close()


def test_el_advisory_lock_se_libera_tambien_con_rollback(db, sembrar_codigos):
    sembrar_codigos(1, 3)
    clave_funcion, clave_anio = _claves_del_lock(db)

    generadora = _conexion_cruda(db)
    observadora = _conexion_cruda(db)
    try:
        cursor_a = generadora.cursor()
        cursor_a.execute('SELECT generar_codigo_prestamo()')
        cursor_a.fetchone()

        # ROLLBACK (no COMMIT): igual debe soltar el lock.
        generadora.rollback()

        cursor_b = observadora.cursor()
        cursor_b.execute('SELECT pg_try_advisory_xact_lock(%s, %s)',
                         (clave_funcion, clave_anio))
        assert cursor_b.fetchone()[0] is True, 'el lock no se libero al hacer ROLLBACK'
        observadora.rollback()
    finally:
        generadora.close()
        observadora.close()


def test_dos_transacciones_seguidas_no_reciben_el_mismo_codigo(db, sembrar_codigos, datos_prestamo):
    """
    A genera + inserta + confirma; recien entonces B puede generar, y obtiene
    el codigo SIGUIENTE (no el mismo). Es el resultado funcional que protege
    el lock: sin el, B leeria el MAX antes de que A confirmara.
    """
    estudiante, bibliotecario, editorial, categoria = datos_prestamo
    sembrar_codigos(1, 10)

    libro = Libro(
        isbn='9786003333333', titulo='Libro concurrencia',
        editorial_id=editorial.id, categoria_id=categoria.id,
        stock_total=1, stock_disponible=1,
    )
    db.session.add(libro)
    db.session.flush()
    ejemplar = Ejemplar(
        libro_id=libro.id, codigo_ejemplar='EJC-CONC', fecha_adquisicion=date.today()
    )
    db.session.add(ejemplar)
    db.session.commit()
    ejemplar_id, estudiante_id, bibliotecario_id = ejemplar.id, estudiante.id, bibliotecario.id

    primera = _conexion_cruda(db)
    segunda = _conexion_cruda(db)
    try:
        cursor_a = primera.cursor()
        cursor_a.execute('SELECT generar_codigo_prestamo()')
        codigo_a = cursor_a.fetchone()[0]
        cursor_a.execute(
            'INSERT INTO prestamos (codigo_prestamo, estudiante_id, ejemplar_id, bibliotecario_id) '
            'VALUES (%s, %s, %s, %s)',
            (codigo_a, estudiante_id, ejemplar_id, bibliotecario_id),
        )
        primera.commit()

        cursor_b = segunda.cursor()
        cursor_b.execute('SELECT generar_codigo_prestamo()')
        codigo_b = cursor_b.fetchone()[0]
        segunda.rollback()

        assert codigo_a == _codigo(11)
        assert codigo_b == _codigo(12)
        assert codigo_a != codigo_b
    finally:
        primera.close()
        segunda.close()


def test_la_definicion_instalada_usa_advisory_lock_transaccional(db):
    """La funcion realmente instalada en la BD debe traer el lock transaccional."""
    fuente = db.session.execute(db.text(
        "SELECT prosrc FROM pg_proc WHERE proname = 'generar_codigo_prestamo'"
    )).scalar()

    assert 'pg_advisory_xact_lock' in fuente
    # De sesion no: no debe quedar retenido despues del COMMIT.
    assert 'pg_advisory_lock(' not in fuente


# ------------------------------------- el flujo real sigue funcionando

def _registrar_prestamo(client, cedula, isbns):
    return client.post('/bibliotecario/prestamos/nuevo', data={
        'cedula': cedula,
        'isbns': ','.join(isbns),
        'observaciones': '',
    }, follow_redirects=True)


def test_prestamo_normal_funciona_pasado_el_codigo_0100(
    client, db, login, usuario_bibliotecario, datos_prestamo, sembrar_codigos
):
    """Registro real por HTTP con 0100 ya existente: antes daba error de duplicado."""
    estudiante, _, editorial, categoria = datos_prestamo
    sembrar_codigos(1, 100)

    libro = Libro(
        isbn='9786001111111', titulo='Libro despues del 100',
        editorial_id=editorial.id, categoria_id=categoria.id,
        stock_total=1, stock_disponible=1,
    )
    db.session.add(libro)
    db.session.flush()
    db.session.add(Ejemplar(
        libro_id=libro.id, codigo_ejemplar='EJC-POST100', fecha_adquisicion=date.today()
    ))
    db.session.commit()

    login('test_bibliotecario', 'ClaveSegura123')
    respuesta = _registrar_prestamo(client, estudiante.cedula, [libro.isbn])
    assert 'Préstamo registrado correctamente' in respuesta.get_data(as_text=True)

    nuevo = Prestamo.query.filter_by(codigo_prestamo=_codigo(101)).first()
    assert nuevo is not None


def test_prestamo_multiple_genera_codigos_distintos_pasado_el_0100(
    client, db, login, usuario_bibliotecario, datos_prestamo, sembrar_codigos
):
    """Los codigos de una misma operacion deben ser correlativos y distintos."""
    estudiante, _, editorial, categoria = datos_prestamo
    sembrar_codigos(1, 100)

    isbns = []
    for indice in range(3):
        libro = Libro(
            isbn=f'978600222222{indice}', titulo=f'Libro lote {indice}',
            editorial_id=editorial.id, categoria_id=categoria.id,
            stock_total=1, stock_disponible=1,
        )
        db.session.add(libro)
        db.session.flush()
        db.session.add(Ejemplar(
            libro_id=libro.id, codigo_ejemplar=f'EJC-LOTE-{indice}',
            fecha_adquisicion=date.today(),
        ))
        isbns.append(libro.isbn)
    db.session.commit()

    login('test_bibliotecario', 'ClaveSegura123')
    respuesta = _registrar_prestamo(client, estudiante.cedula, isbns)
    assert 'Préstamo registrado correctamente' in respuesta.get_data(as_text=True)

    nuevos = Prestamo.query.filter(
        Prestamo.codigo_prestamo.in_([_codigo(101), _codigo(102), _codigo(103)])
    ).all()
    assert len(nuevos) == 3
    # Un solo grupo y tres codigos distintos dentro de la misma operacion.
    assert len({p.grupo_prestamo for p in nuevos}) == 1
    assert nuevos[0].grupo_prestamo is not None
    assert len({p.codigo_prestamo for p in nuevos}) == 3
