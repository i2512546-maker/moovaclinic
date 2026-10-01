"""Generacion de la ficha clinica del paciente en PDF (reportlab)."""
import io
from datetime import date, datetime
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from shared.fechas import fmt_fecha, fmt_hora

_MORADO = colors.HexColor("#5B2B82")
_MORADO_CLARO = colors.HexColor("#EDE3F5")
_GRIS = colors.HexColor("#555555")


def _txt(valor):
    """Normaliza cualquier valor de MySQL/JSON a texto plano para el PDF."""
    if valor is None:
        return ""
    if isinstance(valor, (datetime, date)):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, Decimal):
        return f"{valor:.2f}"
    if isinstance(valor, float):
        return f"{valor:.2f}"
    if isinstance(valor, bool):
        return "Si" if valor else "No"
    return str(valor)


def _styles():
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle(
            "titulo", parent=base["Title"], fontSize=17, leading=21,
            textColor=colors.white, alignment=TA_CENTER, spaceAfter=0,
        ),
        "subtitulo": ParagraphStyle(
            "subtitulo", parent=base["Normal"], fontSize=8.5, leading=11,
            textColor=colors.white, alignment=TA_CENTER,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontSize=10.5, leading=13,
            textColor=_MORADO, spaceBefore=11, spaceAfter=4,
        ),
        "celda": ParagraphStyle("celda", parent=base["Normal"], fontSize=7.4, leading=9),
        "etiqueta": ParagraphStyle("etiqueta", parent=base["Normal"], fontSize=8.6, leading=11),
        "pie": ParagraphStyle("pie", parent=base["Normal"], fontSize=7, leading=9, textColor=_GRIS),
    }


