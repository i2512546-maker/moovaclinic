import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import mysql.connector
import requests as http_requests
from flask import current_app, jsonify, request

from services.citas_service import citas_bp
from shared.audit import log_accion
from shared.config import (
    CUPO_POR_SLOT,
    KPIS_DB_NAME,
    OTP_EXPIRA_MIN,
    OTP_MAX_INTENTOS,
    RIESGO_DIAS_UMBRAL,
    TEXTBEE_API_KEY,
    TEXTBEE_DEVICE_ID,
    TEXTBEE_URL,
)
from shared.fechas import ahora_lima, hoy_lima
from shared.horarios import (
    autoasignar,
    contar_ocupados,
    generar_slots,
    validar_slot,
)
from shared.proc import call_proc, call_proc_execute, call_proc_one
from shared.service_client import auth_client, pacientes_client, pagos_client
from shared.validators import normalizar_telefono, validar_datos_paciente, validar_telefono


# Los catálogos de pacientes y terapeutas se usan en cada carga de agenda.
# Mantenerlos unos segundos evita repetir varias consultas MySQL por navegación.
_CATALOGO_CACHE_TTL = 20.0
_CATALOGO_CACHE = {}
_CATALOGO_CACHE_LOCK = threading.Lock()


def _catalogo_cacheado(clave, cargar):
    ahora = time.monotonic()
    with _CATALOGO_CACHE_LOCK:
        entrada = _CATALOGO_CACHE.get(clave)
        if entrada and ahora - entrada[0] < _CATALOGO_CACHE_TTL:
            return entrada[1]

    datos = cargar()
    # No guardar respuestas vacías: podrían ser consecuencia de una caída
    # temporal del servicio y no queremos ocultarla durante todo el TTL.
    if datos:
        with _CATALOGO_CACHE_LOCK:
            _CATALOGO_CACHE[clave] = (time.monotonic(), datos)
    return datos


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
    except Exception as exc:
        # False es el contrato: el envio de SMS nunca rompe el flujo
        # que lo pide (cita, recordatorio, OTP). Se loguea igual para
        # poder distinguir "nadie lo pidio" de "TextBee esta caido".
        current_app.logger.warning(
            "No se pudo enviar el SMS al telefono %s: %s: %s",
            telefono, type(exc).__name__, exc,
        )
        return False


def medico_disponible(medico_id, fecha_cita, excluir_cita_id=None):
    result = call_proc_one("sp_medico_disponible", (
        medico_id, fecha_cita, excluir_cita_id if excluir_cita_id else None,
    ))
    count = int(result["n"]) if result else 0
    return count == 0


def _mapa_pacientes(timeout=None):
    """{paciente_id: fila} via pacientes_service, con cache breve para la agenda."""
    def cargar():
        try:
            kwargs = {"timeout": timeout} if timeout else {}
            data, _ = pacientes_client.get(
                "/api/pacientes", params={"incluir_resumen": "0"}, **kwargs
            )
            pacientes = data.get("pacientes") or []
            return {p["id"]: p for p in pacientes}
        except Exception:
            return {}

    # Las operaciones sensibles pueden pedir timeout propio y no usan cache.
    return cargar() if timeout else _catalogo_cacheado("pacientes", cargar)


def _mapa_terapeutas(timeout=None):
    """{terapeuta_id: fila} via pacientes_service, con cache breve para la agenda."""
    def cargar():
        try:
            kwargs = {"timeout": timeout} if timeout else {}
            data, _ = pacientes_client.get("/api/terapeutas", **kwargs)
            terapeutas = data.get("terapeutas") or []
            return {t["ID"]: t for t in terapeutas}
        except Exception:
            return {}

    return cargar() if timeout else _catalogo_cacheado("terapeutas", cargar)



def _mapa_servicios():
    """{servicio_id: fila} con la duración real configurada para cada servicio."""
    def cargar():
        try:
            data, _ = pacientes_client.get("/api/servicios")
            servicios = data.get("servicios") or []
            return {
                fila.get("id", fila.get("ID")): fila
                for fila in servicios
                if fila.get("id", fila.get("ID")) is not None
            }
        except Exception as exc:
            current_app.logger.warning("No se pudo cargar el catálogo de servicios: %s", exc)
            return {}

    return _catalogo_cacheado("servicios", cargar)


def _enriquecer_horario_cita(cita, servicios=None):
    """Calcula la hora de término a partir de la duración real del servicio."""
    servicios = servicios if servicios is not None else _mapa_servicios()
    servicio_id = cita.get("servicio_id")
    servicio = servicios.get(servicio_id) or servicios.get(
        int(servicio_id) if str(servicio_id or "").isdigit() else servicio_id
    )
    duracion = (servicio or {}).get("duracion_min", (servicio or {}).get("Duracion_min"))
    cita["duracion_min"] = int(duracion) if duracion is not None else None
    hora_inicio = cita.get("hora_cita")
    cita["hora_fin"] = None
    if hora_inicio and cita["duracion_min"] is not None:
        try:
            texto_hora = str(_fmt_hora(hora_inicio))
            try:
                inicio = datetime.strptime(texto_hora[:8], "%H:%M:%S")
            except ValueError:
                inicio = datetime.strptime(texto_hora[:5], "%H:%M")
            cita["hora_fin"] = (inicio + timedelta(minutes=cita["duracion_min"])).strftime("%H:%M")
        except (TypeError, ValueError):
            cita["hora_fin"] = None
    return cita


