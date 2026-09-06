"""
Helpers de seguridad compartidos.

Aqui vive la generacion de claves temporales, que necesitan tanto el registro
de estudiantes (bibliotecario) como el restablecimiento de contraseña
(gerente). La clave se genera en memoria, se guarda SOLO como hash
(werkzeug/scrypt) y se muestra una unica vez en la respuesta de esa peticion:
nunca se persiste en la base de datos, ni en session, ni en auditoria.
"""
import secrets

from flask import make_response

# Alfabeto explicito sin caracteres ambiguos al leer/dictar una clave:
# se excluyen 0/O/o, 1/l/I. Quedan 32 letras + 8 digitos = 54 simbolos.
ALFABETO_TEMPORAL = (
    'ABCDEFGHJKLMNPQRSTUVWXYZ'   # sin I ni O
    'abcdefghijkmnpqrstuvwxyz'   # sin l ni o
    '23456789'                   # sin 0 ni 1
)

LARGO_PASSWORD_TEMPORAL = 12


def generar_password_temporal(largo=LARGO_PASSWORD_TEMPORAL):
    """
    Clave temporal de un solo uso, con `secrets` (CSPRNG, nunca `random`).

    Con 54 simbolos posibles y 12 caracteres da ~69 bits de entropia, de
    sobra para una clave que ademas obliga a cambiarla en el primer ingreso
    (debe_cambiar_password) y esta protegida por el bloqueo tras 5 intentos
    fallidos del login.
    """
    return ''.join(secrets.choice(ALFABETO_TEMPORAL) for _ in range(largo))


def respuesta_sin_cache(html):
    """
    Envuelve un HTML que contiene una clave temporal para que ni el navegador
    ni un proxy intermedio lo almacenen.

    Se aplica SOLO a las respuestas que muestran una contraseña (registro de
    estudiante y restablecimiento del gerente), no a todo el sistema: el resto
    de paginas si pueden cachearse normalmente.
    """
    respuesta = make_response(html)
    respuesta.headers['Cache-Control'] = 'no-store, private, max-age=0'
    respuesta.headers['Pragma'] = 'no-cache'          # compatibilidad HTTP/1.0
    respuesta.headers['Expires'] = '0'
    return respuesta