def _p(texto, estilo):
    """Escapa el texto y lo envuelve como Paragraph para que no rompa el layout."""
    dato = _txt(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(dato or "-", estilo)


def _tabla(cabeceras, filas, anchos, st, alineaciones=None):
    datos = [[_p(c, st["celda"]) for c in cabeceras]]
    for fila in filas:
        datos.append([_p(v, st["celda"]) for v in fila])

    t = Table(datos, colWidths=anchos, repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), _MORADO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9B8D9")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(1, len(datos)):
        if i % 2 == 0:
            estilo.append(("BACKGROUND", (0, i), (-1, i), _MORADO_CLARO))
    if alineaciones:
        for col, alineacion in alineaciones.items():
            estilo.append(("ALIGN", (col, 1), (col, -1), alineacion))
    t.setStyle(TableStyle(estilo))
    return t


def _bloque_identificacion(st, campos):
    """Rejilla de 4 columnas (etiqueta / valor) para los datos del paciente."""
    filas = []
    for i in range(0, len(campos), 2):
        par = campos[i:i + 2]
        fila = []
        for etiqueta, valor in par:
            fila.append(_p(etiqueta, st["etiqueta"]))
            fila.append(_p(valor, st["celda"]))
        if len(par) == 1:
            fila += ["", ""]
        filas.append(fila)

    t = Table(filas, colWidths=[32 * mm, 55 * mm, 32 * mm, 55 * mm], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("TEXTCOLOR", (0, 0), (0, -1), _MORADO),
        ("TEXTCOLOR", (2, 0), (2, -1), _MORADO),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def build_ficha_clinica_pdf(paciente, historial, paquetes, evaluaciones,
                            consentimientos, generado_por=None):
    """Devuelve los bytes de la ficha clinica en PDF (A4 apaisado)."""
    st = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
        title=f"Ficha clinica - {paciente.get('nombre', '')} {paciente.get('apellido', '')}".strip(),
        author="MOOVA Clinic",
    )
    w = doc.width
    e = []

    # Encabezado en una sola celda para que el fondo morado abarque todo el ancho.
    e.append(Table(
        [[_p("MOOVA CLINIC  -  FICHA CLINICA DEL PACIENTE", st["titulo"])],
         [_p("Documento generado automaticamente. Uso exclusivo del personal autorizado.", st["subtitulo"])]],
        colWidths=[w],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _MORADO),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ])))
    e.append(Spacer(1, 6 * mm))

    # --- Datos de identificacion ---
    e.append(_p("1. Datos del paciente", st["h2"]))
    e.append(_bloque_identificacion(st, [
        ("Nombre y apellidos", f"{_txt(paciente.get('nombre'))} {_txt(paciente.get('apellido'))}"),
        ("DNI", paciente.get("dni")),
        ("Fecha de nacimiento", fmt_fecha(paciente.get("fecha_nacimiento"))),
        ("Sexo", paciente.get("sexo")),
        ("Telefono", paciente.get("telefono")),
        ("Correo", paciente.get("email")),
        ("Direccion", paciente.get("direccion")),
        ("Seguro", paciente.get("seguro")),
        ("Estado", paciente.get("estado")),
        ("Registrado el", fmt_fecha(paciente.get("creado_en"), con_hora=True)),
    ]))
    e.append(Spacer(1, 4 * mm))

    # --- Historial de citas ---
    e.append(_p("2. Historial de citas", st["h2"]))
    if historial:
        filas = [
            (fmt_fecha(h.get("fecha_cita")), fmt_hora(h.get("hora_cita")), h.get("terapeuta"),
             h.get("especialidad"), h.get("estado"),
             f"S/. {h['monto']:.2f}" if h.get("monto") not in (None, "") else "-",
             h.get("metodo_pago") or "-", h.get("estado_pago") or "-")
            for h in historial
        ]
        e.append(_tabla(
            ["Fecha", "Hora", "Terapeuta", "Especialidad", "Estado",
             "Monto", "Metodo de pago", "Estado del pago"],
            filas,
            [24 * mm, 14 * mm, 42 * mm, 38 * mm, 22 * mm, 22 * mm, 32 * mm, 30 * mm],
            st, alineaciones={0: "CENTER", 1: "CENTER", 5: "RIGHT"}))
    else:
        e.append(_p("Sin citas registradas.", st["celda"]))

    # --- Paquetes ---
    if paquetes:
        e.append(Spacer(1, 5 * mm))
        e.append(_p("3. Paquetes de sesiones", st["h2"]))
        filas = [
            (p.get("servicio_nombre"),
             p.get("total_sesiones"), p.get("sesiones_usadas"),
             (p.get("total_sesiones") or 0) - (p.get("sesiones_usadas") or 0),
             fmt_fecha(p.get("fecha_compra")),
             fmt_fecha(p.get("fecha_vencimiento")) or "Sin limite", p.get("estado"))
            for p in paquetes
        ]
        e.append(_tabla(
            ["Servicio", "Sesiones", "Usadas", "Restantes", "Compra", "Vencimiento", "Estado"],
            filas,
            [58 * mm, 20 * mm, 18 * mm, 20 * mm, 25 * mm, 30 * mm, 25 * mm],
            st, alineaciones={1: "CENTER", 2: "CENTER", 3: "CENTER"}))

    # --- Evaluaciones iniciales ---
    if evaluaciones:
        e.append(Spacer(1, 5 * mm))
        e.append(_p("4. Evaluaciones iniciales", st["h2"]))
        filas = [
            (fmt_fecha(v.get("fecha_creacion")), v.get("terapeuta_nombre"),
             v.get("motivo_consulta"), v.get("escala_dolor_eva"),
             v.get("rango_movimiento"), v.get("objetivos_terapeuticos"))
            for v in evaluaciones
        ]
        e.append(_tabla(
            ["Fecha", "Terapeuta", "Motivo de consulta", "Dolor (EVA)",
             "Rango de movimiento", "Objetivos terapeuticos"],
            filas,
            [24 * mm, 40 * mm, 55 * mm, 20 * mm, 35 * mm, 55 * mm],
            st, alineaciones={0: "CENTER", 3: "CENTER"}))

    # --- Consentimientos ---
    if consentimientos:
        e.append(Spacer(1, 5 * mm))
        e.append(_p("5. Consentimientos informados", st["h2"]))
        filas = [
            (c.get("tipo"), c.get("texto_version"),
             fmt_fecha(c.get("aceptado_en"), con_hora=True),
             c.get("ip_origen") or "-")
            for c in consentimientos
        ]
        e.append(_tabla(
            ["Tipo", "Version del texto", "Fecha de aceptacion", "IP de origen"],
            filas, [70 * mm, 40 * mm, 45 * mm, 50 * mm],
            st, alineaciones={2: "CENTER"}))

    # --- Firma ---
    e.append(Spacer(1, 12 * mm))
    e.append(_p(
        f"Emitido el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}"
        + (f" por {generado_por}" if generado_por else "")
        + ". Este documento refleja el estado de la informacion al momento de su descarga.",
        st["pie"]))

    doc.build(e)
    return buf.getvalue()