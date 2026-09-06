from flask import Blueprint

estudiante_bp = Blueprint('estudiante', __name__, url_prefix='/estudiante')

from app.controllers.estudiante import catalogo  # noqa: E402,F401
from app.controllers.estudiante import prestamos  # noqa: E402,F401
from app.controllers.estudiante import perfil  # noqa: E402,F401
