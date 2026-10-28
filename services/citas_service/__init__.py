from flask import Blueprint

citas_bp = Blueprint("citas", __name__)
from services.citas_service import routes as routes
from shared.db import configurar_dominio_blueprint

configurar_dominio_blueprint(citas_bp, "citas")
