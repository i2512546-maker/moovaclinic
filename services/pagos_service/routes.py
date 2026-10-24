import hmac
import json
import os
from datetime import datetime

from flask import current_app, jsonify, request

from services.pagos_service import pagos_bp
from services.pagos_service.providers import (
    NiubizClient,
    PaymentNotConfigured,
    PaymentProviderError,
    PlinClient,
    YapeClient,
    qr_url,
)
from shared.audit import log_accion
from shared.config import WEBHOOK_PROVIDER_TOKEN
from shared.proc import call_proc, call_proc_execute, call_proc_one
from shared.service_client import auth_client, citas_client, pacientes_client


def _obtener_cita_info(cita_id):
    """Datos de la cita (nombre/apellido/terapeuta/Especialidad/
    telefono/fecha) via citas_service. Antes venian de
    sp_obtener_cita_para_confirmar / sp_obtener_pago_pendiente
    (CROSS-DB a moovacloud_citas/moovacloud_pacientes/moovacloud_auth)."""
    try:
        data, status = citas_client.get(f"/api/citas/{cita_id}")
        if status == 200:
            return data.get("cita") or {}
    except Exception as exc:
        # Best effort: quien llama recibe {} y decide. Se loguea para
        # poder ver cuando citas_service no responde.
        current_app.logger.warning(
            "No se pudo leer la cita %s desde citas_service: %s: %s",
            cita_id, type(exc).__name__, exc,
        )
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
    except Exception as exc:
        # Solo se pierde el nombre en la auditoria/respuesta, no el dato.
        current_app.logger.warning(
            "No se pudo resolver el nombre del paciente %s: %s: %s",
            paciente_id, type(exc).__name__, exc,
        )
    return None


def _guardar_referencia(cita_id, cobro_id):
    call_proc_execute("sp_guardar_referencia", (cita_id, cobro_id))


# Campos en los que la pasarela suele devolver lo que nosotros le
# mandamos al crear el cobro. Se miran varios nombres porque Yape y
# Plin no estan fijados a un esquema en este repo.
_CAMPOS_REFERENCIA = ("referencia", "reference", "referenciaExterna", "externalReference")
_CAMPOS_MONTO = ("monto", "amount", "importe", "total", "totalAmount")


def _cobro_valido_para_cita(respuesta, cita_id, monto_pendiente):
    """True solo si el cobro consultado ES el de esta cita y por EL
    monto pendiente.

    Al crear el cobro enviamos referencia=str(cita_id) y monto=precio
    (providers.crear_cobro), asi que se pueden comparar con lo que el
    proveedor devuelve. Si alguno de los dos no viene, NO se da el pago
    por bueno: sin poder comparar, mas vale no marcarlo pagado.
    """
    datos = (respuesta or {}).get("datos_respuesta") or {}
    if not isinstance(datos, dict):
        return False

    referencia = next(
        (datos[c] for c in _CAMPOS_REFERENCIA if datos.get(c) not in (None, "")), None
    )
    if referencia is None or str(referencia).strip() != str(cita_id):
        return False

    monto_respuesta = next(
        (datos[c] for c in _CAMPOS_MONTO if datos.get(c) not in (None, "")), None
    )
    if monto_respuesta is None:
        return False
    try:
        return abs(float(monto_respuesta) - float(monto_pendiente)) < 0.01
    except (TypeError, ValueError):
        return False


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
        except Exception as exc:
            # El pago ya quedo confirmado en la base; lo que se pierde
            # es la linea de auditoria, y conviene verlo igual.
            current_app.logger.warning(
                "Pago de la cita %s confirmado pero sin registrar en auditoria: %s: %s",
                cita_id, type(exc).__name__, exc,
            )

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
            except Exception as exc:
                # False/None no se propaga: el aviso SMS es secundario
                # respecto al pago, que ya quedo confirmado.
                current_app.logger.warning(
                    "No se pudo enviar el SMS de aviso de pago a %s: %s: %s",
                    tel, type(exc).__name__, exc,
                )

        # FASE 2: el telefono del medico vive en moovacloud_auth (usuarios);
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


