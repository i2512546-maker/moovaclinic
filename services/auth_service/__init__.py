from flask import Blueprint

auth_bp = Blueprint("auth", __name__)

from services.auth_service import routes
