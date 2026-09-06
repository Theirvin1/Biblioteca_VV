"""
Funciones puras de presentacion (avatar de iniciales, edad calculada a partir
de la fecha de nacimiento), reutilizadas por mas de un modulo.

Vivian antes solo en app/controllers/bibliotecario/comun.py, pero
estudiante/perfil.py tambien las necesita para su propio avatar y no tiene
sentido que el modulo de estudiante dependa de un modulo interno de
bibliotecario para dibujar una iniciales o calcular una edad: ambas cosas no
son logica de prestamos/devoluciones, son presentacion pura. comun.py las
sigue reexportando (ver mas abajo) para no tocar sus otros imports.
"""
from datetime import date


def iniciales(nombres, apellidos):
    """Iniciales para el avatar circular (el modelo no tiene fotografia)."""
    letras = ''
    for texto in (nombres, apellidos):
        texto = (texto or '').strip()
        if texto:
            letras += texto[0].upper()
    return letras or '?'


def calcular_edad(fecha_nacimiento, hoy=None):
    """Edad en anios a partir de la fecha de nacimiento (no se guarda en BD)."""
    if not fecha_nacimiento:
        return None
    hoy = hoy or date.today()
    return hoy.year - fecha_nacimiento.year - (
        (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day)
    )
