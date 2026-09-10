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
from shared.service_client import pacientes_client, pagos_client


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


def _mapa_pacientes():
    """{paciente_id: fila} via pacientes_service. Se usa para enriquecer
    las citas (nombre/apellido/dni/telefono) sin tocar pacientes_db."""
    try:
        data, _ = pacientes_client.get("/api/pacientes")
        pacientes = data.get("pacientes") or []
        return {p["id"]: p for p in pacientes}
    except Exception:
        return {}


def _mapa_terapeutas():
    """{terapeuta_id: {Nombre, Especialidad}} via pacientes_service."""
    try:
        data, _ = pacientes_client.get("/api/terapeutas")
        terapeutas = data.get("terapeutas") or []
        return {t["ID"]: t for t in terapeutas}
    except Exception:
        return {}


def _fmt_fecha(fila):
    if hasattr(fila.get("fecha_cita"), "strftime"):
        fila["fecha_cita"] = fila["fecha_cita"].strftime("%Y-%m-%d")
    return fila


def _enriquecer_cita(cita, pacientes=None, terapeutas=None):
    pacientes = pacientes if pacientes is not None else _mapa_pacientes()
    terapeutas = terapeutas if terapeutas is not None else _mapa_terapeutas()
    p = pacientes.get(cita.get("paciente_id")) or {}
    for campo, valor in (("nombre", p.get("nombre")), ("apellido", p.get("apellido")),
                         ("dni", p.get("dni")), ("telefono", p.get("telefono"))):
        if valor is not None:
            cita[campo] = valor
    te = terapeutas.get(cita.get("terapeuta_id")) or {}
    if te.get("Nombre") is not None:
        cita["terapeuta"] = te["Nombre"]
    if te.get("Especialidad") is not None:
        cita["Especialidad"] = te["Especialidad"]
    return cita


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
    """Ruta publica conservada. Los terapeutas viven en pacientes_db;
    se obtienen por HTTP a pacientes_service."""
    data, status = pacientes_client.get("/api/terapeutas")
    return jsonify(data), status


@citas_bp.route("/api/citas", methods=["GET"])
def listar_citas():
    dni = request.args.get("dni", "") or None
    fecha = request.args.get("fecha", "") or None
    estado = request.args.get("estado", "programada")
    medico_id = request.args.get("medico_id", "") or None

    # FASE 2: sp_listar_citas es local; el filtro por dni se aplica en
    # Python tras enriquecer con los datos del paciente.
    citas = call_proc("sp_listar_citas", (estado, None, fecha, medico_id))

    resumen = {}
    for r in (call_proc("sp_resumen_pacientes") or []):
        resumen[r["paciente_id"]] = r["total"]

    pacientes = _mapa_pacientes()
    terapeutas = _mapa_terapeutas()

    resultado = []
    for c in citas:
        _enriquecer_cita(c, pacientes, terapeutas)
        c["total_visitas"] = resumen.get(c.get("paciente_id"), 0)
        _fmt_fecha(c)
        if dni and c.get("dni") != dni:
            continue
        resultado.append(c)

    return jsonify({"success": True, "total": len(resultado), "citas": resultado})


@citas_bp.route("/api/citas/paciente/<int:paciente_id>", methods=["GET"])
def listar_citas_paciente(paciente_id):
    """Historial de un paciente (para detalle servido por
    pacientes_service, que enriquece terapeuta/especialidad/pago)."""
    citas = call_proc("sp_listar_citas_paciente", (paciente_id,))
    terapeutas = _mapa_terapeutas()
    for c in citas:
        te = terapeutas.get(c.get("terapeuta_id")) or {}
        if te.get("Nombre") is not None:
            c["terapeuta"] = te["Nombre"]
        if te.get("Especialidad") is not None:
            c["Especialidad"] = te["Especialidad"]
        _fmt_fecha(c)
    return jsonify({"success": True, "citas": citas})


@citas_bp.route("/api/citas/resumen_pacientes", methods=["GET"])
def resumen_pacientes():
    """Conteo de citas por paciente. Lo usa pacientes_service para
    enriquecer sp_listar_pacientes (antes era un subquery CROSS-DB)."""
    resumen = call_proc("sp_resumen_pacientes")
    return jsonify({"success": True, "resumen": resumen})


@citas_bp.route("/api/citas/<int:cita_id>", methods=["GET"])
def detalle_cita(cita_id):
    cita = call_proc_one("sp_detalle_cita", (cita_id,))
    if not cita:
        return jsonify({"error": "Cita no encontrada"}), 404
    _enriquecer_cita(cita)
    _fmt_fecha(cita)
    return jsonify({"success": True, "cita": cita})


