from flask import Blueprint

notas_bp = Blueprint("notas", __name__)
from services.notas_service import routes as routes
from shared.db import configurar_dominio_blueprint

configurar_dominio_blueprint(notas_bp, "notas")
