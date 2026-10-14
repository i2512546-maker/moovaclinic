<<<<<<< Updated upstream
import secrets
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import mysql.connector
import requests as http_requests
from flask import current_app, jsonify, request
=======
import hashlib
import random
import re
import secrets
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import jwt
from flask import current_app, g, jsonify, request
>>>>>>> Stashed changes

from services.citas_service import citas_bp
from shared.api import error, ok, token_required
from shared.audit import log_accion
from shared.config import (
<<<<<<< Updated upstream
    KPIS_DB_NAME,
    OTP_EXPIRA_MIN,
    OTP_MAX_INTENTOS,
    TEXTBEE_API_KEY,
    TEXTBEE_DEVICE_ID,
    TEXTBEE_URL,
)
from shared.proc import call_proc, call_proc_execute, call_proc_one
from shared.service_client import pacientes_client, pagos_client
from shared.validators import validar_datos_paciente
=======
    IDENTITY_TOKEN_TTL_SECONDS, JWT_ALGORITHM,
    OTP_EXPIRA_MIN, OTP_MAX_INTENTOS,
    SECRET_KEY,
)
from shared.db import db_connection
from shared.proc import call_proc, call_proc_execute, call_proc_one
from shared.sms import get_sms_provider
>>>>>>> Stashed changes


def _mask_phone(phone):
    if not phone:
        return "*** ***"
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) >= 9:
        return f"{digits[:3]} *** {digits[-3:]}"
    return "*** ***"


def _hash_code(code):
    return hashlib.sha256(str(code).encode("utf-8")).hexdigest()


def _new_otp_code():
    return str(secrets.randbelow(1000000)).zfill(6)


def _issue_identity_token(dni, accion):
    now = datetime.utcnow()
    payload = {
        "dni": dni,
        "accion": accion,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=IDENTITY_TOKEN_TTL_SECONDS)).timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def _enviar_sms(phone, message):
    provider = get_sms_provider()
    return bool(provider.send(phone, message))


def _otp_rate_limit_ok(dni, ip_address):
    window_seconds = 15 * 60
    max_requests = 3
    bucket = current_app.config.setdefault("otp_rate_limit", {"dni": {}, "ip": {}})
    now = time.time()
    by_dni = bucket["dni"]
    by_ip = bucket["ip"]

    def prune(entries):
        return [ts for ts in entries if now - ts < window_seconds]

    dni_events = prune(by_dni.get(dni, []))
    ip_events = prune(by_ip.get(ip_address, []))

    if len(dni_events) >= max_requests or len(ip_events) >= max_requests:
        return False

    dni_events.append(now)
    ip_events.append(now)
    by_dni[dni] = dni_events
    by_ip[ip_address] = ip_events
    return True


def _parse_lima_datetime(fecha_str, hora_str):
    lima_tz = ZoneInfo("America/Lima")
    try:
        fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError("fecha")
    try:
        hora_dt = datetime.strptime(hora_str, "%H:%M")
    except ValueError:
        raise ValueError("hora")
    dt = datetime.combine(fecha_dt.date(), hora_dt.time()).replace(tzinfo=lima_tz)
    now = datetime.now(lima_tz)
    if dt < now:
        raise ValueError("past")
    return dt


def medico_disponible(medico_id, fecha_cita, excluir_cita_id=None):
    result = call_proc_one("sp_medico_disponible", (
        medico_id, fecha_cita, excluir_cita_id if excluir_cita_id else None,
    ))
    count = int(result["n"]) if result else 0
    return count == 0


def _mapa_pacientes():
    """{paciente_id: fila} via pacientes_service. Se usa para enriquecer
    las citas (nombre/apellido/dni/telefono) sin tocar moovacloud_pacientes."""
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


def _fmt_hora(valor):
    # mysql-connector-python representa una columna MySQL TIME como timedelta.
    # Flask JSON no puede serializar ese tipo, por eso lo llevamos a HH:MM:SS
    # en el borde de la API, igual que los tipos datetime.time/datetime.
    if isinstance(valor, timedelta):
        segundos = int(valor.total_seconds())
        signo = "-" if segundos < 0 else ""
        horas, resto = divmod(abs(segundos), 3600)
        minutos, segundos = divmod(resto, 60)
        return f"{signo}{horas:02d}:{minutos:02d}:{segundos:02d}"
    if hasattr(valor, "strftime"):
        return valor.strftime("%H:%M:%S")
    return valor


def _fmt_fecha(fila):
    if hasattr(fila.get("fecha_cita"), "strftime"):
        fila["fecha_cita"] = fila["fecha_cita"].strftime("%Y-%m-%d")
    if "hora_cita" in fila:
        fila["hora_cita"] = _fmt_hora(fila["hora_cita"])
    return fila


def _hoy_lima():
    """Fecha actual en America/Lima. El servidor puede correr en otra zona
    (hoy: UTC+2); no se usa el reloj de la maquina para decidir si una cita
    ya es 'pasada'."""
    return datetime.now(ZoneInfo("America/Lima")).date()


def _normalizar_hora_cita(hora):
    """Valida y normaliza una hora elegida por el paciente (Americana de
    Lima, sin zona): acepta HH:MM o HH:MM:SS y devuelve 'HH:MM:SS'.
    Devuelve None si no viene hora; lanza ValueError si el formato es malo."""
    if not hora:
        return None
    hora = hora.strip()
    if len(hora) == 5:
        hora = hora + ":00"
    datetime.strptime(hora, "%H:%M:%S")
    return hora


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


