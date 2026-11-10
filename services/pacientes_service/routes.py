import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from flask import current_app, jsonify, request

from services.pacientes_service import pacientes_bp
from shared.config import APIPERU_TOKEN, APIPERU_URL
from shared.proc import call_proc, call_proc_execute, call_proc_one
from shared.service_client import (
    auth_client,
    citas_client,
    pagos_client,
)
from shared.validators import validar_datos_paciente


_TERAPEUTAS_MAPA_TTL = 20.0
_TERAPEUTAS_LISTA_TTL = 15.0
_TERAPEUTAS_MAPA_CACHE = {"expires": 0.0, "data": None}
_TERAPEUTAS_LISTA_CACHE = {"expires": 0.0, "data": None}
_TERAPEUTAS_MAPA_LOCK = threading.Lock()


def _invalidar_mapa_terapeutas():
    with _TERAPEUTAS_MAPA_LOCK:
        _TERAPEUTAS_MAPA_CACHE["expires"] = 0.0
        _TERAPEUTAS_MAPA_CACHE["data"] = None
        _TERAPEUTAS_LISTA_CACHE["expires"] = 0.0
        _TERAPEUTAS_LISTA_CACHE["data"] = None


def _mapa_usuarios():
    """{usuario_id: {nombre, correo, rol, activo}} via auth_service."""
    try:
        data, _ = auth_client.get("/api/auth/usuarios")
        usuarios = data.get("usuarios") or []
        return {u["id"]: u for u in usuarios}
    except Exception:
        return {}


def _mapa_especialidades():
    especialidades = call_proc("sp_listar_especialidades") or []
    return {e["id"]: e["nombre"] for e in especialidades}


def _mapa_terapeutas(usuarios=None, especialidades=None):
    """Mapa de terapeutas con caché breve para enriquecer fichas e historiales."""
    ahora = time.monotonic()
    with _TERAPEUTAS_MAPA_LOCK:
        cache = _TERAPEUTAS_MAPA_CACHE
        if usuarios is None and especialidades is None and cache["data"] is not None and ahora < cache["expires"]:
            return cache["data"]

    usar_cache = usuarios is None and especialidades is None
    usuarios = usuarios if usuarios is not None else _mapa_usuarios()
    especialidades = especialidades if especialidades is not None else _mapa_especialidades()
    terapeutas = call_proc("sp_listar_terapeutas") or []
    mapa = {}
    for t in terapeutas:
        u = usuarios.get(t.get("usuario_id"))
        mapa[t["ID"]] = {
            "terapeuta_nombre": (u or {}).get("nombre"),
            "especialidad": especialidades.get(t.get("especialidad_id")),
            "precio": float(t["precio"]) if t.get("precio") is not None else None,
        }
    if usar_cache and mapa:
        with _TERAPEUTAS_MAPA_LOCK:
            _TERAPEUTAS_MAPA_CACHE["data"] = mapa
            _TERAPEUTAS_MAPA_CACHE["expires"] = time.monotonic() + _TERAPEUTAS_MAPA_TTL
    return mapa


# ============================================================
# Pacientes
# ============================================================

@pacientes_bp.route("/api/pacientes", methods=["GET"])
def listar_pacientes():
    pacientes = call_proc("sp_listar_pacientes")

    # Las pantallas de administración necesitan el resumen de citas.
    # Los módulos que solo enriquecen una agenda necesitan el catálogo
    # básico y no deben disparar otra consulta agregada de citas.
    incluir_resumen = request.args.get("incluir_resumen", "1").strip().lower() not in {
        "0", "false", "no",
    }
    resumen = {}
    if incluir_resumen:
        try:
            data, _ = citas_client.get("/api/citas/resumen_pacientes")
            resumen = {r["paciente_id"]: r for r in (data.get("resumen") or [])}
        except Exception as exc:
            # El listado se devuelve igual; lo que se pierde son las
            # columnas de citas por paciente.
            current_app.logger.warning(
                "No se pudo cargar el resumen de citas para el listado: %s: %s",
                type(exc).__name__, exc,
            )

    for p in pacientes:
        info = resumen.get(p["id"]) or {}
        p["total_citas"] = info.get("total", 0)
        p["ultima_cita"] = info.get("ultima")

    return jsonify({"success": True, "pacientes": pacientes})


