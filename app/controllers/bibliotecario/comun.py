"""
Utilidades compartidas por los controladores de prestamos y devoluciones.

Aqui vive la logica que ambos modulos necesitan (cupos del estudiante, edad,
agrupacion de prestamos por operacion y estado derivado de la operacion) para
no duplicarla ni dejar que se desincronice entre pantallas.

Sobre las OPERACIONES: un prestamo por libro/ejemplar se conserva tal cual
(trazabilidad, fechas, multas y devolucion individuales). Los prestamos
creados en un mismo registro comparten `Prestamo.grupo_prestamo`. Los
prestamos anteriores a esa columna tienen NULL y se tratan como una operacion
de un solo libro, sin necesidad de migrar datos.
"""
from datetime import date

from app.extensions import db
from app.models import ConfiguracionSistema, Estudiante, Prestamo
# Reexportadas para no tocar los imports de quien ya las usa desde aqui
# (app/controllers/bibliotecario/prestamos.py). Su definicion real vive en
# app/presentacion.py: son presentacion pura (avatar, edad), no logica de
# prestamos, y estudiante/perfil.py tambien las necesita.
from app.presentacion import calcular_edad, iniciales  # noqa: F401

# Un prestamo "ocupa cupo" mientras no se haya devuelto: tanto 'activo' como
# 'vencido' significan que el estudiante todavia tiene el libro.
ESTADOS_PENDIENTES = ('activo', 'vencido')

# Tope usado SOLO cuando configuracion_sistema.max_prestamos_activos falta o
# tiene un valor invalido. Coincide con el que siembra database/seed.py, para
# que un despliegue sin configurar se comporte como el sistema espera en vez
# de quedarse sin limite. El valor real, si es valido, siempre manda.
MAX_PRESTAMOS_POR_DEFECTO = 3


def max_prestamos_activos():
    """
    Limite de prestamos simultaneos por estudiante.

    Sigue siendo configurable: manda el valor de
    configuracion_sistema.max_prestamos_activos siempre que sea un entero
    positivo. Si la fila falta, es NULL, no es numerica o no es positiva, se
    usa MAX_PRESTAMOS_POR_DEFECTO en vez de quedarse sin limite: una
    configuracion rota no debe desactivar en silencio la regla de negocio.
    """
    config = ConfiguracionSistema.query.filter_by(clave='max_prestamos_activos').first()
    if config is None:
        return MAX_PRESTAMOS_POR_DEFECTO
    try:
        maximo = int(config.valor)
    except (TypeError, ValueError):
        return MAX_PRESTAMOS_POR_DEFECTO
    # Un 0 o un negativo dejarian a todos sin poder pedir libros (o, peor,
    # se interpretarian como "sin limite"): tampoco son configuraciones validas.
    return maximo if maximo > 0 else MAX_PRESTAMOS_POR_DEFECTO


def contar_prestamos_pendientes(estudiante_id):
    return Prestamo.query.filter(
        Prestamo.estudiante_id == estudiante_id,
        Prestamo.estado.in_(ESTADOS_PENDIENTES),
    ).count()


def contar_prestamos_vencidos(estudiante_id):
    return Prestamo.query.filter_by(estudiante_id=estudiante_id, estado='vencido').count()


def calcular_cupos(estudiante_id):
    """Devuelve (activos, maximo, cupos_disponibles). maximo/cupos = None si no hay limite."""
    activos = contar_prestamos_pendientes(estudiante_id)
    maximo = max_prestamos_activos()
    if maximo is None:
        return activos, None, None
    return activos, maximo, max(maximo - activos, 0)


def clave_operacion(prestamo):
    """Identificador de la operacion: el grupo, o el propio prestamo si es NULL."""
    return prestamo.grupo_prestamo or f'P#{prestamo.id}'


def prestamos_de_operacion(prestamo):
    """Todos los prestamos de la operacion a la que pertenece `prestamo`."""
    if not prestamo.grupo_prestamo:
        return [prestamo]
    return (
        Prestamo.query.filter_by(grupo_prestamo=prestamo.grupo_prestamo)
        .order_by(Prestamo.id)
        .all()
    )


def resumen_operacion(prestamos, hoy=None):
    """
    Estado DERIVADO de una operacion a partir de sus prestamos individuales.

    No se guarda en BD ninguna columna de "devolucion parcial": se calcula
    contando cuantos prestamos del grupo ya tienen estado 'devuelto'.
    """
    hoy = hoy or date.today()
    prestamos = sorted(prestamos, key=lambda p: p.id)
    primero = prestamos[0]

    total = len(prestamos)
    devueltos = sum(1 for p in prestamos if p.estado == 'devuelto')
    pendientes = total - devueltos
    vencida = any(p.estado != 'devuelto' and p.fecha_limite < hoy for p in prestamos)

    if pendientes == 0:
        estado, badge = 'Devolución completa', 'success'
    elif devueltos > 0:
        estado, badge = 'Devolución parcial', 'warning'
    elif vencida:
        estado, badge = 'Vencido', 'danger'
    else:
        estado, badge = 'Activo', 'primary'

    fechas_limite = [p.fecha_limite for p in prestamos if p.estado != 'devuelto']

    return {
        'clave': clave_operacion(primero),
        'codigo': primero.grupo_prestamo or primero.codigo_prestamo,
        'es_grupo': bool(primero.grupo_prestamo),
        'representante_id': primero.id,
        'estudiante': primero.estudiante,
        'prestamos': prestamos,
        'total': total,
        'devueltos': devueltos,
        'pendientes': pendientes,
        'vencida': vencida,
        'estado': estado,
        'estado_badge': badge,
        'fecha_prestamo': primero.fecha_prestamo,
        'fecha_limite': min(fechas_limite) if fechas_limite else max(p.fecha_limite for p in prestamos),
    }