def _mapas_enriquecimiento():
    """Descarga en paralelo los dos catálogos usados para enriquecer citas."""
    with ThreadPoolExecutor(max_workers=2) as executor:
        pacientes_futuro = executor.submit(_mapa_pacientes)
        terapeutas_futuro = executor.submit(_mapa_terapeutas)
        return pacientes_futuro.result(), terapeutas_futuro.result()


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
        # Reutiliza el catálogo breve ya usado por la agenda; no vuelve a
        # descargar y recorrer todos los pacientes por cada acción auditada.
        p = _mapa_pacientes().get(paciente_id) or {}
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
    se consultan en proceso mediante el modulo de pacientes."""
    data, status = pacientes_client.get("/api/terapeutas")
    return jsonify(data), status


@citas_bp.route("/api/citas/ocupadas", methods=["GET"])
def listar_fechas_ocupadas():
    medico_id = request.args.get("medico_id", "")
    desde_txt = request.args.get("desde", "")
    hasta_txt = request.args.get("hasta", "")
    if not medico_id.isdigit() or int(medico_id) < 1:
        return jsonify({"error": "medico_id inválido"}), 400

    try:
        desde = datetime.strptime(desde_txt, "%Y-%m-%d").date()
        hasta = datetime.strptime(hasta_txt, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Las fechas deben tener formato YYYY-MM-DD"}), 400
    if desde.isoformat() != desde_txt or hasta.isoformat() != hasta_txt:
        return jsonify({"error": "Las fechas deben tener formato YYYY-MM-DD"}), 400
    if hasta < desde:
        return jsonify({"error": "El rango de fechas no es válido"}), 400
    if (hasta - desde).days > 90:
        return jsonify({"error": "El rango máximo es de 90 días"}), 400

    # Consulta indexada por rango; la alternativa mantiene compatibilidad
    # mientras se aplica la migración en bases que aún no tienen el SP.
    try:
        filas = call_proc(
            "sp_disponibilidad_citas_rango",
            (int(medico_id), desde_txt, hasta_txt),
        ) or []
    except mysql.connector.Error as exc:
        if getattr(exc, "errno", None) != 1305:
            raise
        filas = []
        for estado in ("programada", "confirmada", "pendiente_pago"):
            filas.extend(call_proc("sp_listar_citas", (
                estado, None, desde_txt, medico_id,
            )) or [])

    horas_por_fecha = {}
    for cita in filas:
        fecha = cita.get("fecha_cita")
        if isinstance(fecha, (date, datetime)):
            fecha = fecha.strftime("%Y-%m-%d")
        elif fecha:
            fecha = str(fecha)[:10]
        if not fecha or not desde_txt <= fecha <= hasta_txt:
            continue
        hora = cita.get("hora_cita")
        if isinstance(hora, datetime):
            hora = hora.strftime("%H:%M")
        elif hasattr(hora, "strftime"):
            hora = hora.strftime("%H:%M")
        elif hora:
            hora = str(hora)[:5]
        if hora:
            horas_por_fecha.setdefault(fecha, set()).add(hora)

    slots = set(generar_slots())
    fechas_completas = sorted(
        fecha for fecha, horas in horas_por_fecha.items()
        if slots.issubset(horas)
    )
    return jsonify({
        "fechas": fechas_completas,
        "horas_ocupadas": {
            fecha: sorted(horas) for fecha, horas in horas_por_fecha.items()
        },
    })

@citas_bp.route("/api/citas", methods=["GET"])
def listar_citas():
    dni = request.args.get("dni", "") or None
    fecha = request.args.get("fecha", "") or None
    estado = request.args.get("estado", "programada")
    medico_id = request.args.get("medico_id", "") or None

    # sp_listar_citas es local; el filtro por dni se aplica en Python
    # tras enriquecer con datos obtenidos del modulo de pacientes.
    citas = call_proc("sp_listar_citas", (estado, None, fecha, medico_id))

    resumen = {}
    for r in (call_proc("sp_resumen_pacientes") or []):
        resumen[r["paciente_id"]] = r["total"]

    pacientes, terapeutas = _mapas_enriquecimiento()

    resultado = []
    for c in citas:
        _enriquecer_cita(c, pacientes, terapeutas)
        c["total_visitas"] = resumen.get(c.get("paciente_id"), 0)
        _fmt_fecha(c)
        if dni and c.get("dni") != dni:
            continue
        resultado.append(c)

    return jsonify({"success": True, "total": len(resultado), "citas": resultado})


@citas_bp.route("/api/citas/seguimiento", methods=["GET"])
def seguimiento_citas():
    """Devuelve cancelaciones e inasistencias dentro de un rango semanal."""
    desde = (request.args.get("desde") or "").strip()
    hasta = (request.args.get("hasta") or "").strip()
    try:
        desde_dt = datetime.strptime(desde, "%Y-%m-%d").date()
        hasta_dt = datetime.strptime(hasta, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"success": False, "error": "Se requieren desde y hasta en formato YYYY-MM-DD"}), 400
    if desde_dt > hasta_dt:
        return jsonify({"success": False, "error": "La fecha inicial no puede ser posterior a la final"}), 400

    try:
        citas = call_proc("sp_listar_citas_seguimiento", (desde, hasta)) or []
    except mysql.connector.Error as exc:
        if getattr(exc, "errno", None) != 1305:
            raise
        # Compatibilidad temporal hasta aplicar la migración agrupada.
        citas = []
        for estado in ("cancelada", "no_asistio"):
            filas = call_proc("sp_listar_citas", (estado, None, desde, None)) or []
            citas.extend(
                cita for cita in filas
                if desde <= str(cita.get("fecha_cita") or "")[:10] <= hasta
            )

    pacientes, terapeutas = _mapas_enriquecimiento() if citas else ({}, {})
    resultado = []
    vistos = set()
    for cita in citas:
        _fmt_fecha(cita)
        cita_id = cita.get("id") or cita.get("historial_id") or cita.get("cita_id")
        clave = str(cita_id) if cita_id is not None else None
        if clave is not None and clave in vistos:
            continue
        _enriquecer_cita(cita, pacientes, terapeutas)
        if clave is not None:
            vistos.add(clave)
        resultado.append(cita)

    resultado.sort(key=lambda c: (str(c.get("fecha_cita") or ""), str(c.get("hora_cita") or "")))
    return jsonify({
        "success": True,
        "total": len(resultado),
        "canceladas": sum(1 for c in resultado if c.get("estado") == "cancelada"),
        "no_asistidos": sum(1 for c in resultado if c.get("estado") == "no_asistio"),
        "citas": resultado,
    })


@citas_bp.route("/api/citas/agenda", methods=["GET"])
def agenda_dia():
    """Devuelve la agenda diaria con una sola carga de datos auxiliares."""
    fecha = (request.args.get("fecha") or "").strip()
    try:
        datetime.strptime(fecha, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Se requiere fecha con formato YYYY-MM-DD"}), 400

    # Este procedimiento filtra por igualdad de fecha en MySQL y usa
    # el índice de fecha; no descarga las citas de todos los días futuros.
    try:
        citas = call_proc("sp_listar_citas_dia", (fecha,)) or []
    except mysql.connector.Error as exc:
        if getattr(exc, "errno", None) != 1305:
            raise
        # Compatibilidad temporal si la migración SQL aún no se ejecutó.
        current_app.logger.warning("Falta sp_listar_citas_dia; usando consulta compatible")
        citas = []
        for estado in ("programada", "confirmada", "cancelada", "completada", "no_asistio"):
            citas.extend(call_proc("sp_listar_citas", (estado, None, fecha, None)) or [])
    if not citas:
        return jsonify({"success": True, "total": 0, "citas": []})

    try:
        filas_resumen = call_proc("sp_resumen_pacientes_agenda", (fecha,)) or []
    except mysql.connector.Error as exc:
        if getattr(exc, "errno", None) != 1305:
            raise
        current_app.logger.warning("Falta sp_resumen_pacientes_agenda; usando resumen general")
        filas_resumen = call_proc("sp_resumen_pacientes") or []
    resumen = {fila["paciente_id"]: fila["total"] for fila in filas_resumen}
    pacientes, terapeutas = _mapas_enriquecimiento()
    servicios = _mapa_servicios()

    resultado = []
    vistos = set()
    for cita in citas:
        if str(cita.get("fecha_cita", ""))[:10] != fecha:
            continue
        _enriquecer_cita(cita, pacientes, terapeutas)
        _enriquecer_horario_cita(cita, servicios)
        cita["total_visitas"] = resumen.get(cita.get("paciente_id"), 0)
        _fmt_fecha(cita)
        cita_id = cita.get("id") or cita.get("historial_id") or cita.get("cita_id")
        clave = str(cita_id) if cita_id is not None else None
        if clave is None or clave not in vistos:
            resultado.append(cita)
            if clave is not None:
                vistos.add(clave)

    return jsonify({"success": True, "total": len(resultado), "citas": resultado})


@citas_bp.route("/api/citas/resumen-panel", methods=["GET"])
def resumen_panel_admin():
    """Carga los datos mínimos del panel admin sin enriquecer listas completas."""
    fecha = (request.args.get("fecha") or "").strip()
    desde = (request.args.get("desde") or "").strip()
    try:
        datetime.strptime(fecha, "%Y-%m-%d")
        datetime.strptime(desde, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "Fechas requeridas con formato YYYY-MM-DD"}), 400

    try:
        citas_dia = call_proc("sp_listar_citas_dia", (fecha,)) or []
        filas_conteo = call_proc("sp_resumen_citas_estados", (desde,)) or []
        conteos = {fila["estado"]: int(fila["total"]) for fila in filas_conteo}
    except mysql.connector.Error as exc:
        if getattr(exc, "errno", None) != 1305:
            raise
        # La pantalla sigue funcionando si el despliegue de código se
        # adelanta a la migración SQL; al aplicarla entra la ruta rápida.
        current_app.logger.warning("Faltan SP optimizados; usando consultas compatibles")
        citas_dia = []
        for estado in ("programada", "confirmada", "cancelada", "completada", "no_asistio"):
            filas_estado = call_proc("sp_listar_citas", (estado, None, fecha, None)) or []
            citas_dia.extend(
                fila for fila in filas_estado
                if str(fila.get("fecha_cita", ""))[:10] == fecha
            )
        conteos = {}
        for estado in ("cancelada", "no_asistio"):
            filas = call_proc("sp_listar_citas", (estado, None, desde, None)) or []
            conteos[estado] = sum(
                1 for fila in filas if str(fila.get("fecha_cita", ""))[:10] >= desde
            )
    # Las reservas que siguen pendientes de pago también se muestran
    # en el panel para que administración tenga el estado completo del día.
    pendientes_pago = call_proc("sp_listar_citas", ("pendiente_pago", None, fecha, None)) or []
    citas_hoy = list(citas_dia) + [
        fila for fila in pendientes_pago
        if str(fila.get("fecha_cita", ""))[:10] == fecha
    ]
    if citas_hoy:
        pacientes, terapeutas = _mapas_enriquecimiento()
        servicios = _mapa_servicios()
        for cita in citas_hoy:
            _enriquecer_cita(cita, pacientes, terapeutas)
            _enriquecer_horario_cita(cita, servicios)
            _fmt_fecha(cita)
        citas_hoy.sort(key=lambda cita: str(cita.get("hora_cita") or ""))

    return jsonify({
        "success": True,
        "proximas_citas": citas_hoy,
        "total_canceladas": conteos.get("cancelada", 0),
        "total_no_asistidos": conteos.get("no_asistio", 0),
    })

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


@citas_bp.route("/api/citas/terapeuta/<int:terapeuta_id>/pacientes", methods=["GET"])
def listar_pacientes_de_terapeuta(terapeuta_id):
    """IDs únicos de pacientes con historial asignado al terapeuta."""
    try:
        filas = call_proc("sp_pacientes_ids_por_terapeuta", (terapeuta_id,)) or []
    except mysql.connector.Error as exc:
        if getattr(exc, "errno", None) != 1305:
            raise
        # Compatibilidad temporal hasta aplicar la migración agrupada.
        filas = []
        for estado in ("programada", "confirmada", "completada", "cancelada", "no_asistio"):
            filas.extend(
                call_proc("sp_listar_citas", (estado, None, None, terapeuta_id)) or []
            )
    paciente_ids = {
        int(fila["paciente_id"])
        for fila in filas
        if fila.get("paciente_id") is not None
    }
    return jsonify({"success": True, "paciente_ids": sorted(paciente_ids)})


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


@citas_bp.route("/api/citas/paciente/<int:paciente_id>/evaluacion-inicial", methods=["GET"])
def existe_evaluacion_inicial_paciente(paciente_id):
    """Indica si el paciente ya reservó una evaluación inicial."""
    existe = call_proc_one("sp_existe_evaluacion_inicial", (paciente_id,)) or {}
    return jsonify({"success": True, "existe": bool(existe.get("existe"))})


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
    enriquecer mediante llamadas internas a otros modulos. Lo usa notas
    para resolver el paciente_id de una cita sin pagar la cadena pesada del
    detalle enriquecido."""
    cita = call_proc_one("sp_detalle_cita", (cita_id,))
    if not cita:
        return jsonify({"error": "Cita no encontrada"}), 404
    _fmt_fecha(cita)
    return jsonify({"success": True, "cita": cita})