@pacientes_bp.route("/api/pacientes/dni/<dni>", methods=["GET"])
def obtener_paciente_id_por_dni(dni):
    """Resuelve el id de un paciente segun dni. Usado por los modulos
    internos de citas y pagos (antes era un JOIN CROSS-DB)."""
    # Endpoint ligero: devuelve el registro del paciente sin cargar citas,
    # pagos ni notas. Se usa en el paso inicial de reserva por DNI.
    paciente = call_proc_one("sp_obtener_paciente_por_dni", (dni,))
    if not paciente:
        return jsonify({"error": "Paciente no encontrado"}), 404
    return jsonify({"success": True, "id": paciente["id"], "paciente": paciente})


@pacientes_bp.route("/api/pacientes/min", methods=["POST"])
def crear_paciente_min():
    """Crea un paciente con datos minimos. Usado por el modulo de citas
    cuando la reserva trae un dni que no existe aun."""
    data = request.get_json() or {}
    nombre = data.get("nombre", "").strip()
    apellido = data.get("apellido", "").strip()
    dni = data.get("dni", "").strip()
    telefono = data.get("telefono", "").strip()

    if not all([nombre, apellido, dni, telefono]):
        return jsonify({"error": "Todos los campos son requeridos."}), 400

    error = validar_datos_paciente(nombre, apellido, dni, telefono)
    if error:
        return jsonify({"error": error}), 400

    try:
        existente = call_proc_one("sp_existe_paciente_por_dni", (dni,))
        if existente:
            return jsonify({"error": "Ya existe un paciente con ese DNI.", "dni": existente["dni"]}), 409

        result = call_proc_one("sp_crear_paciente_min", (nombre, apellido, dni, telefono), commit=True)
    except Exception as exc:
        current_app.logger.error(
            "[crear_paciente_min] Error en BD (sp_crear_paciente_min): %s: %s",
            type(exc).__name__, exc,
        )
        return jsonify({"error": "No se pudo procesar la solicitud, intenta de nuevo"}), 500
    return jsonify({"success": True, "id": result["id"] if result else None}), 201


@pacientes_bp.route("/api/pacientes/min/<int:paciente_id>", methods=["DELETE"])
def eliminar_paciente_min_si_huerfano(paciente_id):
    """Limpia un alta de reserva fallida, solo si aún no tiene historial."""
    try:
        resultado = call_proc_one("sp_eliminar_paciente_si_huerfano", (paciente_id,), commit=True)
    except Exception as exc:
        current_app.logger.warning(
            "No se pudo revertir paciente temporal %s: %s: %s",
            paciente_id, type(exc).__name__, exc,
        )
        return jsonify({"error": "No se pudo verificar si el paciente puede eliminarse."}), 500
    eliminados = int((resultado or {}).get("eliminados") or 0)
    return jsonify({"success": True, "eliminado": bool(eliminados)}), 200


