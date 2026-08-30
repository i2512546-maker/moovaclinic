import os
import requests
from datetime import date, datetime
from flask import request, jsonify, Response
from services.pacientes_service import pacientes_bp
from shared.config import APIPERU_TOKEN, APIPERU_URL
from shared.proc import call_proc, call_proc_one, call_proc_execute, call_proc_results


@pacientes_bp.route("/api/pacientes", methods=["GET"])
def listar_pacientes():
    pacientes = call_proc("sp_listar_pacientes")
    return jsonify({"success": True, "pacientes": pacientes})


@pacientes_bp.route("/api/pacientes/<dni>", methods=["GET"])
def detalle_paciente(dni):
    paciente = call_proc_one("sp_obtener_paciente_por_dni", (dni,))
    if not paciente:
        return jsonify({"error": "Paciente no encontrado"}), 404

    historial = call_proc("sp_obtener_historial_paciente", (paciente["id"],))
    return jsonify({"success": True, "paciente": paciente, "historial": historial})


@pacientes_bp.route("/api/pacientes", methods=["POST"])
def crear_paciente():
    data = request.get_json() or {}
    nombre = data.get("nombre", "").strip()
    apellido = data.get("apellido", "").strip()
    dni = data.get("dni", "").strip()
    telefono = data.get("telefono", "").strip()

    if not all([nombre, apellido, dni, telefono]):
        return jsonify({"error": "Todos los campos son requeridos."}), 400

    existente = call_proc_one("sp_existe_paciente_por_dni", (dni,))
    if existente:
        return jsonify({"error": "Ya existe un paciente con ese DNI.", "dni": existente["dni"]}), 409

    call_proc_execute("sp_crear_paciente", (
        nombre, apellido, dni, telefono,
        data.get("email"),
        data.get("fecha_nacimiento") or None,
        data.get("sexo") or None,
        data.get("direccion"),
        data.get("seguro"),
    ))
    return jsonify({"success": True, "dni": dni}), 201


@pacientes_bp.route("/api/pacientes/<dni>", methods=["PUT"])
def actualizar_paciente(dni):
    data = request.get_json() or {}

    def _val(key):
        return None if key not in data else data[key]

    if not any(k in data for k in [
        "nombre", "apellido", "telefono", "email", "estado",
        "fecha_nacimiento", "sexo", "direccion", "seguro", "dni",
    ]):
        return jsonify({"error": "Nada que actualizar."}), 400

    dni_nuevo = data["dni"] if ("dni" in data and data["dni"] != dni) else None
    result = call_proc("sp_actualizar_paciente", (
        dni,
        _val("nombre"), _val("apellido"), _val("telefono"), _val("email"),
        _val("estado"), _val("fecha_nacimiento"), _val("sexo"),
        _val("direccion"), _val("seguro"), dni_nuevo,
    ))
    return jsonify({"success": True})


@pacientes_bp.route("/api/pacientes/buscar_dni", methods=["POST"])
def buscar_dni():
    data = request.get_json() or {}
    dni = data.get("dni", "").strip()
    if len(dni) != 8 or not dni.isdigit():
        return jsonify({"success": False, "error": "DNI invalido"}), 400

    try:
        url = APIPERU_URL.format(dni=dni, token=APIPERU_TOKEN)
        resp = requests.get(url, headers={"Accept": "application/json"}, timeout=5)
        if resp.status_code == 200:
            api_data = resp.json()
            if api_data.get("success"):
                return jsonify({"success": True, "data": api_data})
    except Exception:
        pass

    return jsonify({"success": False, "error": "DNI no encontrado"}), 404


# ============================================================
# Servicios (catalogo)
# ============================================================

@pacientes_bp.route("/api/servicios", methods=["GET"])
def listar_servicios():
    servicios = call_proc("sp_listar_servicios")
    return jsonify({"success": True, "servicios": servicios})


# ============================================================
# Paquetes de sesiones
# ============================================================

@pacientes_bp.route("/api/pacientes/<int:paciente_id>/paquetes", methods=["GET"])
def listar_paquetes(paciente_id):
    paquetes = call_proc("sp_listar_paquetes", (paciente_id,))
    return jsonify({"success": True, "paquetes": paquetes})