def _limpiar_paciente_nuevo_si_huerfano(paciente_id, creado_ahora):
    """Revierte el alta mínima si no se pudo crear la cita que la justificaba."""
    if not creado_ahora or not paciente_id:
        return
    try:
        _, status = pacientes_client.delete(f"/api/pacientes/min/{int(paciente_id)}")
        if status not in (200, 404):
            current_app.logger.warning(
                "No se pudo limpiar paciente temporal %s (HTTP %s)", paciente_id, status
            )
    except Exception as exc:
        current_app.logger.warning(
            "No se pudo limpiar paciente temporal %s: %s: %s",
            paciente_id, type(exc).__name__, exc,
        )


@citas_bp.route("/api/citas", methods=["POST"])
def crear_cita():
    data = request.get_json() or {}
    for campo in [
        "nombre", "apellido", "dni", "telefono", "medico_id", "fecha_cita",
    ]:
        if not data.get(campo):
            return jsonify({"error": f"Campo requerido: {campo}"}), 400
    metodo_pago = None
    if data.get("metodo_pago"):
        metodo_pago = str(data["metodo_pago"]).strip().lower()
        if metodo_pago not in {
            "yape", "plin", "tarjeta", "transferencia",
        }:
            return jsonify({"error": "Método de pago inválido"}), 400
    servicio_id = None
    if data.get("servicio_id"):
        servicio_id = str(data["servicio_id"]).strip()
        if not servicio_id.isdigit() or int(servicio_id) < 1:
            return jsonify({"error": "Servicio inválido"}), 400

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
        fecha_obj = datetime.strptime(data["fecha_cita"], "%Y-%m-%d").date()
        if fecha_obj < hoy_lima():
            return jsonify({"error": "La fecha no puede ser en el pasado"}), 400
    except ValueError:
        return jsonify({"error": "Formato de fecha invalido (YYYY-MM-DD)"}), 400

    try:
        hora_cita = _normalizar_hora_cita(data.get("hora_cita"))
    except ValueError:
        return jsonify({"error": "Formato de hora invalido (HH:MM)"}), 400

    # Slots ocupados del terapeuta ese dia (para validar cupo por hora).
    ocupados = []
    try:
        filas = call_proc("sp_slots_ocupados", (data["medico_id"], data["fecha_cita"]))
        for f in (filas or []):
            h = f.get("hora_cita")
            n = int(f.get("n") or 1)
            texto = _fmt_hora(h) if h is not None else ""
            if texto:
                ocupados.extend([texto] * n)
    except Exception as exc:
        current_app.logger.error(
            "[crear_cita] Error en sp_slots_ocupados: %s: %s",
            type(exc).__name__, exc,
        )
        return jsonify({"error": "No se pudo procesar la solicitud, intenta de nuevo"}), 500

    ahora = ahora_lima()
    fecha_date = fecha_obj

    # Autoasignacion si no vino hora.
    if not hora_cita:
        hora_cita = autoasignar(ocupados, fecha_date, ahora)
        if not hora_cita:
            return jsonify({"error": "No hay horarios disponibles para ese dia"}), 409

    # Validacion de slot.
    if not validar_slot(hora_cita):
        return jsonify({"error": "Horario invalido"}), 400
    # Si es hoy, no permitir slots pasados.
    if fecha_date == ahora.date():
        try:
            slot_min = int(hora_cita.split(":")[0]) * 60 + int(hora_cita.split(":")[1])
            if slot_min <= ahora.hour * 60 + ahora.minute:
                return jsonify({"error": "Ese horario ya paso"}), 400
        except Exception:
            pass
    # Verificar cupo.
    if contar_ocupados(ocupados).get(str(hora_cita)[:5], 0) >= CUPO_POR_SLOT:
        return jsonify({"error": "Ese horario esta completo"}), 409

    # No se bloquea el día completo: la disponibilidad se valida por slot.

    # El precio del terapeuta se mantiene para las sesiones habituales.
    # La evaluación inicial toma el precio publicado en el catálogo (S/ 55,
    # configurable entre S/ 50 y S/ 60).
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
    try:
        costo = float(medico.get("precio") or 0)
    except (TypeError, ValueError):
        costo = 0.0
    es_evaluacion_inicial = False
    if servicio_id is not None:
        try:
            catalogo_data, catalogo_status = pacientes_client.get("/api/servicios")
            if catalogo_status != 200:
                return jsonify({"error": "No se pudo consultar el catálogo de servicios."}), 502
            servicio = next(
                (s for s in (catalogo_data.get("servicios") or [])
                 if str(s.get("id")) == str(servicio_id)),
                None,
            )
            if not servicio:
                return jsonify({"error": "El servicio seleccionado no está disponible."}), 400
            nombre_servicio = str(servicio.get("nombre") or "").strip().casefold()
            es_evaluacion_inicial = nombre_servicio in {
                "evaluacion inicial", "evaluación inicial",
            }
            if es_evaluacion_inicial:
                costo = float(servicio.get("precio") or 55)
                if not 50 <= costo <= 60:
                    return jsonify({
                        "error": "El precio de la evaluación inicial debe estar entre S/ 50 y S/ 60."
                    }), 400
        except (TypeError, ValueError):
            return jsonify({"error": "No se pudo validar el precio del servicio."}), 400
        except Exception as exc:
            current_app.logger.error(
                "[crear_cita] No se pudo consultar el catálogo de servicios: %s: %s",
                type(exc).__name__, exc,
            )
            return jsonify({"error": "No se pudo validar el servicio seleccionado."}), 502
    anticipo = round(costo / 2, 2) if costo > 0 else 0.0

    # Resolver/crear el paciente solo al confirmar el paso 6.
    # Si se acaba de crear y la reserva pierde una carrera de concurrencia,
    # se elimina únicamente si sigue sin citas ni evaluaciones asociadas.
    paciente_creado_ahora = False
    try:
        pac_data, pac_status = pacientes_client.get(f"/api/pacientes/dni/{data['dni']}")
        if pac_status == 200:
            paciente_id = pac_data.get("id")
            paciente_existente = (pac_data or {}).get("paciente") or {}
            if paciente_existente:
                data["nombre"] = paciente_existente.get("nombre") or data["nombre"]
                data["apellido"] = paciente_existente.get("apellido") or data["apellido"]
                data["telefono"] = paciente_existente.get("telefono") or data["telefono"]
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
            paciente_creado_ahora = bool(paciente_id)
    except Exception as exc:
        current_app.logger.error(
            "[crear_cita] Error HTTP a pacientes_service (resolver/crear paciente): %s: %s",
            type(exc).__name__, exc,
        )
        return jsonify({"error": "Servicio de pacientes no disponible, intenta de nuevo"}), 502

    # Si es evaluación inicial, el procedimiento marca la reserva como única
    # para ese paciente. La restricción UNIQUE en la BD también protege
    # contra dos solicitudes simultáneas con el mismo DNI.
    if es_evaluacion_inicial:
        try:
            existente = call_proc_one(
                "sp_existe_evaluacion_inicial", (paciente_id,)
            ) or {}
        except Exception as exc:
            _limpiar_paciente_nuevo_si_huerfano(paciente_id, paciente_creado_ahora)
            current_app.logger.error(
                "[crear_cita] No se pudo verificar evaluación inicial: %s: %s",
                type(exc).__name__, exc,
            )
            return jsonify({"error": "No se pudo verificar el historial de evaluaciones."}), 500
        if existente.get("existe"):
            _limpiar_paciente_nuevo_si_huerfano(paciente_id, paciente_creado_ahora)
            return jsonify({
                "error": "Este DNI ya tiene una evaluación inicial registrada. Puedes elegir una sesión de tratamiento."
            }), 409
        # Tambien se consideran evaluaciones clinicas ya registradas en
        # pacientes_service, aunque sean anteriores a esta nueva reserva.
        try:
            evaluaciones_data, evaluaciones_status = pacientes_client.get(
                f"/api/pacientes/{paciente_id}/evaluaciones"
            )
        except Exception as exc:
            _limpiar_paciente_nuevo_si_huerfano(paciente_id, paciente_creado_ahora)
            current_app.logger.warning(
                "[crear_cita] No se pudo consultar evaluaciones del paciente %s: %s",
                paciente_id, exc,
            )
            return jsonify({"error": "No se pudo verificar el historial de evaluaciones."}), 502
        if evaluaciones_status != 200:
            _limpiar_paciente_nuevo_si_huerfano(paciente_id, paciente_creado_ahora)
            return jsonify({"error": "No se pudo verificar el historial de evaluaciones."}), 502
        if (evaluaciones_data or {}).get("evaluaciones"):
            _limpiar_paciente_nuevo_si_huerfano(paciente_id, paciente_creado_ahora)
            return jsonify({
                "error": "Este DNI ya tiene una evaluación inicial registrada. Puedes elegir una sesión de tratamiento."
            }), 409

    # Si hay anticipo, la cita queda oculta como pendiente de pago hasta
    # que la pasarela confirme. Así no aparece en la agenda ni en reportes
    # antes de completar el proceso.
    requiere_pago = bool(metodo_pago and anticipo > 0)
    if es_evaluacion_inicial:
        procedimiento_creacion = (
            "sp_crear_cita_evaluacion_pendiente_pago"
            if requiere_pago else "sp_crear_cita_evaluacion"
        )
    else:
        procedimiento_creacion = "sp_crear_cita_pendiente_pago" if requiere_pago else "sp_crear_cita"
    try:
        cita = call_proc_one(
            procedimiento_creacion,
            (paciente_id, data["medico_id"], servicio_id, data["fecha_cita"], hora_cita),
            commit=True,
        )
    except mysql.connector.Error as exc:
        # La restricción uq_reserva es la última barrera contra dos reservas
        # simultáneas del mismo terapeuta, fecha y hora. Puede activarse
        # aunque la consulta previa de disponibilidad haya mostrado el slot libre.
        if getattr(exc, "errno", None) == 1062:
            _limpiar_paciente_nuevo_si_huerfano(paciente_id, paciente_creado_ahora)
            if (
                es_evaluacion_inicial
                and "uq_evaluacion_inicial_paciente" in str(exc)
            ):
                return jsonify({
                    "error": "Este DNI ya tiene una evaluación inicial registrada. Puedes elegir una sesión de tratamiento."
                }), 409
            current_app.logger.info(
                "[crear_cita] Conflicto de reserva concurrente: terapeuta=%s fecha=%s hora=%s",
                data["medico_id"], data["fecha_cita"], hora_cita,
            )
            return jsonify({
                "error": "Ese horario acaba de ser reservado por otra persona. "
                         "Selecciona otra hora disponible e inténtalo nuevamente."
            }), 409
        _limpiar_paciente_nuevo_si_huerfano(paciente_id, paciente_creado_ahora)
        current_app.logger.error(
            "[crear_cita] Error en BD (%s): %s: %s",
            procedimiento_creacion, type(exc).__name__, exc,
        )
        return jsonify({"error": "No se pudo procesar la solicitud, intenta de nuevo"}), 500
    except Exception as exc:
        _limpiar_paciente_nuevo_si_huerfano(paciente_id, paciente_creado_ahora)
        current_app.logger.error(
            "[crear_cita] Error inesperado en sp_crear_cita: %s: %s",
            type(exc).__name__, exc,
        )
        return jsonify({"error": "No se pudo procesar la solicitud, intenta de nuevo"}), 500
    cita_id = cita["id"] if cita else None
    if not cita_id:
        _limpiar_paciente_nuevo_si_huerfano(paciente_id, paciente_creado_ahora)
        return jsonify({
            "error": "No se pudo confirmar la reserva. Verifica la disponibilidad e inténtalo nuevamente."
        }), 500

    log_accion(
        accion="crear_cita",
        tabla_afectada="historial_citas",
        registro_id=cita_id,
        detalle=f"Cita creada para paciente_id={paciente_id}, medico_id={data['medico_id']}, fecha={data['fecha_cita']}, hora={hora_cita or 'sin hora'}",
        ip_origen=request.remote_addr,
        entidad_tipo="paciente",
        entidad_id=paciente_id,
        entidad_nombre=(" ".join(x for x in (data.get("nombre"), data.get("apellido")) if x).strip() or None),
    )

    if cita_id and requiere_pago:
        # Si no se puede crear el pago, liberar la reserva pendiente.
        try:
            pago_data, pago_status = pagos_client.post("/api/pagos/anticipo", {
                "cita_id": cita_id,
                "paciente_id": paciente_id,
                "monto": anticipo,
                "metodo_pago": metodo_pago,
            })
            if (
                pago_status not in (200, 201)
                or not pago_data
                or not pago_data.get("success")
                or pago_data.get("id") is None
            ):
                raise RuntimeError(
                    "pagos_service no creo el anticipo (status %s): %s"
                    % (pago_status, pago_data)
                )
        except Exception as exc:
            current_app.logger.warning(
                "[crear_cita] No se pudo iniciar el pago para la cita %s: %s: %s",
                cita_id, type(exc).__name__, exc,
            )
            try:
                call_proc_execute("sp_cancelar_cita_pago_vencido", (cita_id,))
            except Exception as cancelar_exc:
                current_app.logger.error(
                    "[crear_cita] No se pudo liberar la cita pendiente %s: %s",
                    cita_id, cancelar_exc,
                )
            return jsonify({
                "success": False,
                "error": "No se pudo iniciar el pago. La reserva no quedó confirmada; vuelve a intentarlo.",
            }), 502

    return jsonify({
        "success": True, "cita_id": cita_id,
        "costo": costo, "anticipo": anticipo,
    }), 201


