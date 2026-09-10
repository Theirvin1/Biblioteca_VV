"""
Paginacion del catalogo del estudiante (/estudiante/catalogo).

Replica el patron de /gerente/usuarios: filtros por GET en backend,
15 tarjetas por pagina (grilla 3x5) y macro control_paginacion.
"""
import pytest

from app.models import CategoriaLibro, Editorial, Libro

pytestmark = pytest.mark.requiere_setup_sql


def _isbn_base12(semilla):
    base = f'9780000{semilla:05d}'
    assert len(base) == 12
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(base))
    return base + str((10 - total % 10) % 10)


@pytest.fixture
def catalogo_paginado(db):
    editorial = Editorial(nombre='Editorial Paginacion')
    cat_a = CategoriaLibro(nombre='Categoria Paga')
    cat_b = CategoriaLibro(nombre='Categoria Pagb')
    db.session.add_all([editorial, cat_a, cat_b])
    db.session.flush()
    for i in range(1, 18):
        db.session.add(Libro(
            isbn=_isbn_base12(i),
            titulo=f'Pag Libro {i:02d}',
            editorial_id=editorial.id,
            categoria_id=cat_a.id if i % 2 else cat_b.id,
            stock_total=1,
            stock_disponible=1,
        ))
    db.session.add(Libro(
        isbn=_isbn_base12(99),
        titulo='Pag Libro Inactivo',
        editorial_id=editorial.id,
        categoria_id=cat_a.id,
        stock_total=1,
        stock_disponible=0,
        activo=False,
    ))
    db.session.commit()
    return cat_a, cat_b


def _entrar(client, login):
    login('1234567899', 'ClaveSegura123')


def test_primera_pagina_muestra_15(client, login, usuario_estudiante, catalogo_paginado):
    _entrar(client, login)
    texto = client.get('/estudiante/catalogo').get_data(as_text=True)
    assert 'Mostrando 1-15 de 17 libros' in texto
    assert 'Pag Libro 01' in texto
    assert 'Pag Libro 15' in texto
    assert 'Pag Libro 16' not in texto
    assert 'Pag Libro Inactivo' not in texto


def test_segunda_pagina_muestra_el_resto(client, login, usuario_estudiante, catalogo_paginado):
    _entrar(client, login)
    texto = client.get('/estudiante/catalogo?page=2').get_data(as_text=True)
    assert 'Mostrando 16-17 de 17 libros' in texto
    assert 'Pag Libro 16' in texto
    assert 'Pag Libro 17' in texto
    assert 'Pag Libro 01' not in texto


def test_filtro_por_titulo(client, login, usuario_estudiante, catalogo_paginado):
    _entrar(client, login)
    texto = client.get('/estudiante/catalogo?q=Pag+Libro+01').get_data(as_text=True)
    assert 'Pag Libro 01' in texto
    assert 'Pag Libro 02' not in texto
    assert 'Mostrando 1-1 de 1 libros' in texto


def test_filtro_por_categoria(client, login, usuario_estudiante, catalogo_paginado):
    _entrar(client, login)
    cat_a, _cat_b = catalogo_paginado
    texto = client.get(f'/estudiante/catalogo?categoria_id={cat_a.id}').get_data(as_text=True)
    assert 'Mostrando 1-9 de 9 libros' in texto
    assert 'Pag Libro 01' in texto  # impar -> cat_a


def test_paginacion_conserva_filtros(client, login, usuario_estudiante, catalogo_paginado):
    _entrar(client, login)
    texto = client.get('/estudiante/catalogo?q=Pag+Libro&page=1').get_data(as_text=True)
    assert 'Mostrando 1-15 de 17 libros' in texto
    assert 'page=2' in texto and 'q=Pag' in texto


def test_pagina_invalida_cae_en_pagina_1(client, login, usuario_estudiante, catalogo_paginado):
    _entrar(client, login)
    for pagina in ('abc', '0', '-3'):
        texto = client.get(f'/estudiante/catalogo?page={pagina}').get_data(as_text=True)
        assert 'Mostrando 1-15 de 17 libros' in texto


def test_sin_resultados_muestra_mensaje(client, login, usuario_estudiante, catalogo_paginado):
    _entrar(client, login)
    texto = client.get('/estudiante/catalogo?q=zzz+sin+coincidencias').get_data(as_text=True)
    assert 'No se encontraron libros con esos criterios.' in texto