def _datos_paciente_cita(cita_id):
    """(paciente_id, nombre completo) de una cita para auditoria.
    Best effort: ante cualquier fallo devuelve (None, None) para que
    el registro se guarde igualmente sin entidad."""
    try:
        cita = call_proc_one("sp_detalle_cita", (cita_id,))
    except Exception:
        return None, None
    paciente_id = (cita or {}).get("paciente_id")
    if not paciente_id:
        return None, None
    try:
        data, _ = pacientes_client.get("/api/pacientes")
        mapa = {p["id"]: p for p in (data.get("pacientes") or [])}
        p = mapa.get(paciente_id) or {}
        nombre = " ".join(x for x in (p.get("nombre"), p.get("apellido")) if x).strip()
        return paciente_id, nombre or None
    except Exception:
        return paciente_id, None


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
    """Ruta publica conservada. Los terapeutas viven en moovacloud_pacientes;
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


@citas_bp.route("/api/kpis", methods=["GET"])
def kpis_resumen():
    """KPIs del panel admin (solo lectura, CROSS-DB de reportes).

    Parametros obligatorios: desde=YYYY-MM-DD, hasta=YYYY-MM-DD
    (fechas en hora de Peru). Llama a los procedimientos de la base
    moovacloud_kpis y devuelve un solo JSON:
      {"success": true, "resumen": {...}, "por_terapeuta": [...]}
    Valida formato y que desde <= hasta (400 si algo falla)."""
    desde = (request.args.get("desde") or "").strip()
    hasta = (request.args.get("hasta") or "").strip()
    if not desde or not hasta:
        return jsonify({"error": "Se requieren los parametros desde y hasta (YYYY-MM-DD)"}), 400
    try:
        desde_dt = datetime.strptime(desde, "%Y-%m-%d").date()
        hasta_dt = datetime.strptime(hasta, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Formato invalido, use YYYY-MM-DD"}), 400
    if desde_dt > hasta_dt:
        return jsonify({"error": "desde no puede ser mayor que hasta"}), 400

    try:
        resumen = call_proc_one("sp_kpis_resumen", (desde, hasta), db_name=KPIS_DB_NAME)
        por_terapeuta = call_proc("sp_kpis_por_terapeuta", (desde, hasta), db_name=KPIS_DB_NAME) or []
    except Exception as exc:
        current_app.logger.error("[kpis_resumen] Error al calcular KPIs: %s: %s", type(exc).__name__, exc)
        return jsonify({"error": "No se pudo calcular los KPIs"}), 500

    return jsonify({"success": True, "resumen": resumen, "por_terapeuta": por_terapeuta})


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
    moovacloud_citas (paciente_id, terapeuta_id, fecha_cita, estado, ...) sin
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
<<<<<<< Updated upstream
    data = request.get_json() or {}
    for campo in ["nombre", "apellido", "dni", "telefono", "medico_id", "fecha_cita"]:
        if not data.get(campo):
            return jsonify({"error": f"Campo requerido: {campo}"}), 400
=======
    payload = request.get_json(silent=True) or request.form.to_dict() or {}

    nombres = str(payload.get("nombres") or payload.get("nombre") or "").strip()
    apellidos = str(payload.get("apellidos") or payload.get("apellido") or "").strip()
    dni = str(payload.get("dni", "") or "").strip()
    telefono = str(payload.get("telefono", "") or "").strip()
    terapeuta_id = payload.get("terapeuta_id")
    fecha = str(payload.get("fecha", "") or "").strip()
    hora = str(payload.get("hora", "") or "").strip()

    required_fields = [
        ("nombres", nombres),
        ("apellidos", apellidos),
        ("dni", dni),
        ("telefono", telefono),
        ("terapeuta_id", terapeuta_id),
        ("fecha", fecha),
        ("hora", hora),
    ]
    for campo, valor in required_fields:
        if valor in (None, ""):
            return jsonify(error("4010", f"El campo {campo} es requerido", 400, detail=[{"campo": campo, "codigo": "4010", "mensaje": f"El campo {campo} es requerido"}])[0]), 400

    if len(nombres) > 100:
        return jsonify(error("4011", "El campo nombres excede el máximo permitido", 400, detail=[{"campo": "nombres", "codigo": "4011", "mensaje": "El campo nombres excede el máximo permitido"}])[0]), 400
    if len(apellidos) > 100:
        return jsonify(error("4011", "El campo apellidos excede el máximo permitido", 400, detail=[{"campo": "apellidos", "codigo": "4011", "mensaje": "El campo apellidos excede el máximo permitido"}])[0]), 400
    if not dni.isdigit() or len(dni) != 8:
        return jsonify(error("4011", "El DNI debe tener 8 dígitos numéricos", 400, detail=[{"campo": "dni", "codigo": "4011", "mensaje": "El DNI debe tener 8 dígitos numéricos"}])[0]), 400
    if not telefono.isdigit() or len(telefono) != 9:
        return jsonify(error("4012", "El teléfono debe tener 9 dígitos numéricos", 400, detail=[{"campo": "telefono", "codigo": "4012", "mensaje": "El teléfono debe tener 9 dígitos numéricos"}])[0]), 400
>>>>>>> Stashed changes

    # Validacion de formato estricta, ANTES de tocar DB o servicios.
    error_formato = validar_datos_paciente(
        str(data.get("nombre") or "").strip(),
        str(data.get("apellido") or "").strip(),
        str(data.get("dni") or "").strip(),
        str(data.get("telefono") or "").strip(),
    )
    if error_formato:
        return jsonify({"error": error_formato}), 400

    try:
<<<<<<< Updated upstream
        fecha_obj = datetime.strptime(data["fecha_cita"], "%Y-%m-%d").date()
        if fecha_obj < _hoy_lima():
            return jsonify({"error": "La fecha no puede ser en el pasado"}), 400
    except ValueError:
        return jsonify({"error": "Formato de fecha invalido (YYYY-MM-DD)"}), 400

    try:
        hora_cita = _normalizar_hora_cita(data.get("hora_cita"))
    except ValueError:
        return jsonify({"error": "Formato de hora invalido (HH:MM)"}), 400

    # Disponibilidad del medico (DB local). Blindada: si la BD no responde
    # en tiempo, respondemos 500 en vez de colgar el request.
    try:
        if not medico_disponible(data["medico_id"], data["fecha_cita"]):
            return jsonify({"error": "El medico ya tiene una cita ese dia"}), 409
    except Exception as exc:
        current_app.logger.error(
            "[crear_cita] Error en sp_medico_disponible: %s: %s",
            type(exc).__name__, exc,
        )
        return jsonify({"error": "No se pudo procesar la solicitud, intenta de nuevo"}), 500

    # FASE 2: precio del medico via pacientes_service (antes
    # sp_consulta_medico_precio, CROSS-DB).
    try:
        medico_data, medico_status = pacientes_client.get(f"/api/terapeutas/{data['medico_id']}")
    except Exception as exc:
        current_app.logger.error(
            "[crear_cita] Error HTTP a pacientes_service (/terapeutas/%s): %s: %s",
            data["medico_id"], type(exc).__name__, exc,
        )
        return jsonify({"error": "Servicio de médicos no disponible, intenta de nuevo"}), 502
    if medico_status != 200:
        return jsonify({"error": "Medico no encontrado"}), 404
    medico = medico_data.get("terapeuta") or {}
=======
        cita_dt = _parse_lima_datetime(fecha, hora)
    except ValueError as exc:
        if str(exc) == "fecha":
            return jsonify(error("4014", "La fecha no es válida", 400, detail=[{"campo": "fecha", "codigo": "4014", "mensaje": "La fecha no es válida"}])[0]), 400
        if str(exc) == "hora":
            return jsonify(error("4014", "La hora no es válida", 400, detail=[{"campo": "hora", "codigo": "4014", "mensaje": "La hora no es válida"}])[0]), 400
        return jsonify(error("4014", "La fecha y hora no pueden estar en el pasado", 400, detail=[{"campo": "fecha", "codigo": "4014", "mensaje": "La fecha y hora no pueden estar en el pasado"}])[0]), 400

    if cita_dt < datetime.now(ZoneInfo("America/Lima")):
        return jsonify(error("4014", "La fecha y hora no pueden estar en el pasado", 400, detail=[{"campo": "fecha", "codigo": "4014", "mensaje": "La fecha y hora no pueden estar en el pasado"}])[0]), 400

    try:
        terapeuta_id = int(terapeuta_id)
    except (TypeError, ValueError):
        return jsonify(error("4011", "El terapeuta_id debe ser numérico", 400, detail=[{"campo": "terapeuta_id", "codigo": "4011", "mensaje": "El terapeuta_id debe ser numérico"}])[0]), 400
>>>>>>> Stashed changes

    terapeuta = call_proc_one("sp_consulta_medico_precio", (terapeuta_id,))
    if not terapeuta:
        return jsonify(error("4040", "Terapeuta no existe o está inactivo", 404, detail=[{"campo": "terapeuta_id", "codigo": "4040", "mensaje": "Terapeuta no existe o está inactivo"}])[0]), 404

<<<<<<< Updated upstream
    # FASE 2: resolver/crear paciente via pacientes_service.
    try:
        pac_data, pac_status = pacientes_client.get(f"/api/pacientes/dni/{data['dni']}")
        if pac_status == 200:
            paciente_id = pac_data.get("id")
        else:
            creado, creado_status = pacientes_client.post("/api/pacientes/min", {
                "nombre": data["nombre"], "apellido": data["apellido"],
                "dni": data["dni"], "telefono": data["telefono"],
            })
            if creado_status not in (200, 201):
                return jsonify({
                    "error": (creado or {}).get("error") or "No se pudo registrar al paciente.",
                }), creado_status if creado_status in (400, 409) else 400
            paciente_id = (creado or {}).get("id")
    except Exception as exc:
        current_app.logger.error(
            "[crear_cita] Error HTTP a pacientes_service (resolver/crear paciente): %s: %s",
            type(exc).__name__, exc,
        )
        return jsonify({"error": "Servicio de pacientes no disponible, intenta de nuevo"}), 502
=======
    precio = float(terapeuta.get("precio") or 0.0)
    anticipo = round(precio / 2, 2)

    paciente = call_proc_one("sp_obtener_paciente_id_dni", (dni,))
    if paciente:
        paciente_id = paciente["id"]
    else:
        creado = call_proc_one("sp_crear_paciente_min", (nombres, apellidos, dni, telefono))
        paciente_id = creado["id"] if creado else None
    if not paciente_id:
        return jsonify(error("5000", "Error interno del servidor", 500, detail=[{"campo": "general", "codigo": "5000", "mensaje": "Error interno del servidor"}])[0]), 500
>>>>>>> Stashed changes

    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id FROM historial_citas
            WHERE terapeuta_id = %s
              AND estado = 'programada'
              AND (
                    (DATE(fecha_cita) = DATE(%s) AND TIME(fecha_cita) = TIME(%s))
                    OR (DATE(fecha_cita) = DATE(%s) AND hora_cita = %s)
              )
            FOR UPDATE
            """,
            (terapeuta_id, cita_dt.date(), cita_dt.time(), cita_dt.date(), hora),
        )
        existing = cursor.fetchone()
        if existing:
            conn.rollback()
            return jsonify(error("4090", "El horario ya está ocupado", 409, detail=[{"campo": "hora", "codigo": "4090", "mensaje": "El horario ya está ocupado"}])[0]), 409

