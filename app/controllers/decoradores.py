from functools import wraps
from flask import redirect, url_for
from flask_login import current_user


def requiere_rol(*roles_permitidos):
    def decorador(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if current_user.rol not in roles_permitidos:
                return redirect(url_for(_ruta_inicio_por_rol(current_user.rol)))
            return f(*args, **kwargs)
        return wrapper
    return decorador


def _ruta_inicio_por_rol(rol):
    rutas = {
        'bibliotecario': 'bibliotecario.inicio',
        'estudiante': 'estudiante.listado_catalogo',
        'gerente': 'gerente.dashboard',
    }
    return rutas.get(rol, 'auth.login')