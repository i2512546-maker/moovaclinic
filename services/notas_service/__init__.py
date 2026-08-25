from flask import Blueprint
notas_bp = Blueprint("notas", __name__)
from services.notas_service import routes
