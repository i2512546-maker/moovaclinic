import json
from datetime import datetime
from flask import request, jsonify
from services.pagos_service import pagos_bp
from services.pagos_service.providers import (
    NiubizClient, YapeClient, PlinClient,
    PaymentNotConfigured, PaymentProviderError, qr_url,
)
from shared.db import db_connection


def _obtener_pago_pendiente(cita_id):
    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT h.id, p.nombre, p.apellido,
                      t.Nombre AS terapeuta, e.nombre AS Especialidad,
                      pg.monto, pg.metodo_pago, pg.estado_pago, pg.referencia
               FROM historial_citas h
               JOIN personas p ON h.persona_id = p.id
               JOIN terapeutas t ON h.terapeuta_id = t.ID
               LEFT JOIN especialidades e ON t.especialidad_id = e.id
               LEFT JOIN pagos pg ON pg.cita_id = h.id
               WHERE h.id = %s""", (cita_id,),
        )
        cita = cursor.fetchone()
        if not cita or cita["estado_pago"] != "pendiente":
            return None
    return cita


def _guardar_referencia(cita_id, cobro_id):
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE pagos SET referencia=%s WHERE cita_id=%s", (cobro_id, cita_id))
        conn.commit()


def confirmar_pago_servicio(cita_id, referencia=None, datos_respuesta=None):
    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT h.fecha_cita, p.nombre, p.apellido, p.telefono AS telefono_paciente,
                      t.Nombre AS terapeuta, e.nombre AS Especialidad, t.Telefono AS telefono_medico
               FROM historial_citas h
               JOIN personas p ON h.persona_id = p.id
               JOIN terapeutas t ON h.terapeuta_id = t.ID
               LEFT JOIN especialidades e ON t.especialidad_id = e.id
               WHERE h.id = %s""", (cita_id,),
        )
        cita = cursor.fetchone()

        datos_json = json.dumps(datos_respuesta) if datos_respuesta else None
        cursor.execute(
            """UPDATE pagos SET estado_pago='pagado', fecha_pago=NOW(),
               referencia=COALESCE(%s,referencia), transaccion_id=COALESCE(%s,transaccion_id),
               datos_respuesta=COALESCE(%s,datos_respuesta), verificado_en=NOW()
               WHERE cita_id=%s AND estado_pago='pendiente'""",
            (referencia, referencia, datos_json, cita_id),
        )
        conn.commit()
        pagado = cursor.rowcount > 0

        if pagado and cita:
            import requests as http_requests
            from shared.config import TEXTBEE_API_KEY, TEXTBEE_DEVICE_ID, TEXTBEE_URL
            try:
                fecha_fmt = datetime.strptime(str(cita["fecha_cita"]), "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                fecha_fmt = str(cita["fecha_cita"])

            def _sms(tel, msg):
                try:
                    t = tel.strip().replace(" ", "")
                    if not t.startswith("+"):
                        t = "+51" + t
                    http_requests.post(
                        TEXTBEE_URL.format(device_id=TEXTBEE_DEVICE_ID),
                        json={"recipients": [t], "message": msg},
                        headers={"x-api-key": TEXTBEE_API_KEY}, timeout=10,
                    )
                except Exception:
                    pass

            _sms(cita["telefono_paciente"],
                 f"MOOVA Clinic: Hola {cita['nombre']}, tu cita fue confirmada. Medico: {cita['terapeuta']} ({cita['Especialidad']}). Fecha: {fecha_fmt}.")
            if cita.get("telefono_medico"):
                _sms(cita["telefono_medico"],
                     f"MOOVA Clinic: Dr(a). {cita['terapeuta']}, se agendo cita con {cita['nombre']} {cita['apellido']}. Fecha: {fecha_fmt}.")

    return pagado


@pagos_bp.route("/api/pagos/<int:cita_id>", methods=["GET"])
def estado_pago(cita_id):
    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM pagos WHERE cita_id=%s", (cita_id,))
        pago = cursor.fetchone()
    if not pago:
        return jsonify({"error": "Pago no encontrado"}), 404
    return jsonify({"success": True, "pago": pago})


@pagos_bp.route("/api/pagos/yape/iniciar", methods=["POST"])
def api_pago_yape_iniciar():
    data = request.get_json(silent=True) or {}
    cita_id = data.get("cita_id")
    cita = _obtener_pago_pendiente(cita_id)
    if not cita:
        return jsonify({"ok": False, "error": "Cita no encontrada o ya pagada."}), 400
    try:
        yape = YapeClient()
        cobro = yape.crear_cobro(monto=cita["monto"], concepto=f"Cita MOOVA - {cita['terapeuta']}", referencia=str(cita_id))
    except (PaymentNotConfigured, PaymentProviderError) as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    _guardar_referencia(cita_id, cobro["cobro_id"])
    return jsonify({"ok": True, "qr": qr_url(cobro["qr_base64"]), "cobro_id": cobro["cobro_id"], "monto": cita["monto"]})


@pagos_bp.route("/api/pagos/yape/estado", methods=["POST"])
def api_pago_yape_estado():
    data = request.get_json(silent=True) or {}
    cita_id = data.get("cita_id")
    cobro_id = data.get("cobro_id")
    cita = _obtener_pago_pendiente(cita_id)
    if not cita:
        return jsonify({"ok": False, "error": "Cita no encontrada o ya pagada."}), 400
    try:
        res = YapeClient().consultar_pago(cobro_id or cita.get("referencia"))
    except (PaymentNotConfigured, PaymentProviderError) as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    if res["pagado"]:
        confirmar_pago_servicio(cita_id, referencia=cobro_id, datos_respuesta=res.get("datos_respuesta"))
        return jsonify({"ok": True, "pagado": True})
    return jsonify({"ok": True, "pagado": False})


@pagos_bp.route("/api/pagos/plin/iniciar", methods=["POST"])
def api_pago_plin_iniciar():
    data = request.get_json(silent=True) or {}
    cita_id = data.get("cita_id")
    cita = _obtener_pago_pendiente(cita_id)
    if not cita:
        return jsonify({"ok": False, "error": "Cita no encontrada o ya pagada."}), 400
    try:
        plin = PlinClient()
        cobro = plin.crear_cobro(monto=cita["monto"], concepto=f"Cita MOOVA - {cita['terapeuta']}", referencia=str(cita_id))
    except (PaymentNotConfigured, PaymentProviderError) as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    _guardar_referencia(cita_id, cobro["cobro_id"])
    return jsonify({"ok": True, "qr": qr_url(cobro["qr_base64"]), "cobro_id": cobro["cobro_id"], "monto": cita["monto"]})


@pagos_bp.route("/api/pagos/plin/estado", methods=["POST"])
def api_pago_plin_estado():
    data = request.get_json(silent=True) or {}
    cita_id = data.get("cita_id")
    cobro_id = data.get("cobro_id")
    cita = _obtener_pago_pendiente(cita_id)
    if not cita:
        return jsonify({"ok": False, "error": "Cita no encontrada o ya pagada."}), 400
    try:
        res = PlinClient().consultar_pago(cobro_id or cita.get("referencia"))
    except (PaymentNotConfigured, PaymentProviderError) as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    if res["pagado"]:
        confirmar_pago_servicio(cita_id, referencia=cobro_id, datos_respuesta=res.get("datos_respuesta"))
        return jsonify({"ok": True, "pagado": True})
    return jsonify({"ok": True, "pagado": False})


@pagos_bp.route("/api/pagos/tarjeta/iniciar", methods=["POST"])
def api_pago_tarjeta_iniciar():
    data = request.get_json(silent=True) or {}
    cita_id = data.get("cita_id")
    cita = _obtener_pago_pendiente(cita_id)
    if not cita:
        return jsonify({"ok": False, "error": "Cita no encontrada o ya pagada."}), 400
    try:
        sesion = NiubizClient().get_session_key()
    except (PaymentNotConfigured, PaymentProviderError) as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "sessionKey": sesion["sessionKey"], "merchantId": sesion["merchantId"],
                     "monto": cita["monto"], "purchaseNumber": str(cita_id)})


