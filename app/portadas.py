"""
Utilidades para subir, validar y mostrar portadas de libros.

Almacenamiento: local, dentro de app/static/uploads/portadas/. Para esta
entrega universitaria es suficiente. En Azure App Service el disco del
contenedor puede no persistir entre despliegues (sobre todo si se usa
"Run From Package"/despliegue por zip, que deja wwwroot de solo lectura),
así que las portadas subidas en producción podrían perderse en el próximo
deploy. Para un entorno real se recomienda migrar a Azure Blob Storage
(guardando ahí el archivo y en `portada_archivo` la URL o el nombre del
blob en vez de una ruta local) — no se implementa ahora porque el
proyecto no tiene esa configuración todavía.
"""
import os
import uuid

from flask import url_for
from werkzeug.utils import secure_filename

EXTENSIONES_PERMITIDAS = {'jpg', 'jpeg', 'png', 'webp'}
TAMANO_MAXIMO_BYTES = 2 * 1024 * 1024  # 2 MB

CARPETA_RELATIVA = 'uploads/portadas'
PLACEHOLDER_RELATIVO = 'img/book-placeholder.svg'

MENSAJE_FORMATO_INVALIDO = 'La portada debe ser una imagen JPG, PNG o WEBP.'
MENSAJE_TAMANO_INVALIDO = 'La imagen no debe superar los 2 MB.'

# Primeros bytes ("magic numbers") de cada formato. No confiamos solo en la
# extension del nombre de archivo ni en el Content-Type que manda el
# navegador (ambos los puede falsificar quien sube el archivo).
_FIRMAS_SIMPLES = (
    b'\xff\xd8\xff',        # JPEG
    b'\x89PNG\r\n\x1a\n',   # PNG
)


class PortadaInvalida(Exception):
    """Se lanza cuando el archivo subido no pasa las validaciones de portada."""


def _extension(nombre_archivo):
    return nombre_archivo.rsplit('.', 1)[-1].lower() if '.' in nombre_archivo else ''


def _extension_permitida(nombre_archivo):
    return _extension(nombre_archivo) in EXTENSIONES_PERMITIDAS


def _firma_valida(cabecera):
    if any(cabecera.startswith(firma) for firma in _FIRMAS_SIMPLES):
        return True
    # WEBP: 'RIFF' + 4 bytes de tamaño + 'WEBP'
    if cabecera[:4] == b'RIFF' and cabecera[8:12] == b'WEBP':
        return True
    return False


def guardar_portada(archivo, carpeta_absoluta):
    """
    Valida y guarda la portada subida por el bibliotecario.

    `archivo` es el FileStorage de WTForms/Werkzeug (form.portada.data).
    Devuelve la ruta relativa a app/static/ para guardar en
    Libro.portada_archivo, o None si no se subió ningún archivo.
    Lanza PortadaInvalida (con mensaje en español) si el archivo no es
    una imagen válida o supera el tamaño máximo.
    """
    if not archivo or not archivo.filename:
        return None

    nombre_original = secure_filename(archivo.filename)
    if not nombre_original or not _extension_permitida(nombre_original):
        raise PortadaInvalida(MENSAJE_FORMATO_INVALIDO)

    archivo.stream.seek(0, os.SEEK_END)
    tamano = archivo.stream.tell()
    archivo.stream.seek(0)
    if tamano > TAMANO_MAXIMO_BYTES:
        raise PortadaInvalida(MENSAJE_TAMANO_INVALIDO)

    cabecera = archivo.stream.read(16)
    archivo.stream.seek(0)
    if not _firma_valida(cabecera):
        raise PortadaInvalida(MENSAJE_FORMATO_INVALIDO)

    extension = _extension(nombre_original)
    nombre_final = f'{uuid.uuid4().hex}.{extension}'

    os.makedirs(carpeta_absoluta, exist_ok=True)
    archivo.save(os.path.join(carpeta_absoluta, nombre_final))

    return f'{CARPETA_RELATIVA}/{nombre_final}'


def eliminar_portada(carpeta_absoluta, ruta_relativa):
    """Borra un archivo de portada existente. No falla si ya no está."""
    if not ruta_relativa:
        return
    ruta_absoluta = os.path.join(carpeta_absoluta, os.path.basename(ruta_relativa))
    try:
        if os.path.isfile(ruta_absoluta):
            os.remove(ruta_absoluta)
    except OSError:
        pass


def url_portada(portada_archivo):
    """URL para <img src>: la portada real, o el placeholder si no hay ninguna."""
    if portada_archivo:
        return url_for('static', filename=portada_archivo)
    return url_for('static', filename=PLACEHOLDER_RELATIVO)
