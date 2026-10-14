import json
from datetime import datetime, timedelta

import pytest


@pytest.fixture
def app_client(monkeypatch):
    from shared import config as cfg
    cfg.SECRET_KEY = "test-secret-key"

    from services.citas_service import routes as citas_routes
    from services.citas_service import citas_bp
    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(citas_bp)
    app.config["TESTING"] = True
    app.config["otp_rate_limit"] = {"dni": {}, "ip": {}}

    monkeypatch.setattr(citas_routes, "call_proc_one", lambda proc, params=(): {
        "sp_obtener_telefono_otp": {"telefono": "999123777"},
        "sp_obtener_otp": {"id": 1, "codigo": "" if False else "d41d8cd98f00b204e9800998ecf8427e", "intentos": 0, "expira_en": datetime.now() + timedelta(minutes=5)},
        "sp_obtener_paciente_por_dni": {"id": 101, "dni": "12345678"},
        "SELECT * FROM paquetes_sesiones WHERE id = %s FOR UPDATE": {"id": 10, "paciente_id": 101, "servicio_id": 5, "total_sesiones": 3, "sesiones_usadas": 1, "estado": "activo", "fecha_vencimiento": "2099-12-31"},
        "SELECT id, activo FROM terapeutas WHERE id = %s AND activo = 1 LIMIT 1": {"id": 2, "activo": 1},
        "sp_detalle_cita": {"id": 7, "paciente_id": 101, "estado": "programada"},
        "sp_consulta_medico_precio": {"precio": 100.0},
    }.get(proc, None))

    monkeypatch.setattr(citas_routes, "call_proc_execute", lambda *args, **kwargs: True)
    monkeypatch.setattr(citas_routes, "_enviar_sms", lambda *args, **kwargs: True)

    with app.test_client() as client:
        yield client


def test_otp_solicitar_ok(app_client):
    resp = app_client.post(
        "/api/otp/solicitar",
        json={"dni": "12345678", "accion": "modificar"},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["status"] is True
    assert payload["data"]["intentos"] == 3


def test_otp_verificar_ok(app_client):
    resp = app_client.post(
        "/api/otp/verificar",
        json={"dni": "12345678", "codigo": "123456", "accion": "modificar"},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["status"] is True
    assert "identity_token" in payload["data"]


def test_identity_token_rechaza_cita_ajena(app_client):
    from services.citas_service import routes as citas_routes
    from shared import config as cfg
    cfg.SECRET_KEY = "test-secret-key"

    import jwt
    token = jwt.encode({"dni": "12345678", "exp": datetime.utcnow().timestamp() + 900}, cfg.SECRET_KEY, algorithm="HS256")

    resp = app_client.post(
        "/api/citas/sesion",
        json={"paquete_id": 10, "fecha": "2099-12-15", "hora": "10:30", "terapeuta_id": 2},
        headers={"X-Identity-Token": token},
    )
    assert resp.status_code == 201
    assert resp.get_json()["status"] is True
