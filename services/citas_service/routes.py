import random
import requests as http_requests
from datetime import datetime, timedelta
from flask import request, jsonify
from services.citas_service import citas_bp
from shared.audit import log_accion
from shared.proc import call_proc, call_proc_one, call_proc_execute
from shared.config import (
    OTP_EXPIRA_MIN, OTP_MAX_INTENTOS,
    TEXTBEE_API_KEY, TEXTBEE_DEVICE_ID, TEXTBEE_URL,
)


def _enviar_sms(telefono, mensaje):
    try:
        tel = telefono.strip().replace(" ", "").replace("-", "")
        if not tel.startswith("+"):
            tel = "+51" + tel
        url = TEXTBEE_URL.format(device_id=TEXTBEE_DEVICE_ID)
        resp = http_requests.post(
            url,
            json={"recipients": [tel], "message": mensaje},
            headers={"x-api-key": TEXTBEE_API_KEY},
            timeout=10,
        )
        return resp.status_code in (200, 201)
    except Exception:
        return False


def medico_disponible(medico_id, fecha_cita, excluir_cita_id=None):
    result = call_proc_one("sp_medico_disponible", (
        medico_id, fecha_cita, excluir_cita_id if excluir_cita_id else None,
    ))
    count = int(result["n"]) if result else 0
    return count == 0


@citas_bp.route("/api/citas/disponibilidad", methods=["POST"])
def verificar_disponibilidad():
    data = request.get_json() or {}
    medico_id = data.get("medico_id", "")
    fecha_cita = data.get("fecha_cita", "")
    excluir = data.get("excluir_cita_id")
    if not medico_id or not fecha_cita:
        return jsonify({"error": "Se requieren medico_id y fecha_cita"}), 400
    return jsonify({"disponible": medico_disponible(medico_id, fecha_cita, excluir)})


@citas_bp.route("/api/citas/terapeutas", methods=["GET"])
def listar_terapeutas():
    terapeutas = call_proc("sp_listar_terapeutas")
    return jsonify({"success": True, "terapeutas": terapeutas})


@citas_bp.route("/api/citas", methods=["GET"])
def listar_citas():
    dni = request.args.get("dni", "") or None
    fecha = request.args.get("fecha", "") or None
    estado = request.args.get("estado", "programada")
    medico_id = request.args.get("medico_id", "") or None

    citas = call_proc("sp_listar_citas", (estado, dni, fecha, medico_id))

    for c in citas:
        if hasattr(c.get("fecha_cita"), "strftime"):
            c["fecha_cita"] = c["fecha_cita"].strftime("%Y-%m-%d")
    return jsonify({"success": True, "total": len(citas), "citas": citas})


@citas_bp.route("/api/citas/<int:cita_id>", methods=["GET"])
def detalle_cita(cita_id):
    cita = call_proc_one("sp_detalle_cita", (cita_id,))
    if not cita:
        return jsonify({"error": "Cita no encontrada"}), 404
    if hasattr(cita.get("fecha_cita"), "strftime"):
        cita["fecha_cita"] = cita["fecha_cita"].strftime("%Y-%m-%d")
    return jsonify({"success": True, "cita": cita})


@citas_bp.route("/api/citas", methods=["POST"])
def crear_cita():
    data = request.get_json() or {}
    for campo in ["nombre", "apellido", "dni", "telefono", "medico_id", "fecha_cita"]:
        if not data.get(campo):
            return jsonify({"error": f"Campo requerido: {campo}"}), 400

    try:
        fecha_obj = datetime.strptime(data["fecha_cita"], "%Y-%m-%d").date()
        if fecha_obj < datetime.today().date():
            return jsonify({"error": "La fecha no puede ser en el pasado"}), 400
    except ValueError:
        return jsonify({"error": "Formato de fecha invalido (YYYY-MM-DD)"}), 400

    if not medico_disponible(data["medico_id"], data["fecha_cita"]):
        return jsonify({"error": "El medico ya tiene una cita ese dia"}), 409

    medico = call_proc_one("sp_consulta_medico_precio", (data["medico_id"],))
    if not medico:
        return jsonify({"error": "Medico no encontrado"}), 404

    costo = float(medico["precio"]) if medico.get("precio") else 0.0
    anticipo = round(costo / 2, 2)

    persona = call_proc_one("sp_obtener_paciente_id_dni", (data["dni"],))
    if persona:
        paciente_id = persona["id"]
    else:
        creado = call_proc_one("sp_crear_paciente_min", (
            data["nombre"], data["apellido"], data["dni"], data["telefono"],
        ))
        paciente_id = creado["id"] if creado else None

    servicio_id = data.get("servicio_id")

    cita = call_proc_one("sp_crear_cita", (paciente_id, data["medico_id"], servicio_id, data["fecha_cita"]))
    cita_id = cita["id"] if cita else None

    log_accion(
        accion="crear_cita",
        tabla_afectada="historial_citas",
        registro_id=cita_id,
        detalle=f"Cita creada para paciente_id={paciente_id}, medico_id={data['medico_id']}, fecha={data['fecha_cita']}",
        ip_origen=request.remote_addr,
    )

    metodo_pago = data.get("metodo_pago", "").strip()
    if metodo_pago and anticipo > 0 and cita_id:
        call_proc_execute("sp_crear_pago_anticipo", (
            cita_id, paciente_id, anticipo, metodo_pago,
        ))

    return jsonify({
        "success": True, "cita_id": cita_id,
        "costo": costo, "anticipo": anticipo,
    }), 201


