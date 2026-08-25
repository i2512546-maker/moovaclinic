from flask import Blueprint
pagos_bp = Blueprint("pagos", __name__)
from services.pagos_service import routes