# ------------------------------------------------------------------
# Aviso al terapeuta cuando cambia o se cancela una cita.
#
# Regla principal: el aviso NUNCA puede tumbar el DELETE/PUT de la
# cita. Sin telefono, servicio caido o SMS rechazado se convierte en
# un registro de auditoria con el motivo, y se sigue adelante.
# ------------------------------------------------------------------


def _leer_cita_local(cita_id):
    """Fila de la cita ANTES de tocarla.

    sp_modificar_cita sobrescribe terapeuta_id, asi que para avisar
    al terapeuta que PIERDE la cita hay que leerla antes del UPDATE.
    Devuelve {} ante cualquier fallo: sin fila no se avisa, pero la
    cancelacion/reprogramacion sigue su curso.
    """
    try:
        return call_proc_one("sp_detalle_cita", (cita_id,)) or {}
    except Exception:
        return {}


def _telefono_terapeuta(terapeuta_id, timeout=5):
    """Telefono del terapeuta, mediante llamadas internas (sin consultas
    cruzadas a moovacloud_auth):

        terapeuta_id -> usuario_id   mediante el modulo de pacientes
        usuario_id   -> telefono     mediante el modulo de autenticacion

    Devuelve None si no hay telefono o si cualquier salto falla."""
    try:
        te = _mapa_terapeutas(timeout=timeout).get(terapeuta_id) or {}
        usuario_id = te.get("usuario_id")
        if not usuario_id:
            return None
        data, _status = auth_client.get("/api/auth/usuarios", timeout=timeout)
        for u in (data.get("usuarios") or []):
            if u.get("id") == usuario_id:
                telefono = (u.get("telefono") or "").strip()
                return telefono or None
        return None
    except Exception:
        return None


