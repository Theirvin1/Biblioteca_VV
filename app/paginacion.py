"""
Helpers de paginacion y filtros para los listados.

Todos los listados paginan y filtran EN BACKEND (query.filter/order_by/paginate);
aqui solo se centraliza la lectura segura de los parametros GET para que un
`?page=abc` o un `?estado=<script>` no reviente la pagina ni cambie la consulta.
"""
from datetime import date

from app.extensions import db

# Registros por pagina en los listados principales del bibliotecario.
POR_PAGINA = 10

# El catalogo del estudiante muestra tarjetas en grilla de 3 columnas:
# 15 deja filas completas (5 x 3) en cada pagina.
POR_PAGINA_CATALOGO = 15

# Tope de pagina. Un `?page=99999999999999999999` se convertia en un entero de
# Python sin problema y llegaba tal cual al OFFSET de la consulta, donde
# PostgreSQL lo rechaza por desbordar bigint: error 500 con un simple cambio
# de URL. Con el tope, una pagina absurda se comporta como la ultima pagina
# posible (vacia), no como un error. No afecta a la paginacion normal: ningun
# listado de este sistema llega a 100000 paginas (un millon de registros).
MAX_PAGINA = 100000


def pagina_actual(request):
    """Numero de pagina pedido por GET. Cualquier valor invalido -> pagina 1."""
    pagina = request.args.get('page', type=int)
    if pagina is None or pagina < 1:
        return 1
    return min(pagina, MAX_PAGINA)


def texto_filtro(request, nombre, maximo=100):
    """Lee un filtro de texto libre, recortado a un largo razonable."""
    return (request.args.get(nombre) or '').strip()[:maximo]


def opcion_filtro(request, nombre, permitidas, por_defecto=''):
    """Lee un filtro de lista cerrada; si no esta en `permitidas`, usa el valor por defecto."""
    valor = (request.args.get(nombre) or '').strip()
    return valor if valor in permitidas else por_defecto


def entero_filtro(request, nombre):
    """Lee un filtro numerico (ids de carrera/categoria). Invalido o <= 0 -> None."""
    valor = request.args.get(nombre, type=int)
    return valor if valor and valor > 0 else None


def fecha_filtro(request, nombre):
    """Lee un filtro de fecha (input type=date, 'YYYY-MM-DD'). Invalido -> None."""
    valor = (request.args.get(nombre) or '').strip()
    try:
        return date.fromisoformat(valor) if valor else None
    except ValueError:
        return None


def id_nuevo(request):
    """
    Id del registro recien creado, que llega por querystring tras el redirect.

    Sirve para pintar el badge "Nuevo" sin guardar nada en la base de datos:
    en cuanto el usuario navega (otra pagina, otro filtro) el parametro
    desaparece y el indicador tambien.
    """
    return request.args.get('nuevo', type=int)


class PaginacionManual:
    """
    Objeto compatible con el macro shared/_paginacion.html (mismos atributos y
    `iter_pages()` que `flask_sqlalchemy.pagination.Pagination`), para paginar
    a mano un SELECT que no es un simple `select(Modelo)`.

    Hace falta porque `db.paginate(select)` aplica `.scalars()` al resultado
    (solo sirve para selects de una entidad/columna); un SELECT con varias
    columnas -como el UNION del historial de movimientos- necesita construir
    el conteo y la pagina manualmente y envolver el resultado con esta clase.
    """

    def __init__(self, items, total, page, per_page):
        self.items = items
        self.total = total
        self.page = page
        self.per_page = per_page

    @property
    def pages(self):
        if not self.total:
            return 0
        return -(-self.total // self.per_page)  # ceil sin importar math

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    @property
    def prev_num(self):
        return self.page - 1 if self.has_prev else None

    @property
    def next_num(self):
        return self.page + 1 if self.has_next else None

    def iter_pages(self, left_edge=2, left_current=2, right_current=4, right_edge=2):
        """Misma logica que Pagination.iter_pages de Flask-SQLAlchemy 3.x."""
        pages_end = self.pages + 1
        if pages_end == 1:
            return

        left_end = min(1 + left_edge, pages_end)
        yield from range(1, left_end)
        if left_end == pages_end:
            return

        mid_start = max(left_end, self.page - left_current)
        mid_end = min(self.page + right_current + 1, pages_end)
        if mid_start - left_end > 0:
            yield None
        yield from range(mid_start, mid_end)
        if mid_end == pages_end:
            return

        right_start = max(mid_end, pages_end - right_edge)
        if right_start - mid_end > 0:
            yield None
        yield from range(right_start, pages_end)


def paginar_select(consulta_base, orden, page, per_page=POR_PAGINA):
    """
    Pagina a mano un SELECT de SQLAlchemy Core con varias columnas (agregados,
    UNION, joins armados a mano) que ya trae su WHERE aplicado.

    `db.paginate(select)` no sirve para esto: siempre aplica `.scalars()` al
    resultado, que solo tiene sentido para selects de una sola entidad/columna
    (ver PaginacionManual). Aqui se cuenta el total, se aplica ORDER BY +
    LIMIT + OFFSET, y se devuelve (filas, PaginacionManual) listo para pasar
    a la plantilla junto con `columnas`/`filas` para tabla_dinamica.
    """
    total = db.session.execute(
        db.select(db.func.count()).select_from(consulta_base.subquery())
    ).scalar()

    filas = db.session.execute(
        consulta_base.order_by(*orden).limit(per_page).offset((page - 1) * per_page)
    ).all()

    return filas, PaginacionManual(items=filas, total=total, page=page, per_page=per_page)


def argumentos_activos(**filtros):
    """
    Filtros vigentes, listos para reinyectarlos en los enlaces de paginacion.

    Se descartan los vacios para no arrastrar `?q=&estado=` en cada URL. Nunca
    incluye `page` ni `nuevo`: la pagina la pone el propio enlace y el badge
    "Nuevo" debe desaparecer al navegar.
    """
    return {clave: valor for clave, valor in filtros.items() if valor not in (None, '', 0)}