@citas_bp.route("/api/citas/<int:cita_id>", methods=["PUT"])
def modificar_cita(cita_id):
    data = request.get_json() or {}
    nueva_fecha = data.get("fecha_cita", "")
    nuevo_medico = data.get("medico_id", "")
    if not nueva_fecha or not nuevo_medico:
        return jsonify({"error": "Se requieren fecha_cita y medico_id"}), 400
    try:
        fecha_obj = datetime.strptime(nueva_fecha, "%Y-%m-%d").date()
        if fecha_obj < datetime.today().date():
            return jsonify({"error": "La fecha no puede ser en el pasado"}), 400
    except ValueError:
        return jsonify({"error": "Formato invalido"}), 400
    if not medico_disponible(nuevo_medico, nueva_fecha, excluir_cita_id=cita_id):
        return jsonify({"error": "El medico ya tiene una cita ese dia"}), 409

    result = call_proc_one("sp_modificar_cita", (cita_id, nueva_fecha, nuevo_medico))
    if not result or int(result.get("actualizadas") or 0) == 0:
        return jsonify({"error": "Cita no encontrada o ya no esta programada"}), 404
    log_accion(
        accion="reprogramar_cita",
        tabla_afectada="historial_citas",
        registro_id=cita_id,
        detalle=f"Cita reprogramada a fecha={nueva_fecha}, medico_id={nuevo_medico}",
        ip_origen=request.remote_addr,
    )
    return jsonify({"success": True})


@citas_bp.route("/api/citas/<int:cita_id>", methods=["DELETE"])
def cancelar_cita(cita_id):
    result = call_proc_one("sp_cancelar_cita", (cita_id,))
    if not result or int(result.get("actualizadas") or 0) == 0:
        return jsonify({"error": "Cita no encontrada"}), 404
    log_accion(
        accion="cancelar_cita",
        tabla_afectada="historial_citas",
        registro_id=cita_id,
        ip_origen=request.remote_addr,
    )
    return jsonify({"success": True})


@citas_bp.route("/api/citas/otp/solicitar", methods=["POST"])
def solicitar_otp():
    data = request.get_json() or {}
    dni = data.get("dni", "").strip()
    accion = data.get("accion", "modificar")

    if not dni or len(dni) != 8 or not dni.isdigit():
        return jsonify({"error": "DNI invalido"}), 400

    persona = call_proc_one("sp_obtener_telefono_otp", (dni,))
    if not persona:
        return jsonify({"error": "No se encontraron citas programadas para ese DNI."}), 404

    codigo = str(random.randint(100000, 999999))
    expira = datetime.now() + timedelta(minutes=OTP_EXPIRA_MIN)

    call_proc_execute("sp_invalidar_otps_previos", (dni, accion))
    call_proc_execute("sp_insertar_otp", (dni, codigo, accion, expira))

    verbo = "modificar" if accion == "modificar" else "cancelar"
    mensaje = f"MOOVA Clinic: Tu codigo para {verbo} tu cita es {codigo}. Valido por {OTP_EXPIRA_MIN} min."
    enviado = _enviar_sms(persona["telefono"], mensaje)

    if not enviado:
        return jsonify({"error": "No se pudo enviar el SMS."}), 500

    tel = persona["telefono"].strip()
    tel_mask = tel[:3] + "***" + tel[-3:] if len(tel) >= 6 else "***"
    return jsonify({"success": True, "tel_mask": tel_mask})


@citas_bp.route("/api/citas/otp/verificar", methods=["POST"])
def verificar_otp():
    data = request.get_json() or {}
    dni = data.get("dni", "").strip()
    codigo = data.get("otp", "").strip()
    accion = data.get("accion", "modificar")

    otp = call_proc_one("sp_obtener_otp", (dni, accion))
    if not otp:
        return jsonify({"resultado": "no_existe"})
    if otp["intentos"] >= OTP_MAX_INTENTOS:
        return jsonify({"resultado": "agotado"})
    if datetime.now() > otp["expira_en"]:
        return jsonify({"resultado": "expirado"})
    if otp["codigo"] != codigo:
        call_proc_execute("sp_incrementar_intentos_otp", (otp["id"],))
        restantes = OTP_MAX_INTENTOS - otp["intentos"] - 1
        return jsonify({"resultado": "incorrecto", "restantes": restantes})

    call_proc_execute("sp_marcar_otp_usado", (otp["id"],))
    return jsonify({"resultado": "ok"})


@citas_bp.route("/api/citas/estadisticas", methods=["GET"])
def estadisticas():
    anio_inicio = 2023
    recuperados = especialistas = tasa_exito = total_anios = 0
    try:
        try:
            res = call_proc_one("sp_estadisticas_recuperados")
            recuperados = int(res["total"]) if res else 0
        except Exception:
            pass
        try:
            res = call_proc_one("sp_estadisticas_especialistas")
            especialistas = int(res["total"]) if res else 0
        except Exception:
            pass
        try:
            cfg = call_proc_one("sp_obtener_configuracion_anio")
            if cfg:
                anio_inicio = int(cfg["valor"])
        except Exception:
            pass
        total_anios = datetime.now().year - anio_inicio
        try:
            opin = call_proc_one("sp_estadisticas_opiniones")
            total = int(opin["total"]) if opin else 0
            buenas = int(opin["buenas"]) if opin else 0
            if total > 0:
                tasa_exito = round((buenas / total) * 100)
        except Exception:
            pass
    except Exception:
        pass
    return jsonify({
        "pacientes_recuperados": recuperados,
        "especialistas": especialistas,
        "anios_experiencia": total_anios,
        "tasa_exito": tasa_exito,
    })