def _nombre_pila_paciente(paciente_id, timeout=5):
    """Solo el nombre de pila: es lo unico del paciente que se pone
    en el SMS (sin DNI ni telefono)."""
    try:
        p = _mapa_pacientes(timeout=timeout).get(paciente_id) or {}
        return ((p.get("nombre") or "").strip() or None)
    except Exception:
        return None


def _mensaje_aviso(verbo, fecha_txt, hora_txt, nombre_pila):
    """Compone el SMS del aviso.

    ASCII obligatorio (sin tildes) porque el proveedor SMS no maneja
    bien UTF-8, igual que en OTP y recordatorios. Nunca lleva DNI ni
    telefono del paciente; a lo sumo el nombre de pila.
    Ej: "MOOVA Clinic: Se libero tu cita del 25/10 a las 10:00 (paciente Ana)."
    """
    partes = [f"MOOVA Clinic: {verbo}"]
    if fecha_txt:
        partes.append(f" del {fecha_txt}")
    if hora_txt:
        partes.append(f" a las {hora_txt[:5]}")
    if nombre_pila:
        partes.append(f" (paciente {nombre_pila})")
    return "".join(partes) + "."


def _fecha_txt(fecha):
    if hasattr(fecha, "strftime"):
        return fecha.strftime("%d/%m")
    return str(fecha)[:10] if fecha else None


def _avisar_terapeuta(terapeuta_id, verbo, fecha_txt, hora_txt,
                      nombre_pila, motivo, cita_id):
    """Envia el SMS de aviso al terapeuta.

    NUNCA lanza excepcion. Devuelve True solo si el SMS salio bien;
    todo lo demas (sin telefono, SMS rechazado, error) queda registrado
    en auditoria con `motivo` para poder responder despues a "por que
    no le llego el aviso al doctor".
    """
    estado = "error"
    texto = ""
    try:
        texto = _mensaje_aviso(verbo, fecha_txt, hora_txt, nombre_pila)
        telefono = _telefono_terapeuta(terapeuta_id)
        if not telefono:
            estado = "sin_telefono"
        elif _enviar_sms(telefono, texto):
            estado = "enviado"
        else:
            estado = "sms_fallido"
    except Exception as exc:
        current_app.logger.error(
            "[aviso] %s: %s: %s", motivo, type(exc).__name__, exc,
        )

    log_accion(
        usuario_id=None,
        accion="avisar_terapeuta",
        tabla_afectada="historial_citas",
        registro_id=cita_id,
        detalle=f"{motivo} terapeuta_id={terapeuta_id} estado={estado}",
        ip_origen=request.remote_addr,
        entidad_tipo="medico",
        entidad_id=terapeuta_id,
    )
    return estado == "enviado"


def _avisar_cita_liberada(cita_id, previa, motivo):
    """Un terapeuta se queda sin cita: se lo avisamos."""
    if not previa or not previa.get("terapeuta_id"):
        return False
    try:
        nombre = _nombre_pila_paciente(previa.get("paciente_id"))
        return _avisar_terapeuta(
            previa.get("terapeuta_id"),
            "Se libero tu cita",
            _fecha_txt(previa.get("fecha_cita")),
            _fmt_hora(previa.get("hora_cita")),
            nombre, motivo, cita_id,
        )
    except Exception:
        return False


def _avisar_cambio_cita(cita_id, previa, fecha_nueva, medico_nuevo, hora_nueva):
    """Avisa SOLO si cambio algo que le afecta al terapeuta: fecha, hora
    o terapeuta. Si el cambio no toco ninguno de los tres, no se manda
    ningun SMS.

    - Cambio de terapeuta: 2 avisos (al que pierde la cita y al que
      la recibe).
    - Solo cambio de fecha u hora: 1 aviso con la nueva fecha/hora.
    """
    if not previa:
        return

    try:
        medico_viejo = previa.get("terapeuta_id")
        fecha_vieja = previa.get("fecha_cita")
        hora_vieja = _fmt_hora(previa.get("hora_cita"))
        try:
            medico_nuevo_int = int(medico_nuevo)
        except (TypeError, ValueError):
            medico_nuevo_int = None

        cambio_medico = (
            medico_viejo is not None and medico_nuevo_int is not None
            and int(medico_viejo) != medico_nuevo_int
        )
        cambio_fecha = fecha_vieja != fecha_nueva
        cambio_hora = (hora_vieja or None) != (hora_nueva or None)

        if not (cambio_medico or cambio_fecha or cambio_hora):
            # Cambio de descripcion u otro campo: sin SMS.
            return

        nombre = _nombre_pila_paciente(previa.get("paciente_id"))
        hora_final = hora_nueva or hora_vieja

        if cambio_medico:
            # El que pierde se entera con la cita que se libero (fecha
            # vieja); el que la recibe, con la nueva.
            _avisar_terapeuta(
                medico_viejo, "Se libero tu cita",
                _fecha_txt(fecha_vieja), hora_vieja,
                nombre, "cita_liberada", cita_id,
            )
            _avisar_terapeuta(
                medico_nuevo_int, "Te asignaron una cita",
                _fecha_txt(fecha_nueva), hora_final,
                nombre, "cita_asignada", cita_id,
            )
        else:
            _avisar_terapeuta(
                medico_nuevo_int, "Tu cita quedo en",
                _fecha_txt(fecha_nueva), hora_final,
                nombre, "cita_reprogramada", cita_id,
            )
    except Exception as exc:
        # Cinta adhesiva: ningun fallo de composicion debe romper el PUT.
        current_app.logger.error(
            "[aviso] cita %s: %s: %s", cita_id, type(exc).__name__, exc,
        )