@pagos_bp.route("/api/pagos/tarjeta/cobrar", methods=["POST"])
def api_pago_tarjeta_cobrar():
    data = request.get_json(silent=True) or {}
    cita_id = data.get("cita_id")
    card_token = (data.get("cardToken") or "").strip()
    cvv = (data.get("cvv") or "").strip()
    purchase_number = data.get("purchaseNumber") or str(cita_id)
    cita = _obtener_pago_pendiente(cita_id)
    if not cita:
        return jsonify({"ok": False, "error": "Cita no encontrada o ya pagada."}), 400
    if not card_token or not cvv:
        return jsonify({"ok": False, "error": "Datos incompletos."}), 400
    try:
        res = NiubizClient().cobrar(card_token=card_token, cvv=cvv, purchase_number=purchase_number, monto=float(cita["monto"]))
    except (PaymentNotConfigured, PaymentProviderError) as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    confirmar_pago_servicio(cita_id, referencia=res["transaccion_id"], datos_respuesta=res.get("datos_respuesta"))
    return jsonify({"ok": True, "pagado": True, "transaccion_id": res["transaccion_id"]})


@pagos_bp.route("/api/pagos/webhook", methods=["POST"])
def webhook_pago():
    data = request.get_json(silent=True) or request.form or {}
    cita_id = data.get("cita_id") or data.get("orderId") or data.get("purchaseNumber")
    estado = str(data.get("estado") or data.get("status") or "").lower()
    referencia = data.get("referencia") or data.get("transactionId")
    if not cita_id:
        return jsonify({"ok": False, "error": "cita_id requerido"}), 400
    if estado in ("pagado", "paid", "confirmed", "aprobado", "success", "000"):
        confirmar_pago_servicio(cita_id, referencia=referencia, datos_respuesta=data)
    return jsonify({"ok": True})
