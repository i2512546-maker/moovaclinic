from flask import Blueprint
pacientes_bp = Blueprint("pacientes", __name__)
from services.pacientes_service import routes