@citas_bp.route("/api/citas/<int:cita_id>", methods=["PUT"])
def modificar_cita(cita_id):
    data = request.get_json() or {}
    nueva_fecha = data.get("fecha_cita", "")
    nuevo_medico = data.get("medico_id", "")
    if not nueva_fecha or not nuevo_medico:
        return jsonify({"error": "Se requieren fecha_cita y medico_id"}), 400
    try:
        fecha_obj = datetime.strptime(nueva_fecha, "%Y-%m-%d").date()
        if fecha_obj < hoy_lima():
            return jsonify({"error": "La fecha no puede ser en el pasado"}), 400
    except ValueError:
        return jsonify({"error": "Formato invalido"}), 400
    try:
        hora_cita = _normalizar_hora_cita(data.get("hora_cita"))
    except ValueError:
        return jsonify({"error": "Formato de hora invalido (HH:MM)"}), 400

    # Slots ocupados excluyendo la propia cita.
    ocupados = []
    try:
        filas = call_proc("sp_slots_ocupados", (nuevo_medico, nueva_fecha))
        for f in (filas or []):
            h = f.get("hora_cita")
            n = int(f.get("n") or 1)
            texto = _fmt_hora(h) if h is not None else ""
            if texto:
                ocupados.extend([texto] * n)
    except Exception:
        pass
    # excluir la cita actual
    try:
        cita_actual = call_proc_one("sp_detalle_cita", (cita_id,))
        if cita_actual and cita_actual.get("hora_cita") is not None:
            h = _fmt_hora(cita_actual.get("hora_cita"))
            if h in ocupados:
                ocupados.remove(h)
    except Exception:
        pass

    if hora_cita:
        if not validar_slot(hora_cita):
            return jsonify({"error": "Horario invalido"}), 400
        from datetime import datetime as _dt
        fecha_date = _dt.strptime(nueva_fecha, "%Y-%m-%d").date()
        ahora = ahora_lima()
        if fecha_date == ahora.date():
            slot_min = int(hora_cita.split(":")[0]) * 60 + int(hora_cita.split(":")[1])
            if slot_min <= ahora.hour * 60 + ahora.minute:
                return jsonify({"error": "Ese horario ya paso"}), 400
        if contar_ocupados(ocupados).get(str(hora_cita)[:5], 0) >= CUPO_POR_SLOT:
            return jsonify({"error": "Ese horario esta completo"}), 409
    else:
        hora_cita = autoasignar(ocupados, _dt.strptime(nueva_fecha, "%Y-%m-%d").date(), ahora_lima())
        if not hora_cita:
            return jsonify({"error": "No hay horarios disponibles para ese dia"}), 409

    # Se permite más de una cita por día; el control es por hora/slot.

    # ANTES del UPDATE: sp_modificar_cita sobrescribe terapeuta_id y
    # el aviso necesita saber quien se queda sin la cita.
    previa = _leer_cita_local(cita_id)

    result = call_proc_one("sp_modificar_cita", (cita_id, nueva_fecha, nuevo_medico, hora_cita), commit=True)
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

    # Aviso al terapeuta: solo si cambio fecha, hora o terapeuta.
    # Internamente nunca lanza, asi que el PUT responde igual.
    _avisar_cambio_cita(cita_id, previa, fecha_obj, nuevo_medico, hora_cita)

    return jsonify({"success": True})


@citas_bp.route("/api/citas/<int:cita_id>", methods=["DELETE"])
def cancelar_cita(cita_id):
    # ANTES de cancelar: sp_cancelar_cita no devuelve terapeuta_id ni
    # fecha, y el aviso necesita los dos.
    previa = _leer_cita_local(cita_id)

    result = call_proc_one("sp_cancelar_cita", (cita_id,), commit=True)
    if not result or int(result.get("actualizadas") or 0) == 0:
        return jsonify({"error": "Cita no encontrada"}), 404

    # Cancelar el pago pendiente mediante una llamada interna al modulo
    # de pagos (antes se hacia dentro de sp_cancelar_cita, CROSS-DB).
    try:
        pagos_client.post(f"/api/pagos/{cita_id}/cancelar", {})
    except Exception as exc:
        # La cancelacion de la cita ya quedo hecha en la base propia.
        # Lo que se pierde es el cierre del pago pendiente, y eso se
        # recupera con scripts/liberar_pagos_vencidos.py.
        current_app.logger.warning(
            "No se pudo cancelar el pago pendiente de la cita %s: %s: %s",
            cita_id, type(exc).__name__, exc,
        )

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

    # Aviso al terapeuta de que se libero su espacio. Nunca lanza, el
    # DELETE responde igual aunque falle (sin telefono, SMS caido, ...).
    _avisar_cita_liberada(cita_id, previa, "cita_cancelada")

    return jsonify({"success": True})


@citas_bp.route(
    "/api/citas/<int:cita_id>/cancelar-pago-vencido", methods=["POST"]
)
def cancelar_cita_pago_vencido(cita_id):
    result = call_proc_one("sp_cancelar_cita_pago_vencido", (cita_id,), commit=True)
    cancelada = bool(result and int(result.get("actualizadas") or 0) > 0)
    if cancelada:
        log_accion(
            accion="cancelar_cita",
            tabla_afectada="historial_citas",
            registro_id=cita_id,
            detalle="Cita cancelada por pago vencido",
            ip_origen=request.remote_addr,
        )
    return jsonify({"success": True, "cancelada": cancelada})


@citas_bp.route("/api/citas/<int:cita_id>/confirmar-pago", methods=["POST"])
def confirmar_cita_pago(cita_id):
    """Activa una reserva pendiente solo después de confirmar su pago."""
    try:
        resultado = call_proc_one("sp_confirmar_cita_pago", (cita_id,), commit=True)
    except Exception as exc:
        current_app.logger.error("No se pudo activar la cita %s tras el pago: %s", cita_id, exc)
        return jsonify({"success": False, "error": "No se pudo activar la cita."}), 500
    if resultado and int(resultado.get("actualizadas") or 0) > 0:
        return jsonify({"success": True})
    cita = call_proc_one("sp_detalle_cita", (cita_id,))
    if cita and cita.get("estado") in ("programada", "confirmada"):
        return jsonify({"success": True, "ya_confirmada": True})
    return jsonify({"success": False, "error": "La reserva no está pendiente de pago."}), 409


@citas_bp.route("/api/citas/<int:cita_id>/descripcion", methods=["PUT"])
def actualizar_descripcion_cita(cita_id):
    """Guarda un borrador de notas sin cambiar el estado de la cita."""
    data = request.get_json() or {}
    descripcion = (data.get("descripcion") or "").strip()
    call_proc_execute("sp_actualizar_descripcion_cita", (cita_id, descripcion))
    return jsonify({"success": True, "guardada": True})


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


@citas_bp.route("/api/citas/<int:cita_id>/no-asistio", methods=["POST"])
def marcar_no_asistio(cita_id):
    result = call_proc_one("sp_marcar_no_asistio", (cita_id,), commit=True)
    actualizadas = int((result or {}).get("actualizadas") or 0)
    if actualizadas > 0:
        ent_paciente_id, ent_paciente_nombre = _datos_paciente_cita(cita_id)
        log_accion(
            accion="marcar_inasistencia",
            tabla_afectada="historial_citas",
            registro_id=cita_id,
            detalle="Cita marcada como no asistida",
            ip_origen=request.remote_addr,
            entidad_tipo="paciente",
            entidad_id=ent_paciente_id,
            entidad_nombre=ent_paciente_nombre,
        )
    if actualizadas == 0:
        return jsonify({"success": False, "error": "No se pudo marcar la inasistencia."}), 409
    return jsonify({"success": True})



