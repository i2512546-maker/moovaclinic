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
from shared.service_client import auth_client, citas_client, pacientes_client


def _obtener_cita_info(cita_id):
    """Datos de la cita (nombre/apellido/terapeuta/Especialidad/
    telefono/fecha) via citas_service. Antes venian de
    sp_obtener_cita_para_confirmar / sp_obtener_pago_pendiente
    (CROSS-DB a citas_db/pacientes_db/auth_db)."""
    try:
        data, status = citas_client.get(f"/api/citas/{cita_id}")
        if status == 200:
            return data.get("cita") or {}
    except Exception:
        pass
    return {}


def _obtener_pago_pendiente(cita_id):
    pago = call_proc_one("sp_obtener_pago", (cita_id,))
    if not pago or pago["estado_pago"] != "pendiente":
        return None
    cita = _obtener_cita_info(cita_id)
    combinado = dict(pago)
    for campo in ("nombre", "apellido", "dni", "telefono", "telefono_paciente",
                  "terapeuta", "Especialidad", "fecha_cita"):
        if cita.get(campo) is not None:
            combinado[campo] = cita[campo]
    return combinado


def _nombre_paciente(paciente_id):
    """Nombre completo de un paciente via pacientes_service (best effort)."""
    if not paciente_id:
        return None
    try:
        data, _ = pacientes_client.get("/api/pacientes")
        for p in (data.get("pacientes") or []):
            if p.get("id") == paciente_id:
                nombre = " ".join(x for x in (p.get("nombre"), p.get("apellido")) if x).strip()
                return nombre or None
    except Exception:
        pass
    return None


def _guardar_referencia(cita_id, cobro_id):
    call_proc_execute("sp_guardar_referencia", (cita_id, cobro_id))