@pacientes_bp.route("/api/pacientes/<dni>", methods=["GET"])
def detalle_paciente(dni):
    paciente = call_proc_one("sp_obtener_paciente_por_dni", (dni,))
    if not paciente:
        return jsonify({"error": "Paciente no encontrado"}), 404

    paciente_id = paciente["id"]

    # Historial, pagos y catálogo de terapeutas son independientes.
    # Ejecutarlos en paralelo evita sumar sus latencias a la apertura de ficha.
    logger = current_app.logger

    def _cargar_historial():
        try:
            data, _ = citas_client.get(f"/api/citas/paciente/{paciente_id}")
            return data.get("citas") or []
        except Exception as exc:
            logger.warning(
                "No se pudo cargar el historial de citas del paciente %s: %s: %s",
                paciente_id, type(exc).__name__, exc,
            )
            return []

    def _cargar_pagos():
        try:
            data, _ = pagos_client.get(f"/api/pagos/pacientes/{paciente_id}")
            resultado = {}
            for pg in (data.get("pagos") or []):
                if pg.get("cita_id") not in resultado:
                    resultado[pg["cita_id"]] = pg
            return resultado
        except Exception as exc:
            logger.warning(
                "No se pudo cargar los pagos del paciente %s: %s: %s",
                paciente_id, type(exc).__name__, exc,
            )
            return {}

    with ThreadPoolExecutor(max_workers=3) as executor:
        futuro_historial = executor.submit(_cargar_historial)
        futuro_pagos = executor.submit(_cargar_pagos)
        futuro_terapeutas = executor.submit(_mapa_terapeutas)
        historial = futuro_historial.result()
        pagos = futuro_pagos.result()
        mapa = futuro_terapeutas.result()
    for c in historial:
        te = mapa.get(c.get("terapeuta_id")) or {}
        c["terapeuta"] = te.get("terapeuta_nombre")
        c["Especialidad"] = te.get("especialidad")
        pg = pagos.get(c.get("id"))
        if pg:
            c["monto"] = float(pg.get("monto") or 0)
            c["metodo_pago"] = pg.get("metodo_pago")
            c["estado_pago"] = pg.get("estado_pago")

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
    call_proc("sp_actualizar_paciente", (
        dni,
        _val("nombre"), _val("apellido"), _val("telefono"), _val("email"),
        _val("estado"), _val("fecha_nacimiento"), _val("sexo"),
        _val("direccion"), _val("seguro"), dni_nuevo,
    ), commit=True)
    return jsonify({"success": True})


def _resumen_dni(api_data):
    """Reduce la respuesta de APIPERU a lo que el flujo de reserva usa.

    APIPERU devuelve el expediente completo del titular (direccion,
    telefonos, ubigeo, fecha de nacimiento, etc). El formulario de cita
    solo autocompleta nombres y apellidos, asi que se filtra el resto
    para no exponer datos que el flujo no necesita. Se aceptan las dos
    variantes de nombre que devuelve la API (con y sin guion bajo).
    """
    anidado = api_data.get("data")
    datos = anidado if isinstance(anidado, dict) else api_data
    nombres = datos.get("nombres") or datos.get("nombre")
    paterno = datos.get("apellido_paterno") or datos.get("apellidoPaterno") or ""
    materno = datos.get("apellido_materno") or datos.get("apellidoMaterno") or ""
    return {
        "nombres": nombres or "",
        "nombre": nombres or "",
        "apellido_paterno": paterno,
        "apellido_materno": materno,
        "apellidoPaterno": paterno,
        "apellidoMaterno": materno,
    }


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
                # APIPERU devuelve el expediente completo (DNI, direccion,
                # telefonos, ubigeo, etc). El formulario de reserva solo
                # necesita nombres y apellidos, asi que se devuelve un
                # resumen: retransmitir el payload crudo exponia datos
                # que el flujo de reserva no usa.
                resumen = _resumen_dni(api_data)
                if resumen["nombres"]:
                    return jsonify({"success": True, "data": resumen})
    except Exception as exc:
        current_app.logger.error(
            "[buscar_dni] Error consultando APIPERU (dni=%s): %s: %s",
            dni, type(exc).__name__, exc,
        )

    return jsonify({"success": False, "error": "DNI no encontrado"}), 404


# ============================================================
# Servicios (catalogo)
# ============================================================

@pacientes_bp.route("/api/servicios", methods=["GET"])
def listar_servicios():
    servicios = call_proc("sp_listar_servicios")
    return jsonify({"success": True, "servicios": servicios})