@citas_bp.route("/api/citas/otp/solicitar", methods=["POST"])
def solicitar_otp():
    data = request.get_json() or {}
    dni = data.get("dni", "").strip()
    accion = data.get("accion", "modificar")

    if not dni or len(dni) != 8 or not dni.isdigit():
        return jsonify({"error": "DNI invalido"}), 400

    if accion not in ("agendar", "modificar", "cancelar", "tratamiento", "consultar"):
        return jsonify({"error": "Acción OTP inválida"}), 400

    # En agendamiento, el teléfono registrado es la única fuente válida
    # cuando el paciente existe. Para DNI nuevos se valida el teléfono
    # ingresado usando el validador compartido.
    if accion == "agendar":
        pac_data, pac_status = pacientes_client.get(f"/api/pacientes/{dni}")
        paciente = (pac_data or {}).get("paciente") or {}
        if pac_status == 200 and paciente:
            telefono_destino = str(paciente.get("telefono") or "").strip()
        elif pac_status == 404 or (pac_status == 200 and not paciente):
            telefono_destino = str(data.get("telefono") or "").strip()
            error_telefono = validar_telefono(telefono_destino)
            if error_telefono:
                return jsonify({"error": error_telefono}), 400
            telefono_destino = normalizar_telefono(telefono_destino)
        else:
            return jsonify({"error": "No se pudo consultar el registro del paciente."}), 502
        if not telefono_destino:
            return jsonify({"error": "El paciente no tiene un teléfono registrado."}), 400
    else:
        pac_data, pac_status = pacientes_client.get(f"/api/pacientes/{dni}")
        if pac_status != 200:
            return jsonify({"error": "No se encontraron citas programadas para ese DNI."}), 404
        paciente = (pac_data or {}).get("paciente") or {}
        if not paciente:
            return jsonify({"error": "No se encontraron citas programadas para ese DNI."}), 404
        telefono_destino = str(paciente.get("telefono") or "").strip()

    if accion in ("tratamiento", "consultar"):
        # Continuar tratamiento tambien debe estar disponible para pacientes
        # que ya tienen citas registradas pero aun no cuentan con un paquete
        # de sesiones. La pantalla mostrara su historial y un cronograma
        # propuesto (sin presentarlo como citas ya confirmadas).
        paquetes_paciente = []
        try:
            paq_data, _ = pagos_client.get(f"/api/pagos/pacientes/{paciente['id']}/paquetes")
            paquetes_paciente = (paq_data or {}).get("paquetes") or []
            tiene_paquete_activo = any(
                p.get("estado") == "activo"
                and int(p.get("sesiones_usadas") or 0) < int(p.get("total_sesiones") or 0)
                for p in paquetes_paciente
            )
        except Exception:
            tiene_paquete_activo = False
        try:
            citas_paciente = call_proc("sp_listar_citas_paciente", (paciente["id"],)) or []
        except Exception:
            citas_paciente = []
        try:
            eval_data, eval_status = pacientes_client.get(
                f"/api/pacientes/{paciente['id']}/evaluaciones"
            )
            evaluaciones = (eval_data or {}).get("evaluaciones") or [] if eval_status == 200 else []
        except Exception:
            evaluaciones = []
        tiene_historial = bool(paquetes_paciente or citas_paciente or evaluaciones)
        if accion == "tratamiento" and not (
            tiene_paquete_activo or citas_paciente or evaluaciones
        ):
            return jsonify({
                "error": "No encontramos citas, evaluaciones ni tratamientos asociados a ese DNI."
            }), 404
        if accion == "consultar" and not tiene_historial:
            return jsonify({
                "error": "No encontramos citas ni tratamientos asociados a ese DNI."
            }), 404
    elif accion != "agendar":
        if not call_proc_one("sp_existe_cita_programada_paciente", (paciente["id"],)):
            return jsonify({"error": "No se encontraron citas programadas para ese DNI."}), 404

    codigo = str(secrets.randbelow(900000) + 100000)
    # Reloj de duracion y no de calendario: lo escribe y lo lee este
    # mismo servidor, asi que "ahora" aqui y "ahora" en verificar_otp
    # son el mismo reloj y el OTP caduca a los N minutos pase el dia
    # que pase. Por eso NO pasa por hoy_lima().
    expira = datetime.now() + timedelta(minutes=OTP_EXPIRA_MIN)

    call_proc_execute("sp_invalidar_otps_previos", (dni, accion))
    call_proc_execute("sp_insertar_otp", (dni, codigo, accion, expira))

    verbo = {
        "agendar": "confirmar tu reserva",
        "modificar": "modificar tu cita",
        "cancelar": "cancelar tu cita",
        "tratamiento": "continuar tu tratamiento",
        "consultar": "consultar tu historial de citas",
    }.get(accion, "continuar tu tratamiento")
    mensaje = f"MOOVA Clinic: Tu codigo para {verbo} es {codigo}. Valido por {OTP_EXPIRA_MIN} min."
    enviado = _enviar_sms(telefono_destino, mensaje)

    if not enviado:
        return jsonify({"error": "No se pudo enviar el SMS."}), 500

    tel = telefono_destino.strip()
    tel_mask = tel[:3] + "***" + tel[-3:] if len(tel) >= 6 else "***"
    return jsonify({"success": True, "tel_mask": tel_mask})


@citas_bp.route("/api/citas/otp/verificar", methods=["POST"])
def verificar_otp():
    data = request.get_json() or {}
    dni = data.get("dni", "").strip()
    codigo = data.get("otp", "").strip()
    accion = data.get("accion", "modificar")
    if not dni or len(dni) != 8 or not dni.isdigit() or accion not in (
        "agendar", "modificar", "cancelar", "tratamiento", "consultar"
    ):
        return jsonify({"resultado": "no_existe"}), 400

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
        except Exception as exc:
            current_app.logger.warning(
                "No se pudieron calcular las estadisticas de recuperados: %s: %s",
                type(exc).__name__, exc,
            )
        try:
            esp_data, _ = pacientes_client.get("/api/estadisticas/especialistas")
            especialistas = int(esp_data.get("total") or 0) if esp_data else 0
        except Exception as exc:
            current_app.logger.warning(
                "No se pudo pedir el total de especialistas a pacientes_service: %s: %s",
                type(exc).__name__, exc,
            )
        try:
            cfg_data, _ = pagos_client.get("/api/pagos/configuracion/anio")
            cfg = cfg_data.get("valor") if cfg_data else None
            if cfg:
                anio_inicio = int(cfg)
        except Exception as exc:
            current_app.logger.warning(
                "No se pudo leer el anio de inicio de la configuracion de pagos: %s: %s",
                type(exc).__name__, exc,
            )
        # El anio se cuenta en Lima, igual que el resto de "hoy": en
        # UTC el cambio de anio llegaria cinco horas tarde.
        total_anios = hoy_lima().year - anio_inicio
        try:
            op_data, _ = pacientes_client.get("/api/estadisticas/opiniones")
            if op_data:
                total = int(op_data.get("total") or 0)
                buenas = int(op_data.get("buenas") or 0)
                if total > 0:
                    tasa_exito = round((buenas / total) * 100)
        except Exception as exc:
            current_app.logger.warning(
                "No se pudo calcular la tasa de exito con las opiniones: %s: %s",
                type(exc).__name__, exc,
            )
    except Exception as exc:
        # Cada bloque ya aviso de lo suyo; esto es por si algo mas
        # revienta por el medio y el dashboard devolviera ceros sin mas.
        current_app.logger.warning(
            "Las estadisticas del dashboard se devuelven con valores por defecto: %s: %s",
            type(exc).__name__, exc,
        )
    return jsonify({
        "pacientes_recuperados": recuperados,
        "especialistas": especialistas,
        "anios_experiencia": total_anios,
        "tasa_exito": tasa_exito,
    })


# ------------------------------------------------------------------
# Recordatorios automaticos por SMS (sustentacion)
#
# La tarde anterior se envia un aviso a los pacientes que tienen
# cita al dia siguiente. Usa la columna historial_citas
# .recordatorio_enviado, que hasta ahora no usaba nadie.
# ------------------------------------------------------------------


def _mensaje_recordatorio(fecha_cita, hora_cita, terapeuta):
    """Corto y en ASCII (sin tildes), igual que el mensaje de OTP:
    el proveedor SMS se lleva mal con caracteres UTF-8."""
    partes = "MOOVA Clinic: Recordatorio. Tienes cita"
    if fecha_cita:
        if hasattr(fecha_cita, "strftime"):
            fecha_txt = fecha_cita.strftime("%d/%m")
        else:
            fecha_txt = str(fecha_cita)[:10]
        partes += f" el {fecha_txt}"
    hora_txt = _fmt_hora(hora_cita)
    if isinstance(hora_txt, str) and hora_txt.strip():
        # _fmt_hora devuelve HH:MM:SS; al SMS va HH:MM.
        partes += f" a las {hora_txt[:5]}"
    if terapeuta:
        partes += f" con {terapeuta}"
    partes += ". Si no puedes asistir, reprograma o cancela con anticipacion."
    return partes