<<<<<<< Updated upstream
    try:
        cita = call_proc_one("sp_crear_cita", (paciente_id, data["medico_id"], servicio_id, data["fecha_cita"], hora_cita))
    except mysql.connector.Error as exc:
        current_app.logger.error(
            "[crear_cita] Error en BD (sp_crear_cita): %s: %s",
            type(exc).__name__, exc,
        )
        return jsonify({"error": "No se pudo procesar la solicitud, intenta de nuevo"}), 500
    except Exception as exc:
        current_app.logger.error(
            "[crear_cita] Error inesperado en sp_crear_cita: %s: %s",
            type(exc).__name__, exc,
        )
        return jsonify({"error": "No se pudo procesar la solicitud, intenta de nuevo"}), 500
    cita_id = cita["id"] if cita else None
=======
        cursor.execute(
            """
            INSERT INTO historial_citas (paciente_id, terapeuta_id, servicio_id, fecha_cita, hora_cita, estado)
            VALUES (%s, %s, NULL, %s, %s, 'programada')
            """,
            (paciente_id, terapeuta_id, cita_dt, hora, ),
        )
        cita_id = cursor.lastrowid
        conn.commit()
>>>>>>> Stashed changes

    log_accion(
        usuario_id=None,
        accion="crear_cita",
        tabla_afectada="historial_citas",
        registro_id=cita_id,
<<<<<<< Updated upstream
        detalle=f"Cita creada para paciente_id={paciente_id}, medico_id={data['medico_id']}, fecha={data['fecha_cita']}, hora={hora_cita or 'sin hora'}",
=======
        detalle=f"Cita creada para paciente_id={paciente_id}, terapeuta_id={terapeuta_id}, fecha={fecha}, hora={hora}",
>>>>>>> Stashed changes
        ip_origen=request.remote_addr,
        entidad_tipo="paciente",
        entidad_id=paciente_id,
        entidad_nombre=(" ".join(x for x in (data.get("nombre"), data.get("apellido")) if x).strip() or None),
    )

