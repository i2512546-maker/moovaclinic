from flask import Blueprint

pacientes_bp = Blueprint("pacientes", __name__)
from services.pacientes_service import routes as routes
from shared.db import configurar_dominio_blueprint

configurar_dominio_blueprint(pacientes_bp, "pacientes")
