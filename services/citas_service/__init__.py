from flask import Blueprint
citas_bp = Blueprint("citas", __name__)
from services.citas_service import routes