def confirmar_pago_servicio(cita_id, referencia=None, datos_respuesta=None, verificado_por=None):
    cita = _obtener_cita_info(cita_id)

    datos_json = json.dumps(datos_respuesta) if datos_respuesta else None
    res = call_proc_one("sp_confirmar_pago", (
        cita_id, referencia, datos_json, verificado_por,
    ))
    pagado = bool(res and int(res.get("pagado") or 0) > 0)

    if pagado:
        try:
            paciente_id = cita.get("paciente_id") if cita else None
            entidad_nombre = " ".join(
                x for x in (cita.get("nombre"), cita.get("apellido")) if x
            ).strip() or None
            log_accion(
                usuario_id=verificado_por,
                accion="marcar_pago",
                tabla_afectada="pagos",
                registro_id=cita_id,
                detalle=f"Pago marcado como 'pagado' para cita_id={cita_id}, verificado_por={verificado_por}",
                ip_origen=request.remote_addr,
                entidad_tipo="paciente",
                entidad_id=paciente_id,
                entidad_nombre=entidad_nombre,
            )
        except Exception:
            pass

    if pagado and cita:
        import requests as http_requests
        from shared.config import TEXTBEE_API_KEY, TEXTBEE_DEVICE_ID, TEXTBEE_URL
        try:
            fecha_fmt = datetime.strptime(str(cita["fecha_cita"]), "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            fecha_fmt = str(cita.get("fecha_cita"))

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

        # FASE 2: el telefono del medico vive en auth_db (usuarios);
        # se resuelve por HTTP: terapeuta (pacientes) -> usuario_id ->
        # auth_service GET /api/auth/usuarios/<id>.
        telefono_paciente = cita.get("telefono_paciente") or cita.get("telefono")
        if telefono_paciente:
            _sms(telefono_paciente,
                 f"MOOVA Clinic: Hola {cita.get('nombre')}, tu cita fue confirmada. Medico: {cita.get('terapeuta')} ({cita.get('Especialidad')}). Fecha: {fecha_fmt}.")

        telefono_medico = None
        terapeuta_id = cita.get("terapeuta_id")
        if terapeuta_id:
            try:
                tdata, tstatus = pacientes_client.get(f"/api/terapeutas/{terapeuta_id}")
                usuario_id = ((tdata or {}).get("terapeuta") or {}).get("usuario_id") if tstatus == 200 else None
            except Exception:
                usuario_id = None
            if usuario_id:
                try:
                    udata, ustatus = auth_client.get(f"/api/auth/usuarios/{usuario_id}")
                    userinfo = ((udata or {}).get("usuario") or {}) if ustatus == 200 else {}
                    telefono_medico = userinfo.get("telefono")
                except Exception:
                    telefono_medico = None
        if telefono_medico:
            _sms(telefono_medico,
                 f"MOOVA Clinic: Dr(a). {cita.get('terapeuta')}, se agendo cita con {cita.get('nombre')} {cita.get('apellido')}. Fecha: {fecha_fmt}.")

    return pagado


# ============================================================
# Anticipo / cancelacion (llamados por citas_service)
# ============================================================

@pagos_bp.route("/api/pagos/anticipo", methods=["POST"])
def crear_anticipo():
    """Crea el pago de anticipo de una cita. Lo invoca citas_service
    tras sp_crear_cita (antes sp_crear_pago_anticipo, CROSS-DB)."""
    data = request.get_json() or {}
    cita_id = data.get("cita_id")
    paciente_id = data.get("paciente_id")
    monto = data.get("monto")
    metodo_pago = data.get("metodo_pago", "efectivo")

    if not cita_id or not paciente_id or monto is None or not metodo_pago:
        return jsonify({"error": "cita_id, paciente_id, monto y metodo_pago requeridos."}), 400

    result = call_proc_one("sp_crear_pago_anticipo", (cita_id, paciente_id, monto, metodo_pago))
    return jsonify({"success": True, "id": result["id"] if result else None}), 201


@pagos_bp.route("/api/pagos/<int:cita_id>/cancelar", methods=["POST"])
def cancelar_pago_cita(cita_id):
    """Cancela el pago pendiente de una cita. Lo invoca citas_service
    cuando cancela una cita (antes dentro de sp_cancelar_cita, CROSS-DB)."""
    call_proc_execute("sp_cancelar_pago_cita", (cita_id,))
    return jsonify({"success": True})


# ============================================================
# Consultas de pagos (usadas por pacientes_service para el detalle)
# ============================================================

@pagos_bp.route("/api/pagos/pacientes/<int:paciente_id>", methods=["GET"])
def listar_pagos_paciente(paciente_id):
    pagos = call_proc("sp_obtener_pagos_paciente", (paciente_id,))
    return jsonify({"success": True, "pagos": pagos})


@pagos_bp.route("/api/pagos/pacientes/<int:paciente_id>/paquetes", methods=["GET"])
def listar_paquetes_paciente(paciente_id):
    paquetes = call_proc("sp_listar_paquetes_paciente", (paciente_id,)) or []
    try:
        servicios_data, _ = pacientes_client.get("/api/servicios")
        servicios = {s["id"]: s for s in (servicios_data.get("servicios") or [])}
    except Exception:
        servicios = {}
    for ps in paquetes:
        s = servicios.get(ps.get("servicio_id")) or {}
        if s.get("nombre") is not None:
            ps["servicio_nombre"] = s["nombre"]
        if s.get("duracion_min") is not None:
            ps["duracion_min"] = s["duracion_min"]
    return jsonify({"success": True, "paquetes": paquetes})


@pagos_bp.route("/api/pagos/pacientes/<int:paciente_id>/paquetes", methods=["POST"])
def crear_paquete_paciente(paciente_id):
    data = request.get_json() or {}
    servicio_id = data.get("servicio_id")
    total_sesiones = data.get("total_sesiones")
    fecha_compra = data.get("fecha_compra")
    fecha_vencimiento = data.get("fecha_vencimiento")

    if not servicio_id or not total_sesiones or not fecha_compra:
        return jsonify({"error": "servicio_id, total_sesiones y fecha_compra son requeridos."}), 400

    result = call_proc_one("sp_crear_paquete", (
        paciente_id, servicio_id, total_sesiones, fecha_compra, fecha_vencimiento,
    ))
    return jsonify({"success": True, "paquete_id": result["id"] if result else None}), 201


@pagos_bp.route("/api/pagos/paquetes/<int:paquete_id>/usar", methods=["POST"])
def usar_sesion_paquete(paquete_id):
    """Vincula una cita a un paquete e incrementa sesiones_usadas.
    Lo invoca el gateway tras crear la cita en el flujo /tratamiento
    (continuar tratamiento), como paso ADICIONAL posterior a la
    creacion de la cita (sp_usar_sesion_paquete)."""
    data = request.get_json() or {}
    cita_id = data.get("cita_id")
    if not cita_id:
        return jsonify({"error": "cita_id requerido."}), 400

    result = call_proc_one("sp_usar_sesion_paquete", (paquete_id, cita_id))
    usadas = int((result or {}).get("usadas") or 0)
    if usadas == 0:
        return jsonify({"error": "El paquete no esta activo o no tiene sesiones disponibles."}), 409

    try:
        pago = call_proc_one("sp_obtener_pago", (cita_id,))
        paciente_id = (pago or {}).get("paciente_id")
        log_accion(
            accion="usar_sesion_paquete",
            tabla_afectada="paquetes_sesiones",
            registro_id=paquete_id,
            detalle=f"Sesion del paquete {paquete_id} usada por cita_id={cita_id}",
            ip_origen=request.remote_addr,
            entidad_tipo="paciente",
            entidad_id=paciente_id,
            entidad_nombre=_nombre_paciente(paciente_id),
        )
    except Exception:
        pass
    return jsonify({"success": True, "usadas": usadas})


@pagos_bp.route("/api/pagos/configuracion/anio", methods=["GET"])
def obtener_anio_inicio():
    cfg = call_proc_one("sp_obtener_configuracion_anio")
    return jsonify({"success": True, "valor": cfg["valor"] if cfg else None})


# ============================================================
# Pasarelas de pago
# ============================================================

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
        cobro = yape.crear_cobro(monto=cita["monto"], concepto=f"Cita MOOVA - {cita.get('terapeuta')}", referencia=str(cita_id))
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
        cobro = plin.crear_cobro(monto=cita["monto"], concepto=f"Cita MOOVA - {cita.get('terapeuta')}", referencia=str(cita_id))
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