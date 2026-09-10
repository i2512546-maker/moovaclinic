from flask import Blueprint

audit_bp = Blueprint("audit", __name__)

from services.audit_service import routes