import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from flask import Flask
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()


def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", os.urandom(32).hex())

    bcrypt.init_app(app)

    from services.auth_service.routes import auth_bp
    app.register_blueprint(auth_bp)

    return app