@pagos_bp.route("/api/pagos/mantenimiento/liberar_vencidos", methods=["POST"])
def liberar_pagos_vencidos():
    """Expira los pagos pendientes que llevan demasiado tiempo sin
    confirmar, para que la cita pueda volver a reservarse.

    Lo invoca scripts/liberar_pagos_vencidos.py desde cron. Es interno:
    va protegido por la API_KEY (proteger_api_interna), no por sesion de
    usuario, porque corre sin navegador.

    p_horas define a partir de cuantas horas se considera vencido. Si
    no se envia, usa 24.
    """
    data = request.get_json(silent=True) or {}
    try:
        horas = int(data.get("horas", 24))
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "horas debe ser un entero."}), 400

    if horas <= 0 or horas > 24 * 30:
        return jsonify({"success": False, "error": "horas fuera de rango (1..720)."}), 400

    res = call_proc_one("sp_liberar_pagos_vencidos", (horas,))
    vencidos = int(res.get("vencidos") or 0) if res else 0

    current_app.logger.info(
        "[mantenimiento] pagos vencidos (%sh): %s", horas, vencidos,
    )
    if vencidos:
        try:
            log_accion(
                usuario_id=None,
                accion="liberar_pagos_vencidos",
                tabla_afectada="pagos",
                registro_id=None,
                detalle=f"{vencidos} pago(s) pendiente(s) expirados tras {horas}h",
            )
        except Exception:
            current_app.logger.warning(
                "[mantenimiento] no se pudo auditar la liberacion de pagos",
                exc_info=True,
            )

    return jsonify({"success": True, "vencidos": vencidos, "horas": horas})


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
    except Exception as exc:
        # La sesion ya quedo descontada del paquete; lo que se pierde
        # es la linea de auditoria.
        current_app.logger.warning(
            "Sesion del paquete %s usada (cita %s) pero sin registrar en auditoria: %s: %s",
            paquete_id, cita_id, type(exc).__name__, exc,
        )
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
    # El cobro NO se toma del pedido: el cliente puede mandar cualquier
    # id. Se consulta siempre el que esta guardado en la base para
    # ESTA cita. data.get("cobro_id") se ignora a proposito.
    cita = _obtener_pago_pendiente(cita_id)
    if not cita:
        return jsonify({"ok": False, "error": "Cita no encontrada o ya pagada."}), 400
    referencia = cita.get("referencia")
    if not referencia:
        return jsonify({"ok": False, "error": "Esta cita no tiene un cobro iniciado."}), 400
    try:
        res = YapeClient().consultar_pago(referencia)
    except (PaymentNotConfigured, PaymentProviderError) as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    if not res.get("pagado"):
        return jsonify({"ok": True, "pagado": False})
    if not _cobro_valido_para_cita(res, cita_id, cita.get("monto")):
        current_app.logger.warning(
            "Yape devolvio un cobro pagado que no coincide con la cita %s "
            "(referencia guardada %r); no se marca el pago", cita_id, referencia
        )
        return jsonify({"ok": False, "error": "No se pudo verificar el pago."}), 400
    confirmar_pago_servicio(cita_id, referencia=referencia,
                            datos_respuesta=res.get("datos_respuesta"))
    return jsonify({"ok": True, "pagado": True})


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
    # Igual que en Yape: el cobro se toma de la base, nunca del pedido
    # (data.get("cobro_id") se ignora a proposito).
    cita = _obtener_pago_pendiente(cita_id)
    if not cita:
        return jsonify({"ok": False, "error": "Cita no encontrada o ya pagada."}), 400
    referencia = cita.get("referencia")
    if not referencia:
        return jsonify({"ok": False, "error": "Esta cita no tiene un cobro iniciado."}), 400
    try:
        res = PlinClient().consultar_pago(referencia)
    except (PaymentNotConfigured, PaymentProviderError) as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    if not res.get("pagado"):
        return jsonify({"ok": True, "pagado": False})
    if not _cobro_valido_para_cita(res, cita_id, cita.get("monto")):
        current_app.logger.warning(
            "Plin devolvio un cobro pagado que no coincide con la cita %s "
            "(referencia guardada %r); no se marca el pago", cita_id, referencia
        )
        return jsonify({"ok": False, "error": "No se pudo verificar el pago."}), 400
    confirmar_pago_servicio(cita_id, referencia=referencia,
                            datos_respuesta=res.get("datos_respuesta"))
    return jsonify({"ok": True, "pagado": True})


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
    # Verificar token secreto del proveedor (preventivo contra webhooks falsos)
    token_proveedor = request.headers.get("X-Provider-Token") or request.headers.get("X-Signature") or ""
    token_esperado = WEBHOOK_PROVIDER_TOKEN
    if not token_esperado:
        permitir_inseguro = (os.getenv("ALLOW_INSECURE_WEBHOOK") or "").strip() == "1"
        if not permitir_inseguro:
            current_app.logger.error(
                "Webhook rechazado: falta configurar WEBHOOK_PROVIDER_TOKEN"
            )
            return jsonify({"ok": False, "error": "Webhook no configurado"}), 503
        current_app.logger.warning(
            "Webhook sin token habilitado explícitamente para desarrollo local"
        )
    elif not hmac.compare_digest(token_proveedor, token_esperado):
        current_app.logger.warning("Webhook token inválido desde %s", request.remote_addr)
        return jsonify({"ok": False, "error": "Token no autorizado"}), 401

    data = request.get_json(silent=True) or request.form or {}
    cita_id = data.get("cita_id") or data.get("orderId") or data.get("purchaseNumber")
    estado = str(data.get("estado") or data.get("status") or "").lower()
    referencia = data.get("referencia") or data.get("transactionId")
    if not cita_id:
        return jsonify({"ok": False, "error": "cita_id requerido"}), 400
    if estado in ("pagado", "paid", "confirmed", "aprobado", "success", "000"):
        confirmar_pago_servicio(cita_id, referencia=referencia, datos_respuesta=data)
    return jsonify({"ok": True})
