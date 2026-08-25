import random
import requests as http_requests
from datetime import datetime, timedelta
from flask import request, jsonify
from services.citas_service import citas_bp
from shared.db import db_connection
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
    with db_connection() as conn:
        cursor = conn.cursor()
        if excluir_cita_id:
            cursor.execute(
                """SELECT COUNT(*) FROM historial_citas
                   WHERE terapeuta_id = %s AND fecha_cita = %s
                     AND estado = 'programada' AND id != %s""",
                (medico_id, fecha_cita, excluir_cita_id),
            )
        else:
            cursor.execute(
                """SELECT COUNT(*) FROM historial_citas
                   WHERE terapeuta_id = %s AND fecha_cita = %s
                     AND estado = 'programada'""",
                (medico_id, fecha_cita),
            )
        (count,) = cursor.fetchone()
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
    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT ID, Nombre, Especialidad, precio FROM terapeutas WHERE activo = 1 ORDER BY Nombre")
        terapeutas = cursor.fetchall()
    return jsonify({"success": True, "terapeutas": terapeutas})


@citas_bp.route("/api/citas", methods=["GET"])
def listar_citas():
    dni = request.args.get("dni", "")
    fecha = request.args.get("fecha", "")
    estado = request.args.get("estado", "programada")
    medico_id = request.args.get("medico_id", "")

    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT h.id, h.fecha_cita, h.estado, h.descripcion, h.hora_cita,
                   p.nombre, p.apellido, p.dni, p.telefono, p.id AS persona_id,
                   t.Nombre AS terapeuta, t.Especialidad, h.terapeuta_id
            FROM historial_citas h
            JOIN personas p ON h.persona_id = p.id
            JOIN terapeutas t ON h.terapeuta_id = t.ID
            WHERE h.estado = %s
        """
        params = [estado]
        if dni:
            query += " AND p.dni = %s"
            params.append(dni)
        if fecha:
            query += " AND h.fecha_cita = %s"
            params.append(fecha)
        if medico_id:
            query += " AND h.terapeuta_id = %s"
            params.append(medico_id)
        query += " ORDER BY h.fecha_cita ASC"
        cursor.execute(query, params)
        citas = cursor.fetchall()

    for c in citas:
        if hasattr(c["fecha_cita"], "strftime"):
            c["fecha_cita"] = c["fecha_cita"].strftime("%Y-%m-%d")
    return jsonify({"success": True, "total": len(citas), "citas": citas})


@citas_bp.route("/api/citas/<int:cita_id>", methods=["GET"])
def detalle_cita(cita_id):
    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT h.*, p.nombre, p.apellido, p.dni, p.telefono, p.id AS persona_id,
                      t.Nombre AS terapeuta, t.Especialidad
               FROM historial_citas h
               JOIN personas p ON h.persona_id = p.id
               JOIN terapeutas t ON h.terapeuta_id = t.ID
               WHERE h.id = %s""", (cita_id,),
        )
        cita = cursor.fetchone()
    if not cita:
        return jsonify({"error": "Cita no encontrada"}), 404
    if hasattr(cita["fecha_cita"], "strftime"):
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

    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT Nombre, Especialidad, Telefono, precio FROM terapeutas WHERE ID = %s AND activo = 1",
            (data["medico_id"],),
        )
        medico = cursor.fetchone()
        if not medico:
            return jsonify({"error": "Medico no encontrado"}), 404

        costo = float(medico["precio"]) if medico.get("precio") else 0.0
        anticipo = round(costo / 2, 2)

        cursor.execute("SELECT id FROM personas WHERE dni = %s", (data["dni"],))
        persona = cursor.fetchone()
        if persona:
            persona_id = persona["id"]
        else:
            cursor.execute(
                "INSERT INTO personas (nombre, apellido, dni, telefono) VALUES (%s,%s,%s,%s)",
                (data["nombre"], data["apellido"], data["dni"], data["telefono"]),
            )
            conn.commit()
            persona_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO historial_citas (persona_id, terapeuta_id, fecha_cita, estado) VALUES (%s,%s,%s,'programada')",
            (persona_id, data["medico_id"], data["fecha_cita"]),
        )
        conn.commit()
        cita_id = cursor.lastrowid

        metodo_pago = data.get("metodo_pago", "").strip()
        if metodo_pago and anticipo > 0:
            cursor.execute(
                "INSERT INTO pagos (cita_id, persona_id, monto, metodo_pago, estado_pago, notas) VALUES (%s,%s,%s,%s,'pendiente','Anticipo 50%%')",
                (cita_id, persona_id, anticipo, metodo_pago),
            )
            conn.commit()

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

    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE historial_citas SET fecha_cita=%s, terapeuta_id=%s WHERE id=%s AND estado='programada'",
            (nueva_fecha, nuevo_medico, cita_id),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": "Cita no encontrada o ya no esta programada"}), 404
    return jsonify({"success": True})