@pacientes_bp.route("/api/pacientes/<int:paciente_id>/paquetes", methods=["POST"])
def crear_paquete(paciente_id):
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
    paquete_id = result["id"] if result else None
    return jsonify({"success": True, "paquete_id": paquete_id}), 201


# ============================================================
# Evaluaciones iniciales
# ============================================================

@pacientes_bp.route("/api/pacientes/<int:paciente_id>/evaluaciones", methods=["GET"])
def listar_evaluaciones(paciente_id):
    evaluaciones = call_proc("sp_listar_evaluaciones", (paciente_id,))
    return jsonify({"success": True, "evaluaciones": evaluaciones})


@pacientes_bp.route("/api/pacientes/<int:paciente_id>/evaluaciones", methods=["POST"])
def crear_evaluacion(paciente_id):
    data = request.get_json() or {}
    terapeuta_id = data.get("terapeuta_id")
    motivo_consulta = data.get("motivo_consulta", "").strip()

    if not terapeuta_id or not motivo_consulta:
        return jsonify({"error": "terapeuta_id y motivo_consulta son requeridos."}), 400

    result = call_proc_one("sp_crear_evaluacion", (
        paciente_id, terapeuta_id, motivo_consulta,
        data.get("escala_dolor_eva"),
        data.get("rango_movimiento"),
        data.get("objetivos_terapeuticos"),
    ))
    eval_id = result["id"] if result else None
    return jsonify({"success": True, "evaluacion_id": eval_id}), 201


# ============================================================
# Consentimientos
# ============================================================

@pacientes_bp.route("/api/pacientes/<int:paciente_id>/consentimientos", methods=["GET"])
def listar_consentimientos(paciente_id):
    consentimientos = call_proc("sp_listar_consentimientos", (paciente_id,))
    return jsonify({"success": True, "consentimientos": consentimientos})


@pacientes_bp.route("/api/pacientes/<int:paciente_id>/consentimientos", methods=["POST"])
def crear_consentimiento(paciente_id):
    data = request.get_json() or {}
    tipo = data.get("tipo", "").strip()
    texto_version = data.get("texto_version", "").strip()

    if not tipo or not texto_version:
        return jsonify({"error": "tipo y texto_version son requeridos."}), 400

    result = call_proc_one("sp_crear_consentimiento", (
        paciente_id, tipo, texto_version, data.get("ip_origen"),
    ))
    consent_id = result["id"] if result else None
    return jsonify({"success": True, "consentimiento_id": consent_id}), 201


# ============================================================
# Ficha clinica en PDF (reporte descargable para medico/admin)
# ============================================================

def _texto_pdf(valor, max_len=300):
    """Texto seguro para fuentes core de fpdf2 (latin-1). Reemplaza
    cualquier caracter fuera de rango para que el PDF nunca falle."""
    if valor is None:
        return ""
    try:
        txt = str(valor)
    except Exception:
        txt = ""
    txt = " ".join(txt.split())
    txt = txt.encode("latin-1", "replace").decode("latin-1")
    if len(txt) > max_len:
        txt = txt[:max_len - 3].rstrip() + "..."
    return txt


def _fmt_fecha(valor):
    if isinstance(valor, (datetime, date)):
        return valor.strftime("%d/%m/%Y")
    return _texto_pdf(valor)


def _fmt_soles(valor):
    try:
        return "S/. {:.2f}".format(float(valor or 0))
    except (TypeError, ValueError):
        return "S/. 0.00"


def _pdf_titulo_seccion(pdf, texto):
    pdf.ln(3)
    pdf.set_fill_color(237, 242, 247)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(47, 133, 90)
    pdf.cell(0, 8, "  " + texto, fill=True)
    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)


