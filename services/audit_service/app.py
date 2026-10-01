import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from flask import Flask

from shared.config import SECRET_KEY


def create_app():
    app = Flask(__name__)
    app.secret_key = SECRET_KEY

    from services.audit_service.routes import audit_bp
    app.register_blueprint(audit_bp)

    from shared.service_auth import proteger_api_interna
    proteger_api_interna(app)

    return app