# ============================================================
# Terapeutas (antes consumidos por el gateway via CROSS-DB)
# ============================================================

@pacientes_bp.route("/api/terapeutas", methods=["GET"])
def listar_terapeutas():
    ahora = time.monotonic()
    with _TERAPEUTAS_MAPA_LOCK:
        cache = _TERAPEUTAS_LISTA_CACHE
        if cache["data"] is not None and ahora < cache["expires"]:
            return jsonify({"success": True, "terapeutas": cache["data"]})

    terapeutas = call_proc("sp_listar_terapeutas") or []
    usuarios = _mapa_usuarios()
    especialidades = _mapa_especialidades()

    for t in terapeutas:
        u = usuarios.get(t.get("usuario_id")) or {}
        t["Nombre"] = u.get("nombre")
        t["Telefono"] = u.get("telefono")
        t["Especialidad"] = especialidades.get(t.get("especialidad_id"))
        t["precio"] = float(t["precio"]) if t.get("precio") is not None else None

    if terapeutas:
        with _TERAPEUTAS_MAPA_LOCK:
            _TERAPEUTAS_LISTA_CACHE["data"] = terapeutas
            _TERAPEUTAS_LISTA_CACHE["expires"] = time.monotonic() + _TERAPEUTAS_LISTA_TTL
    return jsonify({"success": True, "terapeutas": terapeutas})


@pacientes_bp.route("/api/terapeutas/<int:medico_id>", methods=["GET"])
def obtener_terapeuta(medico_id):
    terapeuta = call_proc_one("sp_obtener_terapeuta", (medico_id,))
    if not terapeuta:
        return jsonify({"error": "Terapeuta no encontrado"}), 404

    usuarios = _mapa_usuarios()
    especialidades = _mapa_especialidades()
    u = usuarios.get(terapeuta.get("usuario_id")) or {}
    terapeuta["Nombre"] = u.get("nombre")
    terapeuta["Especialidad"] = especialidades.get(terapeuta.get("especialidad_id"))
    terapeuta["precio"] = float(terapeuta["precio"]) if terapeuta.get("precio") is not None else None

    return jsonify({"success": True, "terapeuta": terapeuta})


@pacientes_bp.route("/api/terapeutas", methods=["POST"])
def crear_terapeuta():
    data = request.get_json() or {}
    usuario_id = data.get("usuario_id")
    especialidad_id = data.get("especialidad_id")
    precio = data.get("precio")

    if not usuario_id:
        return jsonify({"error": "usuario_id requerido."}), 400

    result = call_proc_one("sp_crear_terapeuta", (usuario_id, especialidad_id, precio), commit=True)
    _invalidar_mapa_terapeutas()
    return jsonify({"success": True, "id": result["id"] if result else None}), 201


@pacientes_bp.route("/api/terapeutas/<int:medico_id>/precio", methods=["PUT"])
def actualizar_precio_terapeuta(medico_id):
    data = request.get_json() or {}
    precio = data.get("precio")
    if precio is None:
        return jsonify({"error": "precio requerido."}), 400
    call_proc_execute("sp_actualizar_precio", (medico_id, precio))
    _invalidar_mapa_terapeutas()
    return jsonify({"success": True})


@pacientes_bp.route("/api/terapeutas/<int:medico_id>/especialidad", methods=["PUT"])
def actualizar_especialidad_terapeuta(medico_id):
    data = request.get_json() or {}
    especialidad_id = data.get("especialidad_id")
    if especialidad_id is None:
        return jsonify({"error": "especialidad_id requerido."}), 400
    call_proc_execute("sp_actualizar_especialidad", (medico_id, especialidad_id))
    _invalidar_mapa_terapeutas()
    return jsonify({"success": True})


@pacientes_bp.route("/api/terapeutas/<int:medico_id>/activo", methods=["PUT"])
def set_terapeuta_activo(medico_id):
    data = request.get_json() or {}
    activo = data.get("activo")
    if activo is None:
        return jsonify({"error": "activo requerido."}), 400
    call_proc_execute("sp_set_terapeuta_activo", (medico_id, 1 if activo else 0))
    _invalidar_mapa_terapeutas()
    return jsonify({"success": True})