def enviar_recordatorios(fecha=None):
    """Envia SMS de recordatorio para las citas del dia siguiente
    (por defecto) o de la fecha indicada.

    Recorrido por cita, para que dos procesos jamas manden el mismo
    SMS (el scheduler de APScheduler y el endpoint manual pueden
    correr a la vez):
      1. sp_citas_pendientes_recordatorio: las citas de ese dia que
         no recibieron aviso (estado programada/confirmada).
      2. sp_marcar_recordatorio_enviado: RECLAMA cada cita. Si otro
         proceso gano la carrera, marcadas=0 y esta cita se salta.
      3. Si el paciente no tiene telefono, o el SMS falla, se
         DESMARCA con sp_desmarcar_recordatorio para que el
         siguiente ciclo reintente.

    Resumen devuelto: total = pendientes encontradas; enviados +
    fallidos + sin_telefono = las que este proceso llego a reclamar.
    """
    if fecha is None:
        fecha = hoy_lima() + timedelta(days=1)

    pendientes = call_proc("sp_citas_pendientes_recordatorio", (fecha,)) or []
    pacientes, terapeutas = _mapas_enriquecimiento()

    total = len(pendientes)
    enviados = fallidos = sin_telefono = 0

    for cita in pendientes:
        cita_id = cita.get("id")
        reclamo = call_proc_one("sp_marcar_recordatorio_enviado", (cita_id,), commit=True)
        marcadas = int(reclamo.get("marcadas") or 0) if reclamo else 0
        if marcadas != 1:
            # Otro proceso la reclamo primero: no es nuestra.
            continue

        paciente = pacientes.get(cita.get("paciente_id")) or {}
        telefono = (paciente.get("telefono") or "").strip()
        terapeuta = (
            terapeutas.get(cita.get("terapeuta_id")) or {}
        ).get("Nombre") or ""

        if not telefono:
            call_proc_execute("sp_desmarcar_recordatorio", (cita_id,))
            sin_telefono += 1
            continue

        nombre = (
            f"{paciente.get('nombre') or ''} "
            f"{paciente.get('apellido') or ''}"
        ).strip() or telefono
        mensaje = _mensaje_recordatorio(
            cita.get("fecha_cita"), cita.get("hora_cita"), terapeuta
        )

        if _enviar_sms(telefono, mensaje):
            enviados += 1
            current_app.logger.info(
                "[recordatorios] SMS enviado a %s (cita %s)", nombre, cita_id
            )
        else:
            call_proc_execute("sp_desmarcar_recordatorio", (cita_id,))
            fallidos += 1
            current_app.logger.error(
                "[recordatorios] SMS fallo para %s (cita %s)", nombre, cita_id
            )

    resumen = {
        "fecha": str(fecha),
        "total": total,
        "enviados": enviados,
        "fallidos": fallidos,
        "sin_telefono": sin_telefono,
    }
    current_app.logger.info("[recordatorios] %s", resumen)
    log_accion(
        usuario_id=None,
        accion="enviar_recordatorios",
        tabla_afectada="historial_citas",
        registro_id=None,
        detalle=(
            f"fecha={fecha} total={total} enviados={enviados} "
            f"fallidos={fallidos} sin_telefono={sin_telefono}"
        ),
        ip_origen=None,
        entidad_tipo="cita",
    )
    return resumen


@citas_bp.route("/api/citas/recordatorios/enviar", methods=["POST"])
def enviar_recordatorios_endpoint():
    """Dispara el envio de recordatorios para un dia.

    El cuerpo es opcional: {"fecha": "YYYY-MM-DD"}. Sin fecha, usa
    el dia siguiente (America/Lima). Es interno: va protegido por
    la API_KEY (proteger_api_interna), no por sesion de usuario.
    """
    data = request.get_json(silent=True) or {}
    fecha_txt = str(data.get("fecha") or "").strip()

    fecha = None
    if fecha_txt:
        try:
            fecha = datetime.strptime(fecha_txt, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({
                "success": False,
                "error": "Formato de fecha invalido (YYYY-MM-DD).",
            }), 400

    resumen = enviar_recordatorios(fecha)
    return jsonify({"success": True, **resumen}), 200


# ------------------------------------------------------------------
# Reporte de pacientes en riesgo de fuga (sustentacion)
#
# El paciente dejo de venir sin avisar: nadie se entera hasta que
# se pregunta por el. Aqui se listan los que muestran senales de
# abandono para que reception pueda llamarlos.
# ------------------------------------------------------------------


def _motivo_riesgo(dias, faltas, programadas, umbral):
    """Texto corto para el panel: por que este paciente esta en riesgo."""
    motivos = []
    if programadas == 0 and dias is not None and dias >= umbral:
        motivos.append(f"Sin cita programada hace {dias} dias")
    if faltas >= 3:
        motivos.append(f"{faltas} citas perdidas")
    return "; ".join(motivos) or "Revisar"


def pacientes_en_riesgo(fecha=None, dias_umbral=None):
    """Lista los pacientes con senales de abandono.

    sp_pacientes_en_riesgo decide quien esta en riesgo usando solo
    datos de moovacloud_citas (no hay consultas cruzadas). Aqui se
    agrega el nombre y el telefono, que viven en moovacloud_pacientes
    y se consultan mediante el modulo interno de pacientes, mas el nivel de
    criticidad para ordenar la llamada de reception.

    Nivel 'alto': falto tres o mas veces, o ya paso el doble del
    umbral sin venir.
    """
    if fecha is None:
        fecha = hoy_lima()
    umbral = int(dias_umbral or RIESGO_DIAS_UMBRAL)

    filas = call_proc("sp_pacientes_en_riesgo", (fecha, umbral)) or []
    pacientes = _mapa_pacientes()

    riesgos = []
    for fila in filas:
        paciente_id = fila.get("paciente_id")
        p = pacientes.get(paciente_id) or {}
        dias = fila.get("dias_desde_ultima")
        dias = int(dias) if dias is not None else None
        faltas = int(fila.get("faltas") or 0)
        programadas = int(fila.get("citas_programadas") or 0)

        nivel = "alto" if (
            faltas >= 3 or (dias is not None and dias >= umbral * 2)
        ) else "medio"

        ultima = fila.get("ultima_cita")
        if hasattr(ultima, "strftime"):
            ultima = ultima.strftime("%Y-%m-%d")

        riesgos.append({
            "paciente_id": paciente_id,
            "nombre": (p.get("nombre") or "").strip(),
            "apellido": (p.get("apellido") or "").strip(),
            "dni": p.get("dni"),
            "telefono": p.get("telefono"),
            "ultima_cita": ultima,
            "dias_desde_ultima": dias,
            "citas_programadas": programadas,
            "completadas": int(fila.get("completadas") or 0),
            "canceladas": int(fila.get("canceladas") or 0),
            "faltas": faltas,
            "nivel": nivel,
            "motivo": _motivo_riesgo(dias, faltas, programadas, umbral),
        })

    alto = sum(1 for r in riesgos if r["nivel"] == "alto")
    current_app.logger.info(
        "[riesgo] fecha=%s umbral=%s total=%s alto=%s",
        fecha, umbral, len(riesgos), alto,
    )
    return {
        "fecha": str(fecha),
        "dias_umbral": umbral,
        "total": len(riesgos),
        "alto": alto,
        "medio": len(riesgos) - alto,
        "pacientes": riesgos,
    }


@citas_bp.route("/api/citas/riesgo", methods=["GET"])
def pacientes_en_riesgo_endpoint():
    """Reporte de pacientes con senales de abandono.

    Query opcional:
      fecha=YYYY-MM-DD   dia de referencia (default: hoy en Lima)
      dias_umbral=N      dias sin cita para marcar riesgo
                         (default: RIESGO_DIAS_UMBRAL, 30)
    """
    fecha_txt = (request.args.get("fecha") or "").strip()
    fecha = None
    if fecha_txt:
        try:
            fecha = datetime.strptime(fecha_txt, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({
                "success": False,
                "error": "Formato de fecha invalido (YYYY-MM-DD).",
            }), 400

    umbral_txt = (request.args.get("dias_umbral") or "").strip()
    umbral = None
    if umbral_txt:
        try:
            umbral = int(umbral_txt)
        except ValueError:
            return jsonify({
                "success": False,
                "error": "dias_umbral debe ser un entero.",
            }), 400
        if umbral < 1 or umbral > 365:
            return jsonify({
                "success": False,
                "error": "dias_umbral fuera de rango (1..365).",
            }), 400

    resumen = pacientes_en_riesgo(fecha, umbral)
    return jsonify({"success": True, **resumen}), 200
