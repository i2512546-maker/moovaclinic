import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from flask import Flask

from shared.config import SECRET_KEY


def create_app():
    app = Flask(__name__)
    app.secret_key = SECRET_KEY

    from services.citas_service.routes import citas_bp
    app.register_blueprint(citas_bp)

    from shared.service_auth import proteger_api_interna
    proteger_api_interna(app)

    # Recordatorios automaticos por SMS: solo si RECORDATORIOS_ENABLED=1.
    # Es infraestructura secundaria: si APScheduler no esta instalado o
    # no puede arrancar, las citas deben seguir funcionando igual.
    try:
        from services.citas_service.scheduler import iniciar_scheduler
        iniciar_scheduler(app)
    except Exception as exc:
        app.logger.error(
            "[recordatorios] no se pudo arrancar el scheduler: %s: %s",
            type(exc).__name__, exc,
        )

    return app
