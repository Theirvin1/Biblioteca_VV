from flask import Blueprint

gerente_bp = Blueprint('gerente', __name__, url_prefix='/gerente')

from app.controllers.gerente import dashboard  # noqa: E402,F401
from app.controllers.gerente import reportes  # noqa: E402,F401
from app.controllers.gerente import usuarios  # noqa: E402,F401