<<<<<<< Updated upstream
    metodo_pago = data.get("metodo_pago", "").strip()
    if metodo_pago and anticipo > 0 and cita_id:
        # FASE 2: pago anticipado via pagos_service (antes
        # sp_crear_pago_anticipo, CROSS-DB).
        try:
            pago_data, pago_status = pagos_client.post("/api/pagos/anticipo", {
                "cita_id": cita_id,
                "paciente_id": paciente_id,
                "monto": anticipo,
                "metodo_pago": metodo_pago,
            })
            if pago_status not in (200, 201):
                current_app.logger.warning(
                    "[crear_cita] pagos_service no creo el anticipo (status %s): %s",
                    pago_status, pago_data,
                )
        except Exception as exc:
            current_app.logger.error(
                "[crear_cita] Error HTTP a pagos_service (anticipo): %s: %s",
                type(exc).__name__, exc,
            )

    return jsonify({
        "success": True, "cita_id": cita_id,
        "costo": costo, "anticipo": anticipo,
    }), 201
=======
    payload = ok(
        "Cita creada correctamente",
        {
            "cita_id": cita_id,
            "paciente_id": paciente_id,
            "estado": "programada",
            "precio": round(precio, 2),
            "monto_anticipo": round(anticipo, 2),
            "fecha": fecha,
            "hora": hora,
        },
    )
    return jsonify(payload), 201
>>>>>>> Stashed changes