@citas_bp.route("/api/citas/<int:cita_id>", methods=["DELETE"])
def cancelar_cita(cita_id):
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE historial_citas SET estado='cancelada' WHERE id=%s AND estado='programada'", (cita_id,))
        cursor.execute("UPDATE pagos SET estado_pago='cancelado' WHERE cita_id=%s AND estado_pago='pendiente'", (cita_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": "Cita no encontrada"}), 404
    return jsonify({"success": True})


@citas_bp.route("/api/citas/otp/solicitar", methods=["POST"])
def solicitar_otp():
    data = request.get_json() or {}
    dni = data.get("dni", "").strip()
    accion = data.get("accion", "modificar")

    if not dni or len(dni) != 8 or not dni.isdigit():
        return jsonify({"error": "DNI invalido"}), 400

    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT p.telefono FROM personas p
               JOIN historial_citas h ON h.persona_id = p.id
               WHERE p.dni = %s AND h.estado = 'programada' LIMIT 1""",
            (dni,),
        )
        persona = cursor.fetchone()

    if not persona:
        return jsonify({"error": "No se encontraron citas programadas para ese DNI."}), 404

    codigo = str(random.randint(100000, 999999))
    expira = datetime.now() + timedelta(minutes=OTP_EXPIRA_MIN)

    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE otp_verificaciones SET usado=1 WHERE dni=%s AND accion=%s AND usado=0",
            (dni, accion),
        )
        cursor.execute(
            "INSERT INTO otp_verificaciones (dni, codigo, accion, expira_en) VALUES (%s,%s,%s,%s)",
            (dni, codigo, accion, expira),
        )
        conn.commit()

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

    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT * FROM otp_verificaciones
               WHERE dni=%s AND accion=%s AND usado=0
               ORDER BY creado_en DESC LIMIT 1""",
            (dni, accion),
        )
        otp = cursor.fetchone()

        if not otp:
            return jsonify({"resultado": "no_existe"})
        if otp["intentos"] >= OTP_MAX_INTENTOS:
            return jsonify({"resultado": "agotado"})
        if datetime.now() > otp["expira_en"]:
            return jsonify({"resultado": "expirado"})
        if otp["codigo"] != codigo:
            cursor.execute("UPDATE otp_verificaciones SET intentos=intentos+1 WHERE id=%s", (otp["id"],))
            conn.commit()
            restantes = OTP_MAX_INTENTOS - otp["intentos"] - 1
            return jsonify({"resultado": "incorrecto", "restantes": restantes})

        cursor.execute("UPDATE otp_verificaciones SET usado=1 WHERE id=%s", (otp["id"],))
        conn.commit()

    return jsonify({"resultado": "ok"})


@citas_bp.route("/api/citas/estadisticas", methods=["GET"])
def estadisticas():
    from shared.config import REDES_SOCIALES
    anio_inicio = 2023
    recuperados = especialistas = tasa_exito = total_anios = 0
    try:
        with db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute("SELECT COUNT(DISTINCT persona_id) AS total FROM historial_citas WHERE estado='completada'")
                recuperados = cursor.fetchone()["total"]
            except Exception:
                pass
            try:
                cursor.execute("SELECT COUNT(*) AS total FROM terapeutas WHERE activo=1")
                especialistas = cursor.fetchone()["total"]
            except Exception:
                pass
            try:
                cursor.execute("SELECT valor FROM configuracion WHERE clave='anio_inicio'")
                cfg = cursor.fetchone()
                if cfg:
                    anio_inicio = int(cfg["valor"])
            except Exception:
                pass
            total_anios = datetime.now().year - anio_inicio
            try:
                cursor.execute("SELECT COUNT(*) AS total FROM opiniones WHERE visible=1")
                total = cursor.fetchone()["total"]
                if total > 0:
                    cursor.execute("SELECT COUNT(*) AS buenas FROM opiniones WHERE calificacion>=4 AND visible=1")
                    buenas = cursor.fetchone()["buenas"]
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
