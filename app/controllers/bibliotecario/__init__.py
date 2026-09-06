from flask import Blueprint

bibliotecario_bp = Blueprint('bibliotecario', __name__, url_prefix='/bibliotecario')

from app.controllers.bibliotecario import inicio  # noqa: E402,F401
from app.controllers.bibliotecario import libros  # noqa: E402,F401
from app.controllers.bibliotecario import estudiantes  # noqa: E402,F401
from app.controllers.bibliotecario import prestamos  # noqa: E402,F401
from app.controllers.bibliotecario import devoluciones  # noqa: E402,F401
