import json
from datetime import datetime
from flask import request, jsonify
from services.pagos_service import pagos_bp
from services.pagos_service.providers import (
    NiubizClient, YapeClient, PlinClient,
    PaymentNotConfigured, PaymentProviderError, qr_url,
)
from shared.audit import log_accion
from shared.proc import call_proc, call_proc_one, call_proc_execute


def _obtener_pago_pendiente(cita_id):
    cita = call_proc_one("sp_obtener_pago_pendiente", (cita_id,))
    if not cita or cita["estado_pago"] != "pendiente":
        return None
    return cita


def _guardar_referencia(cita_id, cobro_id):
    call_proc_execute("sp_guardar_referencia", (cita_id, cobro_id))


def confirmar_pago_servicio(cita_id, referencia=None, datos_respuesta=None, verificado_por=None):
    cita = call_proc_one("sp_obtener_cita_para_confirmar", (cita_id,))

    datos_json = json.dumps(datos_respuesta) if datos_respuesta else None
    res = call_proc_one("sp_confirmar_pago", (
        cita_id, referencia, datos_json, verificado_por,
    ))
    pagado = bool(res and int(res.get("pagado") or 0) > 0)

    if pagado:
        try:
            log_accion(
                usuario_id=verificado_por,
                accion="marcar_pago",
                tabla_afectada="pagos",
                registro_id=cita_id,
                detalle=f"Pago marcado como 'pagado' para cita_id={cita_id}, verificado_por={verificado_por}",
                ip_origen=request.remote_addr,
            )
        except Exception:
            pass

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
    pago = call_proc_one("sp_obtener_pago", (cita_id,))
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
