from flask import Blueprint

pagos_bp = Blueprint("pagos", __name__)
from services.pagos_service import routes as routes
from shared.db import configurar_dominio_blueprint

configurar_dominio_blueprint(pagos_bp, "pagos")
