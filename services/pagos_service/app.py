import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from flask import Flask

from shared.config import SECRET_KEY


def create_app():
    app = Flask(__name__)
    app.secret_key = SECRET_KEY

    from services.pagos_service.routes import pagos_bp
    app.register_blueprint(pagos_bp)

    from shared.service_auth import proteger_api_interna
    proteger_api_interna(app)

    return app
