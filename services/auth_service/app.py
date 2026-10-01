import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from flask import Flask
from flask_bcrypt import Bcrypt

from shared.config import SECRET_KEY

bcrypt = Bcrypt()


def create_app():
    app = Flask(__name__)
    app.secret_key = SECRET_KEY

    bcrypt.init_app(app)

    from services.auth_service.routes import auth_bp
    app.register_blueprint(auth_bp)

    from shared.service_auth import proteger_api_interna
    proteger_api_interna(app)

    return app