def agrupar_prestamos(prestamos_base, hoy=None):
    """
    Agrupa una lista de prestamos en operaciones, conservando el orden recibido.

    Para los prestamos con grupo se cargan TAMBIEN los hermanos que no estaban
    en la lista base (p. ej. los ya devueltos), para que el conteo de
    devueltos/pendientes de la operacion sea correcto.
    """
    grupos = {p.grupo_prestamo for p in prestamos_base if p.grupo_prestamo}
    hermanos = {}
    if grupos:
        for prestamo in Prestamo.query.filter(Prestamo.grupo_prestamo.in_(grupos)).all():
            hermanos.setdefault(prestamo.grupo_prestamo, []).append(prestamo)

    operaciones = []
    vistos = set()
    for prestamo in prestamos_base:
        clave = clave_operacion(prestamo)
        if clave in vistos:
            continue
        vistos.add(clave)
        del_grupo = hermanos.get(prestamo.grupo_prestamo) if prestamo.grupo_prestamo else None
        operaciones.append(resumen_operacion(del_grupo or [prestamo], hoy=hoy))
    return operaciones


def generar_codigo_grupo():
    """Siguiente codigo de operacion del anio en curso: 'GRP-<anio>-0001'."""
    anio = date.today().year
    prefijo = f'GRP-{anio}-'
    ultimo = (
        db.session.query(db.func.max(Prestamo.grupo_prestamo))
        .filter(Prestamo.grupo_prestamo.like(f'{prefijo}%'))
        .scalar()
    )
    siguiente = 1
    if ultimo:
        try:
            siguiente = int(ultimo[len(prefijo):]) + 1
        except (TypeError, ValueError):
            siguiente = 1
    return f'{prefijo}{siguiente:04d}'


# ---------------------------------------------------------------------------
# Listado paginado de OPERACIONES (prestamos y devoluciones)
# ---------------------------------------------------------------------------

# Estados de operacion que aceptan los listados. 'todas' no filtra.
ESTADOS_OPERACION = ('pendientes', 'completadas', 'vencidas', 'todas')


def _clave_operacion_sql():
    """
    Misma clave que clave_operacion(), pero calculada en SQL.

    Agrupa por `grupo_prestamo` y, cuando es NULL (prestamos anteriores a la
    funcionalidad), por el propio id: cada uno queda como su propia operacion.
    """
    return db.func.coalesce(
        Prestamo.grupo_prestamo,
        db.func.concat('P#', db.cast(Prestamo.id, db.String)),
    )


def paginar_operaciones(termino='', estado='todas', page=1, per_page=10, hoy=None):
    """
    Devuelve (paginacion, operaciones) filtrando y paginando EN BACKEND.

    La consulta agrupa los prestamos por operacion y pagina sobre esas
    operaciones (no sobre prestamos sueltos), asi una operacion de 4 libros
    ocupa una fila y no cuatro. Los estados 'pendientes'/'completadas' se
    calculan con HAVING sobre el grupo completo: no hay ninguna columna de
    estado derivado en la base de datos.
    """
    hoy = hoy or date.today()
    clave = _clave_operacion_sql()

    total_libros = db.func.count(Prestamo.id)
    devueltos = db.func.count(Prestamo.id).filter(Prestamo.estado == 'devuelto')
    vencidos = db.func.count(Prestamo.id).filter(
        db.and_(Prestamo.estado != 'devuelto', Prestamo.fecha_limite < hoy)
    )
    primero = db.func.min(Prestamo.id)

    consulta = db.select(primero).group_by(clave)

    if termino:
        patron = f'%{termino}%'
        # El termino se busca en CUALQUIER prestamo de la operacion (codigo del
        # prestamo, codigo de la operacion, cedula o nombre del estudiante) y se
        # filtra por clave para que el grupo llegue entero al HAVING.
        coincidencias = (
            db.select(clave)
            .join(Estudiante, Estudiante.id == Prestamo.estudiante_id)
            .where(db.or_(
                Prestamo.codigo_prestamo.ilike(patron),
                Prestamo.grupo_prestamo.ilike(patron),
                Estudiante.cedula.ilike(patron),
                Estudiante.nombres.ilike(patron),
                Estudiante.apellidos.ilike(patron),
                (Estudiante.nombres + ' ' + Estudiante.apellidos).ilike(patron),
            ))
        )
        consulta = consulta.where(clave.in_(coincidencias))

    if estado == 'pendientes':
        consulta = consulta.having(devueltos < total_libros)
    elif estado == 'completadas':
        consulta = consulta.having(devueltos == total_libros)
    elif estado == 'vencidas':
        consulta = consulta.having(vencidos > 0)

    # Lo mas reciente primero: el id del primer prestamo marca cuando se creo
    # la operacion.
    consulta = consulta.order_by(primero.desc())

    paginacion = db.paginate(consulta, page=page, per_page=per_page, error_out=False)

    operaciones = []
    if paginacion.items:
        encontrados = {
            prestamo.id: prestamo
            for prestamo in Prestamo.query.filter(Prestamo.id.in_(paginacion.items)).all()
        }
        representantes = [
            encontrados[identificador]
            for identificador in paginacion.items if identificador in encontrados
        ]
        operaciones = agrupar_prestamos(representantes, hoy=hoy)

    return paginacion, operaciones