def _pdf_grid(pdf, pares, compact=False):
    """Una etiqueta + valor por linea, con salto de linea automatico."""
    lh = 5.0 if compact else 6.2
    fs = 9 if compact else 10
    label_w = 34
    val_w = 186 - 12 - label_w
    for lbl, val in pares:
        pdf.set_x(12)
        pdf.set_font("Helvetica", "", fs - 2)
        pdf.set_text_color(113, 128, 150)
        pdf.cell(label_w, lh, lbl + ":", new_x="RIGHT")
        pdf.set_font("Helvetica", "B", fs - 1)
        pdf.set_text_color(45, 55, 72)
        pdf.multi_cell(val_w, lh, _texto_pdf(val), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)


def _generar_ficha_pdf(paciente, citas, evaluaciones, paquetes):
    """Genera la ficha clinica en PDF con el logo de MOOVA Clinic."""
    from fpdf import FPDF

    logo_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "static", "pp.png",
    )

    verde = (47, 133, 90)
    gris = (74, 85, 104)

    pdf = FPDF(format="A4", unit="mm")
    pdf.set_margins(12, 12, 12)
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()

    # ---- Encabezado con logo ----
    if os.path.exists(logo_path):
        try:
            pdf.image(logo_path, x=12, y=10, w=30)
        except Exception:
            pass
    pdf.set_xy(46, 14)
    pdf.set_font("Helvetica", "B", 17)
    pdf.set_text_color(*verde)
    pdf.cell(0, 8, "MOOVA CLINIC")
    pdf.set_xy(46, 22)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*gris)
    pdf.cell(0, 6, "Ficha Clinica del Paciente")
    pdf.set_xy(46, 30)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 4, "Generado el " + datetime.now().strftime("%d/%m/%Y a las %H:%M"))
    pdf.set_draw_color(*verde)
    pdf.set_line_width(0.6)
    pdf.line(12, 36, 198, 36)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(11)

    # ---- Datos del paciente ----
    _pdf_titulo_seccion(pdf, "Datos del Paciente")
    sexo = {"M": "Masculino", "F": "Femenino"}.get(paciente.get("sexo"))
    sexo_txt = sexo if sexo else (_texto_pdf(paciente.get("sexo")) or "No registrado")
    _pdf_grid(pdf, [
        ("Nombre", (_texto_pdf(paciente.get("nombre")) + " " + _texto_pdf(paciente.get("apellido"))).strip()),
        ("DNI", _texto_pdf(paciente.get("dni"))),
        ("Telefono", _texto_pdf(paciente.get("telefono"))),
        ("Email", _texto_pdf(paciente.get("email")) or "No registrado"),
        ("Nacimiento", _fmt_fecha(paciente.get("fecha_nacimiento")) or "No registrado"),
        ("Sexo", sexo_txt),
        ("Direccion", _texto_pdf(paciente.get("direccion")) or "No registrado"),
        ("Seguro", _texto_pdf(paciente.get("seguro")) or "No registrado"),
    ])

    # ---- Historial de citas ----
    _pdf_titulo_seccion(pdf, "Historial de Citas ({})".format(len(citas)))
    if not citas:
        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(0, 5, "Sin citas registradas.", new_x="LMARGIN", new_y="NEXT")
    for c in citas:
        fecha_txt = _fmt_fecha(c.get("fecha_cita"))
        if c.get("hora_cita"):
            fecha_txt = (fecha_txt + " " + _texto_pdf(c.get("hora_cita"))).strip()
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*verde)
        pdf.cell(0, 5, "Cita #{}{}".format(
            _texto_pdf(c.get("cita_id")),
            " - " + fecha_txt if fecha_txt else "",
        ))
        pdf.ln(6)
        pdf.set_text_color(0, 0, 0)
        _pdf_grid(pdf, [
            ("Terapeuta", _texto_pdf(c.get("terapeuta")) or "-"),
            ("Especialidad", _texto_pdf(c.get("Especialidad")) or "-"),
            ("Estado", _texto_pdf(c.get("estado")) or "-"),
            ("Monto", _fmt_soles(c.get("monto"))),
            ("Pago", _texto_pdf(c.get("estado_pago")) or "-"),
        ], compact=True)
        diag = _texto_pdf(c.get("diagnostico"))
        nota = _texto_pdf(c.get("nota"))
        desc = _texto_pdf(c.get("descripcion"))
        if diag or nota:
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(*gris)
            pdf.cell(0, 4.5, "Nota clinica:")
            pdf.ln(5)
            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_text_color(0, 0, 0)
            if diag:
                pdf.multi_cell(0, 4.5, "  Diagnostico: " + diag, new_x="LMARGIN", new_y="NEXT")
            if nota:
                pdf.multi_cell(0, 4.5, "  " + nota, new_x="LMARGIN", new_y="NEXT")
        if desc:
            pdf.set_font("Helvetica", "I", 8.5)
            pdf.multi_cell(0, 4.5, "  Descripcion: " + desc, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    # ---- Evaluaciones ----
    _pdf_titulo_seccion(pdf, "Evaluaciones Iniciales ({})".format(len(evaluaciones)))
    if not evaluaciones:
        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(0, 5, "Sin evaluaciones registradas.", new_x="LMARGIN", new_y="NEXT")
    for ev in evaluaciones:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*verde)
        pdf.cell(0, 5, "Evaluacion del " + (_fmt_fecha(ev.get("fecha_creacion")) or "-"))
        pdf.ln(6)
        pdf.set_text_color(0, 0, 0)
        eva = _texto_pdf(ev.get("escala_dolor_eva"))
        _pdf_grid(pdf, [
            ("Terapeuta", _texto_pdf(ev.get("terapeuta_nombre")) or "-"),
            ("Dolor (EVA)", "{}/10".format(eva) if ev.get("escala_dolor_eva") is not None else "-"),
            ("Motivo de consulta", _texto_pdf(ev.get("motivo_consulta")) or "-"),
            ("Rango de movimiento", _texto_pdf(ev.get("rango_movimiento")) or "-"),
            ("Objetivos", _texto_pdf(ev.get("objetivos_terapeuticos")) or "-"),
        ], compact=True)
        pdf.ln(2)

    # ---- Paquetes ----
    _pdf_titulo_seccion(pdf, "Paquetes de Sesiones ({})".format(len(paquetes)))
    if not paquetes:
        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(0, 5, "Sin paquetes registrados.", new_x="LMARGIN", new_y="NEXT")
    for ps in paquetes:
        usadas = int(ps.get("sesiones_usadas") or 0)
        total = int(ps.get("total_sesiones") or 0)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*verde)
        pdf.cell(0, 5, "Paquete #{}".format(_texto_pdf(ps.get("id"))))
        pdf.ln(6)
        pdf.set_text_color(0, 0, 0)
        _pdf_grid(pdf, [
            ("Servicio", _texto_pdf(ps.get("servicio_nombre")) or "-"),
            ("Sesiones", "{}/{} ({} restantes)".format(usadas, total, max(total - usadas, 0))),
            ("Compra", _fmt_fecha(ps.get("fecha_compra")) or "-"),
            ("Vencimiento", _fmt_fecha(ps.get("fecha_vencimiento")) if ps.get("fecha_vencimiento") else "Sin limite"),
            ("Estado", _texto_pdf(ps.get("estado")) or "-"),
        ], compact=True)
        pdf.ln(2)

    # ---- Pie ----
    pdf.set_y(-15)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(12, pdf.get_y(), 198, pdf.get_y())
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, "Documento generado por MOOVA Clinic - Uso interno", align="C")

    return pdf.output()


@pacientes_bp.route("/api/pacientes/<int:paciente_id>/pdf", methods=["GET"])
def ficha_clinica_pdf(paciente_id):
    results = call_proc_results("sp_obtener_ficha_clinica_completa", (paciente_id,))
    if not results or not results[0]:
        return jsonify({"error": "Paciente no encontrado"}), 404

    paciente = results[0][0]
    citas = results[1] if len(results) > 1 else []
    evaluaciones = results[2] if len(results) > 2 else []
    paquetes = results[3] if len(results) > 3 else []

    try:
        pdf_bytes = bytes(_generar_ficha_pdf(paciente, citas, evaluaciones, paquetes))
    except Exception:
        return jsonify({"error": "No se pudo generar el PDF."}), 500

    dni = _texto_pdf(paciente.get("dni")) or str(paciente_id)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=ficha_clinica_{}.pdf".format(dni)},
    )