@citas_bp.route("/api/citas/<int:cita_id>/basico", methods=["GET"])
def detalle_cita_basico(cita_id):
    """Version liviana de detalle_cita: devuelve SOLO los datos locales de
    citas_db (paciente_id, terapeuta_id, fecha_cita, estado, ...) sin
    enriquecer por HTTP a otros servicios. Lo usa notas_service para
    resolver el paciente_id de una cita sin pagar la cadena pesada del
    detalle enriquecido."""
    cita = call_proc_one("sp_detalle_cita", (cita_id,))
    if not cita:
        return jsonify({"error": "Cita no encontrada"}), 404
    _fmt_fecha(cita)
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

    # FASE 2: precio del medico via pacientes_service (antes
    # sp_consulta_medico_precio, CROSS-DB).
    medico_data, medico_status = pacientes_client.get(f"/api/terapeutas/{data['medico_id']}")
    if medico_status != 200:
        return jsonify({"error": "Medico no encontrado"}), 404
    medico = medico_data.get("terapeuta") or {}

    costo = float(medico["precio"]) if medico.get("precio") else 0.0
    anticipo = round(costo / 2, 2)

    # FASE 2: resolver/crear paciente via pacientes_service.
    pac_data, pac_status = pacientes_client.get(f"/api/pacientes/dni/{data['dni']}")
    if pac_status == 200:
        paciente_id = pac_data.get("id")
    else:
        creado, creado_status = pacientes_client.post("/api/pacientes/min", {
            "nombre": data["nombre"], "apellido": data["apellido"],
            "dni": data["dni"], "telefono": data["telefono"],
        })
        if creado_status not in (200, 201):
            return jsonify({"error": "No se pudo registrar al paciente."}), 400
        paciente_id = (creado or {}).get("id")

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
        # FASE 2: pago anticipado via pagos_service (antes
        # sp_crear_pago_anticipo, CROSS-DB).
        try:
            pagos_client.post("/api/pagos/anticipo", {
                "cita_id": cita_id,
                "paciente_id": paciente_id,
                "monto": anticipo,
                "metodo_pago": metodo_pago,
            })
        except Exception:
            pass

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

    # FASE 2: cancelar el pago pendiente via pagos_service (antes se
    # hacia dentro de sp_cancelar_cita, CROSS-DB a pagos_db).
    try:
        pagos_client.post(f"/api/pagos/{cita_id}/cancelar", {})
    except Exception:
        pass

    log_accion(
        accion="cancelar_cita",
        tabla_afectada="historial_citas",
        registro_id=cita_id,
        ip_origen=request.remote_addr,
    )
    return jsonify({"success": True})


@citas_bp.route("/api/citas/<int:cita_id>/completar", methods=["PUT"])
def completar_cita(cita_id):
    """Marca la cita como completada y guarda la descripcion clinica.
    Sustituye la llamada directa que hacia el gateway (sp_completar_cita)
    y el trigger trg_historial_completada (CROSS-DB, eliminado)."""
    data = request.get_json() or {}
    descripcion = (data.get("descripcion") or "").strip()
    if not descripcion:
        return jsonify({"error": "descripcion requerida"}), 400

    call_proc_execute("sp_completar_cita", (cita_id, descripcion))
    log_accion(
        accion="completar_cita",
        tabla_afectada="historial_citas",
        registro_id=cita_id,
        detalle="Cita completada con descripcion clinica",
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

    # FASE 2: telefono y verificacion de cita programada via
    # pacientes_service (antes sp_obtener_telefono_otp, CROSS-DB).
    pac_data, pac_status = pacientes_client.get(f"/api/pacientes/{dni}")
    if pac_status != 200:
        return jsonify({"error": "No se encontraron citas programadas para ese DNI."}), 404
    paciente = pac_data.get("paciente") or {}
    if not pac_data or not paciente:
        return jsonify({"error": "No se encontraron citas programadas para ese DNI."}), 404

    if not call_proc_one("sp_existe_cita_programada_paciente", (paciente["id"],)):
        return jsonify({"error": "No se encontraron citas programadas para ese DNI."}), 404

    codigo = str(random.randint(100000, 999999))
    expira = datetime.now() + timedelta(minutes=OTP_EXPIRA_MIN)

    call_proc_execute("sp_invalidar_otps_previos", (dni, accion))
    call_proc_execute("sp_insertar_otp", (dni, codigo, accion, expira))

    verbo = "modificar" if accion == "modificar" else "cancelar"
    mensaje = f"MOOVA Clinic: Tu codigo para {verbo} tu cita es {codigo}. Valido por {OTP_EXPIRA_MIN} min."
    enviado = _enviar_sms(paciente["telefono"], mensaje)

    if not enviado:
        return jsonify({"error": "No se pudo enviar el SMS."}), 500

    tel = paciente["telefono"].strip()
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
            esp_data, _ = pacientes_client.get("/api/estadisticas/especialistas")
            especialistas = int(esp_data.get("total") or 0) if esp_data else 0
        except Exception:
            pass
        try:
            cfg_data, _ = pagos_client.get("/api/pagos/configuracion/anio")
            cfg = cfg_data.get("valor") if cfg_data else None
            if cfg:
                anio_inicio = int(cfg)
        except Exception:
            pass
        total_anios = datetime.now().year - anio_inicio
        try:
            op_data, _ = pacientes_client.get("/api/estadisticas/opiniones")
            if op_data:
                total = int(op_data.get("total") or 0)
                buenas = int(op_data.get("buenas") or 0)
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