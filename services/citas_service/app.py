import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from flask import Flask
from shared.api import register_global_error_handlers
from shared.config import SECRET_KEY

from shared.config import SECRET_KEY


def create_app():
    app = Flask(__name__)
    app.secret_key = SECRET_KEY
<<<<<<< Updated upstream
=======
    register_global_error_handlers(app)
>>>>>>> Stashed changes

    from services.citas_service.routes import citas_bp
    app.register_blueprint(citas_bp)

    from shared.service_auth import proteger_api_interna
    proteger_api_interna(app)

    return app