@citas_bp.route("/api/citas/<int:cita_id>", methods=["PUT"])
def modificar_cita(cita_id):
    data = request.get_json() or {}
    nueva_fecha = data.get("fecha_cita", "")
    nuevo_medico = data.get("medico_id", "")
    if not nueva_fecha or not nuevo_medico:
        return jsonify({"error": "Se requieren fecha_cita y medico_id"}), 400
    try:
        fecha_obj = datetime.strptime(nueva_fecha, "%Y-%m-%d").date()
        if fecha_obj < _hoy_lima():
            return jsonify({"error": "La fecha no puede ser en el pasado"}), 400
    except ValueError:
        return jsonify({"error": "Formato invalido"}), 400
    try:
        hora_cita = _normalizar_hora_cita(data.get("hora_cita"))
    except ValueError:
        return jsonify({"error": "Formato de hora invalido (HH:MM)"}), 400
    if not medico_disponible(nuevo_medico, nueva_fecha, excluir_cita_id=cita_id):
        return jsonify({"error": "El medico ya tiene una cita ese dia"}), 409

    result = call_proc_one("sp_modificar_cita", (cita_id, nueva_fecha, nuevo_medico, hora_cita))
    if not result or int(result.get("actualizadas") or 0) == 0:
        return jsonify({"error": "Cita no encontrada o ya no esta programada"}), 404
    ent_paciente_id, ent_paciente_nombre = _datos_paciente_cita(cita_id)
    log_accion(
        accion="reprogramar_cita",
        tabla_afectada="historial_citas",
        registro_id=cita_id,
        detalle=f"Cita reprogramada a fecha={nueva_fecha}, hora={hora_cita or 'sin hora'}, medico_id={nuevo_medico}",
        ip_origen=request.remote_addr,
        entidad_tipo="paciente",
        entidad_id=ent_paciente_id,
        entidad_nombre=ent_paciente_nombre,
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

    ent_paciente_id, ent_paciente_nombre = _datos_paciente_cita(cita_id)
    log_accion(
        accion="cancelar_cita",
        tabla_afectada="historial_citas",
        registro_id=cita_id,
        ip_origen=request.remote_addr,
        entidad_tipo="paciente",
        entidad_id=ent_paciente_id,
        entidad_nombre=ent_paciente_nombre,
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
    ent_paciente_id, ent_paciente_nombre = _datos_paciente_cita(cita_id)
    log_accion(
        accion="completar_cita",
        tabla_afectada="historial_citas",
        registro_id=cita_id,
        detalle="Cita completada con descripcion clinica",
        ip_origen=request.remote_addr,
        entidad_tipo="paciente",
        entidad_id=ent_paciente_id,
        entidad_nombre=ent_paciente_nombre,
    )
    return jsonify({"success": True})


@citas_bp.route("/api/otp/solicitar", methods=["POST"])
def otp_solicitar():
    data = request.get_json(silent=True) or {}
    dni = str(data.get("dni", "") or "").strip()
    accion = str(data.get("accion", "modificar") or "modificar").strip().lower()
    if accion not in {"modificar", "cancelar", "continuar"}:
        accion = "modificar"

    if not dni or not dni.isdigit() or len(dni) != 8:
        return jsonify(error("4011", "El DNI debe tener 8 dígitos numéricos", 400, detail=[{"campo": "dni", "codigo": "4011", "mensaje": "El DNI debe tener 8 dígitos numéricos"}])[0]), 400

    if not _otp_rate_limit_ok(dni, request.remote_addr or "unknown"):
        return jsonify(error("4290", "Demasiadas solicitudes, inténtelo más tarde", 429, detail=[{"campo": "dni", "codigo": "4290", "mensaje": "Demasiadas solicitudes, inténtelo más tarde"}])[0]), 429

<<<<<<< Updated upstream
    # FASE 2: telefono y verificacion de cita programada via
    # pacientes_service (antes sp_obtener_telefono_otp, CROSS-DB).
    pac_data, pac_status = pacientes_client.get(f"/api/pacientes/{dni}")
    if pac_status != 200:
        return jsonify({"error": "No se encontraron citas programadas para ese DNI."}), 404
    paciente = pac_data.get("paciente") or {}
    if not pac_data or not paciente:
        return jsonify({"error": "No se encontraron citas programadas para ese DNI."}), 404

    if accion == "tratamiento":
        # Los pacientes que continuan un tratamiento NO necesitan una
        # cita programada previa: se valida que tengan al menos un
        # paquete activo con sesiones disponibles (via pagos_service).
        try:
            paq_data, _ = pagos_client.get(f"/api/pagos/pacientes/{paciente['id']}/paquetes")
            tiene_paquete_activo = any(
                p.get("estado") == "activo"
                and int(p.get("sesiones_usadas") or 0) < int(p.get("total_sesiones") or 0)
                for p in ((paq_data or {}).get("paquetes") or [])
            )
        except Exception:
            tiene_paquete_activo = False
        if not tiene_paquete_activo:
            return jsonify({"error": "No tienes tratamientos activos pendientes de pago."}), 404
    else:
        if not call_proc_one("sp_existe_cita_programada_paciente", (paciente["id"],)):
            return jsonify({"error": "No se encontraron citas programadas para ese DNI."}), 404

    codigo = str(secrets.randbelow(900000) + 100000)
=======
    persona = call_proc_one("sp_obtener_telefono_otp", (dni,))
    phone = (persona or {}).get("telefono") if persona else ""

    codigo = _new_otp_code()
>>>>>>> Stashed changes
    expira = datetime.now() + timedelta(minutes=OTP_EXPIRA_MIN)

    if persona:
        call_proc_execute("sp_invalidar_otps_previos", (dni, accion))
        call_proc_execute("sp_insertar_otp", (dni, _hash_code(codigo), accion, expira))
        mensaje = f"MOOVA Clinic: Tu codigo para {accion} es {codigo}. Valido por {OTP_EXPIRA_MIN} min."
        enviado = _enviar_sms(phone, mensaje)
        if not enviado:
            return jsonify(error("5001", "No se pudo enviar el SMS", 500, detail=[{"campo": "telefono", "codigo": "5001", "mensaje": "No se pudo enviar el SMS"}])[0]), 500
    else:
        # respuesta uniforme para no filtrar existencia de pacientes
        pass

<<<<<<< Updated upstream
    verbo = {
        "modificar": "modificar tu cita",
        "cancelar": "cancelar tu cita",
        "tratamiento": "continuar tu tratamiento",
    }.get(accion, "continuar tu tratamiento")
    mensaje = f"MOOVA Clinic: Tu codigo para {verbo} es {codigo}. Valido por {OTP_EXPIRA_MIN} min."
    enviado = _enviar_sms(paciente["telefono"], mensaje)
=======
    return jsonify(ok("OTP enviado", {
        "telefono": _mask_phone(phone),
        "expira_en": int(OTP_EXPIRA_MIN * 60),
        "intentos": OTP_MAX_INTENTOS,
    })), 200
>>>>>>> Stashed changes


<<<<<<< Updated upstream
    tel = paciente["telefono"].strip()
    tel_mask = tel[:3] + "***" + tel[-3:] if len(tel) >= 6 else "***"
    return jsonify({"success": True, "tel_mask": tel_mask})
=======
@citas_bp.route("/api/otp/verificar", methods=["POST"])
def otp_verificar():
    data = request.get_json(silent=True) or {}
    dni = str(data.get("dni", "") or "").strip()
    codigo = str(data.get("codigo", data.get("otp", "")) or "").strip()
    accion = str(data.get("accion", "modificar") or "modificar").strip().lower()
    if accion not in {"modificar", "cancelar", "continuar"}:
        accion = "modificar"

    if not dni or not dni.isdigit() or len(dni) != 8:
        return jsonify(error("4011", "El DNI debe tener 8 dígitos numéricos", 400, detail=[{"campo": "dni", "codigo": "4011", "mensaje": "El DNI debe tener 8 dígitos numéricos"}])[0]), 400
    if not codigo or not codigo.isdigit() or len(codigo) != 6:
        return jsonify(error("4010", "El código OTP es requerido", 400, detail=[{"campo": "codigo", "codigo": "4010", "mensaje": "El código OTP es requerido"}])[0]), 400

    otp = call_proc_one("sp_obtener_otp", (dni, accion))
    if not otp:
        return jsonify(error("4103", "OTP inexistente", 404, detail=[{"campo": "codigo", "codigo": "4103", "mensaje": "OTP inexistente"}])[0]), 404

    if otp.get("intentos") is not None and int(otp["intentos"]) >= OTP_MAX_INTENTOS:
        return jsonify(error("4102", "OTP agotado", 401, detail=[{"campo": "codigo", "codigo": "4102", "mensaje": "OTP agotado"}])[0]), 401

    if otp.get("expira_en") and datetime.now() > otp["expira_en"]:
        return jsonify(error("4101", "OTP expirado", 401, detail=[{"campo": "codigo", "codigo": "4101", "mensaje": "OTP expirado"}])[0]), 401

    if _hash_code(codigo) != (otp.get("codigo") or ""):
        call_proc_execute("sp_incrementar_intentos_otp", (otp["id"],))
        restantes = max(OTP_MAX_INTENTOS - (int(otp.get("intentos") or 0) + 1), 0)
        return jsonify(error("4100", "OTP incorrecto", 401, detail=[{"campo": "codigo", "codigo": "4100", "mensaje": f"OTP incorrecto. Intentos restantes: {restantes}"}])[0]), 401

    call_proc_execute("sp_marcar_otp_usado", (otp["id"],))

    paciente = call_proc_one("sp_obtener_paciente_por_dni", (dni,))
    paciente_id = paciente["id"] if paciente else None
    citas = []
    paquetes = []
    if paciente_id:
        with db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT h.id AS cita_id, DATE(h.fecha_cita) AS fecha, h.hora_cita AS hora,
                       CONCAT(u.nombre, ' ', u.apellido) AS especialista, h.estado
                FROM historial_citas h
                JOIN terapeutas t ON t.id = h.terapeuta_id
                JOIN usuarios u ON u.id = t.usuario_id
                WHERE h.paciente_id = %s
                ORDER BY h.fecha_cita DESC
                LIMIT 20
                """,
                (paciente_id,),
            )
            citas = cursor.fetchall()

            cursor.execute(
                """
                SELECT id AS paquete_id, servicio_id, total_sesiones, sesiones_usadas,
                       estado, fecha_vencimiento
                FROM paquetes_sesiones
                WHERE paciente_id = %s AND estado = 'activo'
                ORDER BY fecha_compra DESC
                """,
                (paciente_id,),
            )
            paquetes = cursor.fetchall()

    identity_token = _issue_identity_token(dni, accion)
    return jsonify(ok("OTP verificado", {
        "verificado": True,
        "identity_token": identity_token,
        "expira_en": IDENTITY_TOKEN_TTL_SECONDS,
        "citas": [{
            "cita_id": item.get("cita_id"),
            "fecha": str(item.get("fecha") or ""),
            "hora": str(item.get("hora") or ""),
            "especialista": item.get("especialista") or "",
            "estado": item.get("estado") or "",
        } for item in citas],
        "paquetes": [{
            "paquete_id": item.get("paquete_id"),
            "servicio_id": item.get("servicio_id"),
            "total_sesiones": item.get("total_sesiones"),
            "sesiones_usadas": item.get("sesiones_usadas"),
            "estado": item.get("estado"),
            "fecha_vencimiento": str(item.get("fecha_vencimiento") or ""),
        } for item in paquetes],
    })), 200


@citas_bp.route("/api/citas/otp/solicitar", methods=["POST"])
def solicitar_otp():
    return otp_solicitar()
>>>>>>> Stashed changes


@citas_bp.route("/api/citas/otp/verificar", methods=["POST"])
def verificar_otp():
    return otp_verificar()


@citas_bp.route("/api/citas/agenda", methods=["GET"])
@token_required(roles=["admin", "terapeuta"])
def agenda_citas():
    fecha_param = (request.args.get("fecha") or "").strip()
    terapeuta_id_param = request.args.get("terapeuta_id", type=int)

    if fecha_param:
        try:
            fecha_dt = datetime.strptime(fecha_param, "%Y-%m-%d")
        except ValueError:
            return jsonify(error("4014", "La fecha no es válida", 400, detail=[{"campo": "fecha", "codigo": "4014", "mensaje": "La fecha no es válida"}])[0]), 400
    else:
        fecha_dt = datetime.now(ZoneInfo("America/Lima"))
        fecha_param = fecha_dt.strftime("%Y-%m-%d")

    if g.user_role == "terapeuta":
        terapeuta = call_proc_one("SELECT id FROM terapeutas WHERE usuario_id = %s AND activo = 1 LIMIT 1", (g.user_id,))
        if not terapeuta:
            return jsonify(error("4030", "Sin permisos para el rol", 403, detail=[{"campo": "terapeuta_id", "codigo": "4030", "mensaje": "Sin permisos para el rol"}])[0]), 403
        terapeuta_id = int(terapeuta["id"])
    else:
        if terapeuta_id_param is not None:
            terapeuta = call_proc_one("SELECT id FROM terapeutas WHERE id = %s AND activo = 1", (terapeuta_id_param,))
            if not terapeuta:
                return jsonify(error("4040", "Terapeuta no existe o está inactivo", 404, detail=[{"campo": "terapeuta_id", "codigo": "4040", "mensaje": "Terapeuta no existe o está inactivo"}])[0]), 404
            terapeuta_id = int(terapeuta_id_param)
        else:
            terapeuta_id = None

    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        if g.user_role == "terapeuta":
            cursor.execute(
                """
                SELECT h.id AS cita_id, h.hora_cita AS hora, CONCAT(p.nombre, ' ', p.apellido) AS paciente,
                       e.nombre AS especialidad, h.estado
                FROM historial_citas h
                JOIN pacientes p ON p.id = h.paciente_id
                LEFT JOIN terapeutas t ON t.id = h.terapeuta_id
                LEFT JOIN especialidades e ON e.id = t.especialidad_id
                WHERE h.fecha_cita = %s AND h.terapeuta_id = %s
                ORDER BY h.hora_cita ASC
                """,
                (fecha_param, terapeuta_id),
            )
        else:
            if terapeuta_id is None:
                cursor.execute(
                    """
                    SELECT h.id AS cita_id, h.hora_cita AS hora, CONCAT(p.nombre, ' ', p.apellido) AS paciente,
                           e.nombre AS especialidad, h.estado
                    FROM historial_citas h
                    JOIN pacientes p ON p.id = h.paciente_id
                    LEFT JOIN terapeutas t ON t.id = h.terapeuta_id
                    LEFT JOIN especialidades e ON e.id = t.especialidad_id
                    WHERE h.fecha_cita = %s
                    ORDER BY h.hora_cita ASC
                    """,
                    (fecha_param,),
                )
            else:
                cursor.execute(
                    """
                    SELECT h.id AS cita_id, h.hora_cita AS hora, CONCAT(p.nombre, ' ', p.apellido) AS paciente,
                           e.nombre AS especialidad, h.estado
                    FROM historial_citas h
                    JOIN pacientes p ON p.id = h.paciente_id
                    LEFT JOIN terapeutas t ON t.id = h.terapeuta_id
                    LEFT JOIN especialidades e ON e.id = t.especialidad_id
                    WHERE h.fecha_cita = %s AND h.terapeuta_id = %s
                    ORDER BY h.hora_cita ASC
                    """,
                    (fecha_param, terapeuta_id),
                )
        citas = cursor.fetchall()

    items = []
    for row in citas:
        items.append({
            "cita_id": row["cita_id"],
            "hora": row["hora"].strftime("%H:%M") if row.get("hora") is not None and hasattr(row.get("hora"), "strftime") else (row.get("hora") or ""),
            "paciente": row.get("paciente") or "",
            "especialidad": row.get("especialidad") or "",
            "estado": row.get("estado") or "",
        })

    return jsonify(ok("Agenda del día", {"total": len(items), "citas": items})), 200


def _get_identity_from_header():
    token = request.headers.get("X-Identity-Token", "").strip()
    if not token:
        return None, error("4104", "Token de identidad ausente", 401, detail=[{"campo": "x-identity-token", "codigo": "4104", "mensaje": "Token de identidad ausente"}])[0]

    try:
<<<<<<< Updated upstream
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
=======
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM], options={"require": ["exp", "dni"]})
    except jwt.ExpiredSignatureError:
        return None, error("4104", "Token de identidad expirado", 401, detail=[{"campo": "x-identity-token", "codigo": "4104", "mensaje": "Token de identidad expirado"}])[0]
>>>>>>> Stashed changes
    except Exception:
        return None, error("4104", "Token de identidad inválido", 401, detail=[{"campo": "x-identity-token", "codigo": "4104", "mensaje": "Token de identidad inválido"}])[0]

    dni = str(payload.get("dni") or "").strip()
    if not dni or not dni.isdigit() or len(dni) != 8:
        return None, error("4104", "Token de identidad inválido", 401, detail=[{"campo": "x-identity-token", "codigo": "4104", "mensaje": "Token de identidad inválido"}])[0]

    return dni, None


def _validar_cita_pertenece_al_dni(cita_id, dni):
    cita = call_proc_one("sp_detalle_cita", (cita_id,))
    if not cita:
        return None, error("4040", "Cita no existe", 404, detail=[{"campo": "cita_id", "codigo": "4040", "mensaje": "Cita no existe"}])[0]

    paciente = call_proc_one("sp_obtener_paciente_por_dni", (dni,))
    if not paciente:
        return None, error("4104", "Token no pertenece a este DNI", 401, detail=[{"campo": "dni", "codigo": "4104", "mensaje": "Token no pertenece a este DNI"}])[0]

    if int(cita.get("paciente_id") or 0) != int(paciente.get("id") or 0):
        return None, error("4104", "Cita no pertenece al DNI autenticado", 401, detail=[{"campo": "cita_id", "codigo": "4104", "mensaje": "Cita no pertenece al DNI autenticado"}])[0]

    return cita, None


@citas_bp.route("/api/citas/<int:cita_id>", methods=["PUT"])
def modificar_cita_segura(cita_id):
    dni, err = _get_identity_from_header()
    if err:
        return jsonify(err), 401

    cita, err = _validar_cita_pertenece_al_dni(cita_id, dni)
    if err:
        return jsonify(err), 401 if "4104" in str(err) else 404

    data = request.get_json(silent=True) or {}
    fecha = str(data.get("fecha") or "").strip()
    hora = str(data.get("hora") or "").strip()
    terapeuta_id = data.get("terapeuta_id")

    if not fecha or not hora or not terapeuta_id:
        return jsonify(error("4010", "Los campos fecha, hora y terapeuta_id son requeridos", 400, detail=[{"campo": "general", "codigo": "4010", "mensaje": "Los campos fecha, hora y terapeuta_id son requeridos"}])[0]), 400

    try:
        cita_dt = _parse_lima_datetime(fecha, hora)
    except ValueError:
        return jsonify(error("4014", "La fecha y hora no son válidas", 400, detail=[{"campo": "fecha", "codigo": "4014", "mensaje": "La fecha y hora no son válidas"}])[0]), 400

    try:
        terapeuta_id = int(terapeuta_id)
    except (TypeError, ValueError):
        return jsonify(error("4011", "El terapeuta_id debe ser numérico", 400, detail=[{"campo": "terapeuta_id", "codigo": "4011", "mensaje": "El terapeuta_id debe ser numérico"}])[0]), 400

    terapeuta = call_proc_one("sp_consulta_medico_precio", (terapeuta_id,))
    if not terapeuta:
        return jsonify(error("4040", "Terapeuta no existe o está inactivo", 404, detail=[{"campo": "terapeuta_id", "codigo": "4040", "mensaje": "Terapeuta no existe o está inactivo"}])[0]), 404

    if str(cita.get("estado") or "").lower() not in {"programada", "confirmada"}:
        return jsonify(error("4091", "La cita no puede ser modificada en su estado actual", 409, detail=[{"campo": "estado", "codigo": "4091", "mensaje": "La cita no puede ser modificada en su estado actual"}])[0]), 409

    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id FROM historial_citas
            WHERE terapeuta_id = %s
              AND estado IN ('programada', 'confirmada')
              AND id <> %s
              AND fecha_cita = %s
              AND hora_cita = %s
            FOR UPDATE
            """,
            (terapeuta_id, cita_id, cita_dt.date(), hora),
        )
        if cursor.fetchone():
            conn.rollback()
            return jsonify(error("4090", "Horario ocupado", 409, detail=[{"campo": "hora", "codigo": "4090", "mensaje": "Horario ocupado"}])[0]), 409

        cursor.execute(
            """
            UPDATE historial_citas
            SET terapeuta_id = %s, fecha_cita = %s, hora_cita = %s, estado = 'programada'
            WHERE id = %s AND paciente_id = %s
            """,
            (terapeuta_id, cita_dt, hora, cita_id, cita["paciente_id"]),
        )
        conn.commit()

    log_accion(
        usuario_id=None,
        accion="reprogramar_cita",
        tabla_afectada="historial_citas",
        registro_id=cita_id,
        detalle=f"Cita reprogramada por DNI {dni} a fecha={fecha}, hora={hora}, terapeuta_id={terapeuta_id}",
        ip_origen=request.remote_addr,
    )
    return jsonify(ok("Cita modificada", {
        "cita_id": cita_id,
        "estado": "programada",
        "fecha": fecha,
        "hora": hora,
    })), 200


@citas_bp.route("/api/citas/<int:cita_id>", methods=["DELETE"])
def cancelar_cita_segura(cita_id):
    dni, err = _get_identity_from_header()
    if err:
        return jsonify(err), 401

    cita, err = _validar_cita_pertenece_al_dni(cita_id, dni)
    if err:
        return jsonify(err), 401 if "4104" in str(err) else 404

    if str(cita.get("estado") or "").lower() in {"cancelada", "completada"}:
        return jsonify(error("4091", "La cita no puede ser cancelada en su estado actual", 409, detail=[{"campo": "estado", "codigo": "4091", "mensaje": "La cita no puede ser cancelada en su estado actual"}])[0]), 409

    pago = call_proc_one("sp_obtener_pago", (cita_id,))
    pago_estado = "sin_pago"
    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            UPDATE historial_citas
            SET estado = 'cancelada'
            WHERE id = %s AND paciente_id = %s
            """,
            (cita_id, cita["paciente_id"]),
        )
        if pago and str(pago.get("estado_pago") or "").lower() == "pendiente":
            cursor.execute(
                "UPDATE pagos SET estado_pago = 'cancelado' WHERE cita_id = %s AND estado_pago = 'pendiente'",
                (cita_id,),
            )
            pago_estado = "cancelado"
        elif pago and str(pago.get("estado_pago") or "").lower() == "pagado":
            cursor.execute(
                "UPDATE pagos SET estado_pago = 'reembolso_en_proceso' WHERE cita_id = %s AND estado_pago = 'pagado'",
                (cita_id,),
            )
            pago_estado = "reembolso_en_proceso"
        conn.commit()

    if pago and str(pago.get("estado_pago") or "").lower() == "pagado":
        try:
            cita_dt = cita.get("fecha_cita")
            if isinstance(cita_dt, str):
                fecha_dt = datetime.strptime(cita_dt, "%Y-%m-%d")
            else:
                fecha_dt = cita_dt
            horas = (fecha_dt - datetime.now()).total_seconds() / 3600 if hasattr(fecha_dt, "__sub__") else 0
            if horas < 24:
                with db_connection() as conn2:
                    cursor2 = conn2.cursor()
                    cursor2.execute(
                        "UPDATE pagos SET estado_pago = 'retenido' WHERE cita_id = %s AND estado_pago = 'reembolso_en_proceso'",
                        (cita_id,),
                    )
                    conn2.commit()
                pago_estado = "retenido"
        except Exception:
            pass

    log_accion(
        usuario_id=None,
        accion="cancelar_cita",
        tabla_afectada="historial_citas",
        registro_id=cita_id,
        detalle=f"Cita cancelada por DNI {dni}; pago_estado={pago_estado}",
        ip_origen=request.remote_addr,
    )
    return jsonify(ok("Cita cancelada", {
        "cita_id": cita_id,
        "estado": "cancelada",
        "pago_estado": pago_estado,
    })), 200


@citas_bp.route("/api/citas/sesion", methods=["POST"])
def crear_cita_con_paquete():
    dni, err = _get_identity_from_header()
    if err:
        return jsonify(err), 401

    data = request.get_json(silent=True) or {}
    paquete_id = data.get("paquete_id")
    fecha = str(data.get("fecha") or "").strip()
    hora = str(data.get("hora") or "").strip()
    terapeuta_id = data.get("terapeuta_id")

    if paquete_id in (None, "") or not fecha or not hora or not terapeuta_id:
        return jsonify(error("4010", "Los campos paquete_id, fecha, hora y terapeuta_id son requeridos", 400, detail=[{"campo": "general", "codigo": "4010", "mensaje": "Los campos paquete_id, fecha, hora y terapeuta_id son requeridos"}])[0]), 400

    try:
        paquete_id = int(paquete_id)
    except (TypeError, ValueError):
        return jsonify(error("4011", "El paquete_id debe ser numérico", 400, detail=[{"campo": "paquete_id", "codigo": "4011", "mensaje": "El paquete_id debe ser numérico"}])[0]), 400

    try:
        terap_id = int(terapeuta_id)
    except (TypeError, ValueError):
        return jsonify(error("4011", "El terapeuta_id debe ser numérico", 400, detail=[{"campo": "terapeuta_id", "codigo": "4011", "mensaje": "El terapeuta_id debe ser numérico"}])[0]), 400

    try:
        cita_dt = _parse_lima_datetime(fecha, hora)
    except ValueError:
        return jsonify(error("4014", "La fecha y hora no son válidas", 400, detail=[{"campo": "fecha", "codigo": "4014", "mensaje": "La fecha y hora no son válidas"}])[0]), 400

    paciente = call_proc_one("sp_obtener_paciente_por_dni", (dni,))
    if not paciente:
        return jsonify(error("4104", "Token de identidad inválido", 401, detail=[{"campo": "dni", "codigo": "4104", "mensaje": "Token de identidad inválido"}])[0]), 401

    paquete = call_proc_one("SELECT * FROM paquetes_sesiones WHERE id = %s FOR UPDATE", (paquete_id,))
    if not paquete:
        return jsonify(error("4040", "Paquete no existe", 404, detail=[{"campo": "paquete_id", "codigo": "4040", "mensaje": "Paquete no existe"}])[0]), 404
    if int(paquete.get("paciente_id") or 0) != int(paciente.get("id") or 0):
        return jsonify(error("4104", "Paquete no pertenece al DNI autenticado", 401, detail=[{"campo": "paquete_id", "codigo": "4104", "mensaje": "Paquete no pertenece al DNI autenticado"}])[0]), 401
    if str(paquete.get("estado") or "").lower() != "activo":
        return jsonify(error("4092", "Paquete no activo o vencido", 409, detail=[{"campo": "paquete_id", "codigo": "4092", "mensaje": "Paquete no activo o vencido"}])[0]), 409
    if paquete.get("fecha_vencimiento") and datetime.strptime(str(paquete["fecha_vencimiento"]), "%Y-%m-%d") < datetime.now().date():
        return jsonify(error("4092", "Paquete vencido", 409, detail=[{"campo": "paquete_id", "codigo": "4092", "mensaje": "Paquete vencido"}])[0]), 409

    sesiones_usadas = int(paquete.get("sesiones_usadas") or 0)
    total_sesiones = int(paquete.get("total_sesiones") or 0)
    sesiones_restantes = total_sesiones - sesiones_usadas
    if sesiones_restantes <= 0:
        return jsonify(error("4092", "Paquete sin sesiones disponibles", 409, detail=[{"campo": "paquete_id", "codigo": "4092", "mensaje": "Paquete sin sesiones disponibles"}])[0]), 409

    terapeuta = call_proc_one("SELECT id, activo FROM terapeutas WHERE id = %s AND activo = 1 LIMIT 1", (terap_id,))
    if not terapeuta:
        return jsonify(error("4040", "Terapeuta no existe o está inactivo", 404, detail=[{"campo": "terapeuta_id", "codigo": "4040", "mensaje": "Terapeuta no existe o está inactivo"}])[0]), 404

    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id FROM historial_citas
            WHERE terapeuta_id = %s
              AND estado IN ('programada', 'confirmada')
              AND fecha_cita = %s
              AND hora_cita = %s
            FOR UPDATE
            """,
            (terap_id, cita_dt.date(), hora),
        )
        if cursor.fetchone():
            conn.rollback()
            return jsonify(error("4090", "Horario ocupado", 409, detail=[{"campo": "hora", "codigo": "4090", "mensaje": "Horario ocupado"}])[0]), 409

        cursor.execute(
            """
            INSERT INTO historial_citas (paciente_id, terapeuta_id, servicio_id, fecha_cita, hora_cita, estado)
            VALUES (%s, %s, %s, %s, %s, 'programada')
            """,
            (int(paciente["id"]), terap_id, int(paquete["servicio_id"]), cita_dt, hora),
        )
        cita_id = cursor.lastrowid

        cursor.execute(
            """
            UPDATE paquetes_sesiones
            SET sesiones_usadas = sesiones_usadas + 1,
                estado = CASE WHEN sesiones_usadas + 1 >= total_sesiones THEN 'agotado' ELSE 'activo' END
            WHERE id = %s
            """,
            (paquete_id,),
        )
        conn.commit()

    log_accion(
        usuario_id=None,
        accion="crear_cita_paquete",
        tabla_afectada="historial_citas",
        registro_id=cita_id,
        detalle=f"Cita creada por paquete_id={paquete_id}, dni={dni}, terapeuta_id={terap_id}, fecha={fecha}, hora={hora}",
        ip_origen=request.remote_addr,
    )

    nuevas_usadas = sesiones_usadas + 1
    nuevas_restantes = max(total_sesiones - nuevas_usadas, 0)
    return jsonify(ok("Cita creada con paquete", {
        "cita_id": cita_id,
        "sesiones_usadas": nuevas_usadas,
        "sesiones_restantes": nuevas_restantes,
    })), 201


@citas_bp.route("/api/citas/<int:cita_id>", methods=["PUT"])
def modificar_cita_legacy(cita_id):
    return modificar_cita_segura(cita_id)


@citas_bp.route("/api/citas/<int:cita_id>", methods=["DELETE"])
def cancelar_cita_legacy(cita_id):
    return cancelar_cita_segura(cita_id)