# ============================================================
# Especialidades
# ============================================================

@pacientes_bp.route("/api/especialidades", methods=["GET"])
def listar_especialidades():
    especialidades = call_proc("sp_listar_especialidades")
    return jsonify({"success": True, "especialidades": especialidades})


@pacientes_bp.route("/api/especialidades/por-nombre/<path:nombre>", methods=["GET"])
def obtener_especialidad_id(nombre):
    if not nombre:
        return jsonify({"error": "nombre requerido"}), 400
    esp = call_proc_one("sp_obtener_especialidad_id", (nombre,))
    if not esp:
        return jsonify({"error": "Especialidad no encontrada."}), 404
    return jsonify({"success": True, "id": esp["id"]})


# ============================================================
# Estadisticas
# ============================================================

@pacientes_bp.route("/api/estadisticas/especialistas", methods=["GET"])
def estadisticas_especialistas():
    data = call_proc_one("sp_estadisticas_especialistas") or {}
    return jsonify({"success": True, "total": data.get("total", 0)})


@pacientes_bp.route("/api/estadisticas/opiniones", methods=["GET"])
def estadisticas_opiniones():
    data = call_proc_one("sp_estadisticas_opiniones") or {}
    return jsonify({"success": True, "total": data.get("total", 0), "buenas": data.get("buenas", 0)})


# ============================================================
# Paquetes de sesiones (consultas internas al modulo de pagos)
# ============================================================

@pacientes_bp.route("/api/pacientes/<int:paciente_id>/paquetes", methods=["GET"])
def listar_paquetes(paciente_id):
    data, status = pagos_client.get(f"/api/pagos/pacientes/{paciente_id}/paquetes")
    return jsonify(data), status


@pacientes_bp.route("/api/pacientes/<int:paciente_id>/paquetes", methods=["POST"])
def crear_paquete(paciente_id):
    payload = request.get_json() or {}
    data, status = pagos_client.post(f"/api/pagos/pacientes/{paciente_id}/paquetes", payload)
    return jsonify(data), status


# ============================================================
# Evaluaciones iniciales
# ============================================================

@pacientes_bp.route("/api/pacientes/<int:paciente_id>/evaluaciones", methods=["GET"])
def listar_evaluaciones(paciente_id):
    evaluaciones = call_proc("sp_listar_evaluaciones", (paciente_id,)) or []
    mapa = _mapa_terapeutas()
    for e in evaluaciones:
        e["terapeuta_nombre"] = (mapa.get(e.get("terapeuta_id")) or {}).get("terapeuta_nombre")
    return jsonify({"success": True, "evaluaciones": evaluaciones})


@pacientes_bp.route("/api/pacientes/<int:paciente_id>/evaluaciones", methods=["POST"])
def crear_evaluacion(paciente_id):
    data = request.get_json() or {}
    terapeuta_id = data.get("terapeuta_id")
    motivo_consulta = data.get("motivo_consulta", "").strip()

    if not terapeuta_id or not motivo_consulta:
        return jsonify({"error": "terapeuta_id y motivo_consulta son requeridos."}), 400

    existente = call_proc_one("sp_existe_evaluacion_paciente", (paciente_id,)) or {}
    if existente.get("existe"):
        return jsonify({
            "error": "Este paciente ya tiene una evaluación inicial registrada."
        }), 409

    result = call_proc_one("sp_crear_evaluacion", (
        paciente_id, terapeuta_id, motivo_consulta,
        data.get("escala_dolor_eva"),
        data.get("rango_movimiento"),
        data.get("objetivos_terapeuticos"),
    ), commit=True)
    eval_id = result["id"] if result else None
    return jsonify({"success": True, "evaluacion_id": eval_id}), 201


