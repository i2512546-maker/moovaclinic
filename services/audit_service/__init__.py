from flask import Blueprint

audit_bp = Blueprint("audit", __name__)

from services.audit_service import routes as routes
from shared.db import configurar_dominio_blueprint

configurar_dominio_blueprint(audit_bp, "audit")
