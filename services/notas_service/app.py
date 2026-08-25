import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from flask import Flask


def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", os.urandom(32).hex())

    from services.notas_service.routes import notas_bp
    app.register_blueprint(notas_bp)

    return app
