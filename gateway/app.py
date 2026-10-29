import math
import os
import random
import sys
import threading

sys.path.insert(0, os.path.dirname(__file__))
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import yaml
from flask import (
    Flask,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_wtf.csrf import CSRFError, CSRFProtect, generate_csrf

from gateway.ficha_pdf import build_ficha_clinica_pdf
from shared.audit import log_accion
from shared.config import (
    LOGIN_BLOQUEO_MIN,
    LOGIN_MAX_INTENTOS,
    LOGIN_VENTANA_MIN,
    OTP_SESION_MIN,
    PAGOS_MODO_DEMO,
    REDES_SOCIALES,
    TRUST_PROXY,
)
from shared.fechas import fmt_fecha, hoy_lima
from shared.rate_limit import LimitadorIntentos, ip_del_request
from shared.service_client import (
    audit_client,
    auth_client,
    citas_client,
    notas_client,
    pacientes_client,
    pagos_client,
    set_internal_app,
)

csrf = CSRFProtect()


def _cargar_anexos_paciente(paciente_id):
    """Paquetes, evaluaciones iniciales y consentimientos de un paciente.

    Cada bloque es independiente: si un módulo interno falla, el resto
    de la ficha se sigue mostrando igual que antes en la vista HTML.
    """
    if not paciente_id:
        return [], [], []
    paquetes, evaluaciones, consentimientos = [], [], []
    pdata, _ = pacientes_client.get(f"/api/pacientes/{paciente_id}/paquetes")
    paquetes = pdata.get("paquetes", [])
    edata, _ = pacientes_client.get(f"/api/pacientes/{paciente_id}/evaluaciones")
    evaluaciones = edata.get("evaluaciones", [])
    cdata, _ = pacientes_client.get(f"/api/pacientes/{paciente_id}/consentimientos")
    consentimientos = cdata.get("consentimientos", [])
    return paquetes, evaluaciones, consentimientos


def _is_ajax():
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
        or "application/json" in request.headers.get("Content-Type", "")
    )


def _dni_ok(valor):
    return bool(re.fullmatch(r"\d{8}", (valor or "").strip()))


def _terapeuta_id_de_sesion():
    usuario_id = session.get("usuario_id")
    if usuario_id is None:
        return None

    data, status = pacientes_client.get("/api/terapeutas")
    if status != 200:
        abort(502, description="No se pudo verificar el terapeuta de la sesión.")
    terapeutas = data.get("terapeutas") if isinstance(data, dict) else None
    if not isinstance(terapeutas, list):
        abort(502, description="No se pudo verificar el terapeuta de la sesión.")

    for terapeuta in terapeutas:
        if str(terapeuta.get("usuario_id")) == str(usuario_id):
            return terapeuta.get("ID")
    return None


# Acciones de cliente que exigen identidad verificada por OTP antes de
# mostrar datos de salud o de mutar una cita (S1). Cada una tiene su
# propio sello en la sesion: verificar para cancelar no habilita a
# modificar, ni a tratar.
ACCIONES_OTP = ("cancelar", "modificar", "tratamiento")

# Vista a la que vuelve el usuario cuando no tiene la verificacion.
VISTA_ACCION = {
    "cancelar": "cancelar_cita_page",
    "modificar": "modificar_cita_page",
    "tratamiento": "tratamiento_page",
}


def _marcar_otp_verificado(dni, accion):
    """Anota en la sesion que `dni` supero el OTP para `accion`.

    Guarda {dni, accion, ts} por accion. El ts es el sello con el que
    despues se mide la caducidad (OTP_SESION_MIN). Solo se llama desde
    el camino de exito de /api/citas/otp/verificar.
    """
    verificaciones = dict(session.get("otp_verificado") or {})
    verificaciones[accion] = {"dni": str(dni), "ts": time.time()}
    session["otp_verificado"] = verificaciones


def _otp_vigente(dni, accion, ahora=None):
    """True si `dni` tiene verificacion OTP vigente para `accion`.

    Tres condiciones y ninguna de mas: que exista el sello, que sea del
    MISMO dni (la verificacion de un paciente no sirve para otro) y que
    no hayan pasado OTP_SESION_MIN minutos desde que se marco.
    """
    verificacion = (session.get("otp_verificado") or {}).get(accion)
    if not verificacion:
        return False
    if str(verificacion.get("dni") or "") != str(dni or ""):
        return False
    ts = verificacion.get("ts") or 0
    transcurrido = (time.time() if ahora is None else ahora) - ts
    return 0 <= transcurrido <= OTP_SESION_MIN * 60


def _dni_verificado(accion):
    """DNI verificado vigente para `accion`, o None si no lo hay.

    Es lo que usan los POST: el cuerpo solo trae un cita_id, asi que el
    dni con el que se contrasta sale de la sesion, nunca del pedido.
    """
    verificacion = (session.get("otp_verificado") or {}).get(accion)
    if not verificacion:
        return None
    dni = str(verificacion.get("dni") or "")
    if not dni or not _otp_vigente(dni, accion):
        return None
    return dni


def _cita_pertenece_al_dni(dni, cita_id):
    """True si `cita_id` figura en las citas programadas de `dni`.

    Consulta las citas de ESE dni mediante llamadas internas en proceso
    (sin consultas cruzadas a la base) para que un codigo verificado no sirva para cancelar o
    mover la cita de otro paciente pasando un id al azar. Ante cualquier
    fallo responde False: la operacion queda denegada, no abierta.
    """
    if not dni or cita_id in (None, ""):
        return False
    try:
        data, status = citas_client.get(f"/api/citas?dni={dni}&estado=programada")
        if status != 200:
            return False
        return any(str(c.get("id")) == str(cita_id) for c in (data.get("citas") or []))
    except Exception:
        return False


def _proteccion_otp(dni, accion):
    """Guardia de GET: devuelve la respuesta de proteccion (redirect al
    primer paso, o 401 si viene de la cadena AJAX) y None cuando la
    verificacion esta vigente."""
    if _otp_vigente(dni, accion):
        return None
    if _is_ajax():
        return jsonify({"error": "Verifica tu identidad para continuar."}), 401
    return redirect(url_for(VISTA_ACCION[accion]))


def _otp_negado():
    """Guardia de POST: la verificacion falta, caduco o no alcanza para
    esa cita. Siempre 403, y se llama antes de tocar al módulo interno,
    de modo que ni el PUT ni el DELETE llegan a emitirse."""
    return jsonify({
        "error": "No se pudo verificar tu identidad para esta operacion.",
    }), 403


def _tel_ok(valor):
    tel = re.sub(r"[\s\-]", "", (valor or "").strip())
    if tel.startswith("+51"):
        tel = tel[3:]
    return bool(re.fullmatch(r"\d{9}", tel))


def _nombre_ok(valor):
    return bool(re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóúÑñ ]{2,60}", (valor or "").strip()))


def _validar_datos_cita_rapida(nombre, apellido, dni, telefono):
    """Validacion de formato sin salir del gateway (milisegundos, no HTTP)."""
    if not _nombre_ok(nombre) or not _nombre_ok(apellido):
        return "Nombre/apellido inválido"
    if not _dni_ok(dni):
        return "DNI inválido, debe tener 8 dígitos"
    if not _tel_ok(telefono):
        return "Teléfono inválido, debe tener 9 dígitos"
    return None


def _paquetes_activos_dni(dni):
    """Resuelve el paciente por DNI y su listado de paquetes de sesiones.
    Devuelve (paciente, paquetes) con solo los paquetes activos que aun
    tienen sesiones disponibles (estado='activo' y sesiones_usadas < total)."""
    data, status = pacientes_client.get(f"/api/pacientes/{dni}")
    if status != 200 or not (data or {}).get("paciente"):
        return None, []
    paciente = data["paciente"]
    try:
        paq_data, _ = pacientes_client.get(f"/api/pacientes/{paciente['id']}/paquetes")
        paquetes = (paq_data or {}).get("paquetes") or []
    except Exception:
        paquetes = []
    activos = [
        p for p in paquetes
        if p.get("estado") == "activo"
        and int(p.get("sesiones_usadas") or 0) < int(p.get("total_sesiones") or 0)
    ]
    return paciente, activos


def _load_swagger():
    path = os.path.join(os.path.dirname(__file__), "..", "swagger.yaml")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


# Mensajes fijos del limite de login (S2). Nunca se reutiliza el texto
# que devuelva auth_service: el de "bloqueado" y el de "clave mala"
# tienen que ser indistinguibles entre si y no pueden depender de si el
# correo existe o no.
MENSAJE_LOGIN_BLOQUEADO = (
    "Demasiados intentos. Espera unos minutos y vuelve a intentarlo."
)
MENSAJE_LOGIN_INVALIDO = "Correo o clave incorrectos."

# Los proxies de Yape/Plin del gateway no estaban atras de ninguna
# sesion: con el id de una cita y el de un cobro pagado bastaba para
# iniciar o consultar cobros ajenos. Ahora solo se dejan pasar las
# citas cuya pagina de pago abrio esta misma sesion, y dentro de la
# vigencia de VIGENCIA_PAGO_SEG desde esa apertura.
VIGENCIA_PAGO_SEG = 2 * 60 * 60
MAX_CITAS_PAGABLES = 10
# Texto generico: no distingue entre "no existe", "no es tuya" y
# "caduco", que es lo que hace que el mensaje no sirva de sonda.
MENSAJE_PAGO_NO_PERMITIDO = "No se puede procesar el pago con estos datos."


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    if PAGOS_MODO_DEMO:
        app.logger.warning(
            "Pagos en MODO DEMOSTRACIÓN: no se cobra dinero real"
        )
    app.config["MOOVA_MONOLITH"] = True
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        raise RuntimeError("Falta la variable de entorno SECRET_KEY. Déjala en .env y vuelve a arrancar.")
    app.secret_key = secret_key
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # Solo si se usa HTTPS en producción; en localhost http queda desactivado automaticamente
    if os.getenv("FLASK_ENV") == "production":
        app.config["SESSION_COOKIE_SECURE"] = True
    csrf.init_app(app)

    from services.audit_service import audit_bp
    from services.auth_service import auth_bp
    from services.auth_service.app import bcrypt
    from services.citas_service import citas_bp
    from services.notas_service import notas_bp
    from services.pacientes_service import pacientes_bp
    from services.pagos_service import pagos_bp
    from shared.config import LIBERAR_VENCIDOS_ENABLED, RECORDATORIOS_ENABLED
    from shared.db import dominio
    from shared.service_auth import proteger_api_interna

    bcrypt.init_app(app)
    for blueprint in (
        auth_bp,
        pacientes_bp,
        citas_bp,
        pagos_bp,
        notas_bp,
        audit_bp,
    ):
        # Estas APIs se autentican con API_KEY; el navegador no envia CSRF
        # en sus llamadas internas ni en el webhook del proveedor.
        csrf.exempt(blueprint)
        app.register_blueprint(blueprint, url_prefix="/_internal")
    proteger_api_interna(app, prefijo="/_internal")
    set_internal_app(app)

    if RECORDATORIOS_ENABLED == "1" or LIBERAR_VENCIDOS_ENABLED:
        try:
            from services.citas_service.scheduler import iniciar_scheduler

            with app.app_context(), dominio("citas"):
                iniciar_scheduler(app)
        except Exception as exc:
            app.logger.error(
                "[recordatorios] no se pudo arrancar el scheduler: %s: %s",
                type(exc).__name__, exc,
            )

    # Contador de intentos de login (S2). Cada worker tiene el suyo y
    # un reinicio lo pone a cero: esta limitacion esta documentada en
    # el README.
    app.extensions["rate_limit"] = LimitadorIntentos(
        LOGIN_MAX_INTENTOS, LOGIN_VENTANA_MIN, LOGIN_BLOQUEO_MIN
    )
    app.extensions["disponibilidad_rate_limit"] = LimitadorIntentos(15, 1, 1)
    app.extensions["citas_rate_limit_ip"] = LimitadorIntentos(5, 60, 60)
    app.extensions["citas_rate_limit_dni"] = LimitadorIntentos(3, 60, 60)
    app.extensions["consultas_dni_por_ip"] = {}
    app.extensions["consultas_dni_por_ip_lock"] = threading.Lock()

    app.jinja_env.filters["fecha"] = lambda v: fmt_fecha(v)
    app.jinja_env.filters["fechahora"] = lambda v: fmt_fecha(v, con_hora=True)

    try:
        from flasgger import Swagger
        specs = _load_swagger()
        Swagger(app, template=specs) if specs else Swagger(app)
    except Exception as e:
        app.logger.error(f"No se pudo inicializar Swagger: {e!r}")

    @app.context_processor
    def inject():
        return {
            "REDES": REDES_SOCIALES,
            "csrf_raw": generate_csrf(),
            "current_user": {
                "id": session.get("usuario_id"),
                "nombre": session.get("usuario_nombre"),
                "rol": session.get("rol"),
                "es_admin": session.get("rol") == "admin",
                "es_terapeuta": session.get("rol") == "terapeuta",
            }
        }

    @app.errorhandler(CSRFError)
    def _csrf_error(e):
        if _is_ajax():
            return jsonify({"error": "Sesión expirada o token de seguridad inválido. Recarga la página e inténtalo de nuevo."}), 403
        flash("error:Tu sesión expiró o el token de seguridad no es válido. Vuelve a cargar la página e inténtalo de nuevo.")
        return redirect(request.referrer or url_for("index"))

    @app.after_request
    def _cabeceras_de_seguridad(respuesta):
        """Cabeceras de seguridad en TODA respuesta del gateway (S3).

        En un solo after_request y no en cada ruta: asi no depende de
        que alguien no se le olvide una, y cubre tambien los 404, los
        500 y las respuestas de error. `setdefault` para no pisar lo
        que una ruta ya haya fijado a proposito.
        """
        respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
        respuesta.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        respuesta.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # HSTS solo en produccion: en localhost por http, avisarle al
        # navegador que use https siempre dejaria la app inaccesible
        # en desarrollo, sin forma facil de deshacerlo.
        if os.getenv("FLASK_ENV") == "production":
            respuesta.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        return respuesta

    @app.before_request
    def _documentacion_interna():
        """Swagger (flasgger) solo para administradores (S7 e).

        flasgger monta /apidocs y /apispec_1.json sin proteger ninguna
        y el gateway no tiene before_request: cualquiera podia leer el
        plano completo de la API (54 rutas, con los endpoints de pago).
        No es un agujero de datos por si solo, pero es el mapa de la
        casa. Sin sesión de admin se manda a /login, igual que hace
        _admin_required con las rutas de gestion.
        """
        ruta = request.path
        es_docs = (
            ruta.rstrip("/") == "/apidocs"
            or ruta.startswith("/apidocs/")
            or re.match(r"^/apispec_\d+\.json$", ruta) is not None
        )
        if es_docs and not ("usuario_id" in session and session.get("rol") == "admin"):
            return redirect(url_for("login"))
        return None

    # --- Protección de rutas que requieren sesión activa ---
    def _login_required(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "usuario_id" not in session:
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return decorated_function

    def _admin_required(f):
        """Requerir sesión activa y rol admin (acceso al panel)."""
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "usuario_id" not in session or session.get("rol") != "admin":
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return decorated_function

    def _cita_pendiente_de_pago():
        """Id de la cita que esta sesion creo y sigue sin pagar, o None.

        Limpia la sesion si esa cita ya se pago o ya no existe, para que
        un id viejo no quede pegado al navegador.
        """
        cita_id = session.get("cita_pendiente_id")
        if not cita_id:
            return None
        try:
            data, status = pagos_client.get(f"/api/pagos/{cita_id}")
            pago = (data or {}).get("pago") or {}
        except Exception as exc:
            app.logger.warning("No se pudo consultar el pago de la cita %s: %s", cita_id, exc)
            return cita_id
        if status != 200 or pago.get("estado_pago") != "pendiente":
            session.pop("cita_pendiente_id", None)
            return None
        return cita_id

    def _cita_autorizada_en_sesion(cita_id, incluir_pagada=False):
        """Acceso de PACIENTES (sin cuenta) a /pago y /retorno.

        Se permite si hay un usuario logueado (personal) o si la cita es
        la que ESTA sesion acaba de crear (cita_pendiente_id) o de pagar
        (cita_recien_pagada, solo para /retorno). Asi un anonimo no puede
        abrir el pago de la cita de otra persona cambiando el id.
        """
        if not cita_id or not str(cita_id).isdigit():
            return False
        if "usuario_id" in session:
            return True
        claves = ["cita_pendiente_id"]
        if incluir_pagada:
            claves.append("cita_recien_pagada")
        return any(
            session.get(k) is not None and str(session.get(k)) == str(cita_id)
            for k in claves
        )

    # ---- Citas que ESTA sesion tiene habilitadas para pagar (S7) ----

    def _registrar_cita_pagable(cita_id):
        """Anota en la sesion que se acaba de abrir /pago para esa cita.

        Se llama desde pago_page: es el unico punto por el que un
        navegador llega al formulario de pago, de ahi sale la lista de
        lo que los proxies de abajo van a dejar iniciar.
        """
        if not cita_id:
            return
        ahora = time.time()
        clave = str(cita_id)
        entradas = [
            e for e in (session.get("citas_pagables") or [])
            if isinstance(e, dict)
            and str(e.get("cita_id")) != clave
            and _vigente(e, ahora)
        ]
        entradas.append({"cita_id": clave, "ts": ahora})
        # Si pasan de MAX_CITAS_PAGABLES se caen las mas antiguas.
        session["citas_pagables"] = entradas[-MAX_CITAS_PAGABLES:]

    def _vigente(entrada, ahora):
        ts = entrada.get("ts")
        return isinstance(ts, (int, float)) and 0 <= ahora - ts <= VIGENCIA_PAGO_SEG

    def _cita_pagable_en_sesion(cita_id):
        """True solo si esta sesion abrio /pago para esa cita y la
        vigencia (2 h) sigue abierta. Se compara como texto porque el
        id viaja por query en una ruta y por JSON en otra."""
        if cita_id in (None, ""):
            return False
        ahora = time.time()
        return any(
            isinstance(e, dict)
            and str(e.get("cita_id")) == str(cita_id)
            and _vigente(e, ahora)
            for e in (session.get("citas_pagables") or [])
        )

    def _pago_denegado(cuerpo):
        """Respuesta 403 si la cita del cuerpo no esta habilitada para
        esta sesion; None si se puede seguir."""
        if not _cita_pagable_en_sesion(cuerpo.get("cita_id")):
            app.logger.warning(
                "[pagos] cobro rechazado: la sesion no tiene habilitada la "
                "cita %r (usuario %s)",
                cuerpo.get("cita_id"), session.get("usuario_id"),
            )
            return jsonify({"ok": False, "error": MENSAJE_PAGO_NO_PERMITIDO}), 403
        return None

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            correo = request.form["correo"].strip()
            clave = request.form["clave"].strip()
            if not correo or not clave:
                flash("Completa todos los campos.")
                return redirect(url_for("login"))

            # Dos contadores independientes y ambos tienen que pasar:
            # por IP corta a quien prueba claves desde un solo equipo,
            # por correo corta a quien prueba un correo desde muchos.
            # El corte ocurre ANTES de llamar a auth_service, que asi
            # ni se entera de los intentos que ya no valen.
            limite = app.extensions["rate_limit"]
            claves = (f"ip:{ip_del_request(request, TRUST_PROXY)}", f"correo:{correo.lower()}")
            bloqueado, _ = limite.bloqueado(claves)
            if bloqueado:
                flash(MENSAJE_LOGIN_BLOQUEADO)
                return redirect(url_for("login"))

            data, status = auth_client.post("/api/auth/login", {"correo": correo, "clave": clave})
            if status == 200 and data.get("success"):
                limite.registrar_exito(claves)
                u = data["usuario"]
                session["usuario_id"] = u["id"]
                session["usuario_nombre"] = u["nombre"]
                session["rol"] = u["rol"]
                session["correo"] = u["correo"]
                if u["rol"] == "admin":
                    return redirect(url_for("panel_admin"))
                return redirect(url_for("interfaz"))
            else:
                limite.registrar_fallo(claves)
                flash(MENSAJE_LOGIN_INVALIDO)

        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/interfaz")
    def interfaz():
        if "usuario_id" not in session:
            return redirect(url_for("login"))

        fecha_str = request.args.get("fecha", hoy_lima().strftime("%Y-%m-%d"))
        try:
            fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d")
        except ValueError:
            # Fecha ilegible: se vuelve a HOY en Lima. Es un date y no
            # un datetime, pero lo que se le pide abajo (sumar y restar
            # dias, weekday, strftime) se comporta igual.
            fecha_obj = hoy_lima()

        ayer = (fecha_obj - timedelta(days=1)).strftime("%Y-%m-%d")
        manana = (fecha_obj + timedelta(days=1)).strftime("%Y-%m-%d")
        dias = ["Domingo", "Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado"]
        dia_semana = dias[fecha_obj.weekday() + 1 if fecha_obj.weekday() < 6 else 0]
        fecha_display = fecha_obj.strftime("%d/%m/%Y")
        es_hoy = fecha_str == hoy_lima().strftime("%Y-%m-%d")
        es_admin = session.get("rol") == "admin"

        params = f"?fecha={fecha_str}&estado=programada"
        data, _ = citas_client.get(f"/api/citas{params}")
        # sp_listar_citas ahora devuelve desde p_fecha en adelante (>=);
        # la agenda diaria solo debe mostrar ese día exacto.
        pacientes = [c for c in data.get("citas", []) if str(c.get("fecha_cita", ""))[:10] == fecha_str]
        if not es_admin:
            terapeuta_id = _terapeuta_id_de_sesion()
            pacientes = [
                cita for cita in pacientes
                if terapeuta_id is not None
                and str(cita.get("terapeuta_id")) == str(terapeuta_id)
            ]

        return render_template(
            "interfaz.html", pacientes=pacientes,
            fecha_actual=fecha_str, fecha_display=fecha_display,
            dia_semana=dia_semana, ayer=ayer, manana=manana,
            es_hoy=es_hoy, nombre_usuario=session.get("usuario_nombre"), es_admin=es_admin,
        )

    @app.route("/guardar_descripcion", methods=["POST"])
    def guardar_descripcion():
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        historial_id = request.form.get("historial_id")
        descripcion = request.form.get("descripcion", "").strip()
        fecha = request.form.get("fecha", hoy_lima().strftime("%Y-%m-%d"))

        if session.get("rol") != "admin":
            data, status = citas_client.get(f"/api/citas/{historial_id}")
            if status == 404:
                abort(404)
            if status != 200:
                abort(502, description="No se pudo verificar la cita.")
            cita = data.get("cita") if data else None
            if not cita:
                abort(404)

            terapeuta_id = _terapeuta_id_de_sesion()
            if (
                terapeuta_id is None
                or str(cita.get("terapeuta_id")) != str(terapeuta_id)
            ):
                return redirect(url_for("interfaz"))

        # Completar la cita es responsabilidad del modulo interno de citas.
        citas_client.put(f"/api/citas/{historial_id}/completar", {"descripcion": descripcion})
        log_accion(
            usuario_id=session.get("usuario_id"),
            accion="completar_cita",
            tabla_afectada="historial_citas",
            registro_id=historial_id,
            detalle="Cita marcada como completada",
        )
        return redirect(url_for("interfaz", fecha=fecha))

    @app.route("/citas", methods=["GET", "POST"])
    def citas_page():
        if request.method == "POST":
            ip_claves = [f"citas:{ip_del_request(request, TRUST_PROXY)}"]
            dni = str(request.form.get("dni") or "").strip()
            dni_claves = [f"citas:dni:{dni}"] if dni else []
            limite_ip = app.extensions["citas_rate_limit_ip"]
            limite_dni = app.extensions["citas_rate_limit_dni"]
            bloqueado_ip, _ = limite_ip.bloqueado(ip_claves)
            bloqueado_dni, _ = limite_dni.bloqueado(dni_claves) if dni_claves else (False, None)
            if bloqueado_ip or bloqueado_dni:
                return jsonify({
                    "error": "Límite de citas alcanzado. Intenta de nuevo dentro de una hora.",
                }), 429
            limite_ip.registrar_fallo(ip_claves)
            if dni_claves:
                limite_dni.registrar_fallo(dni_claves)

        # El formulario SIEMPRE se muestra (paso 1 -> 2). Ya no se redirige
        # al pago de una cita vieja de la sesion: eso impedia agendar de
        # nuevo. Si queda una cita sin pagar, solo se ofrece un aviso con
        # el enlace para continuarla (ver _cita_pendiente_de_pago).
        cita_pendiente = _cita_pendiente_de_pago() if request.method == "GET" else None

        data, _ = citas_client.get("/api/citas/terapeutas")
        terapeutas = data.get("terapeutas", [])
        sdata, _ = pacientes_client.get("/api/servicios")
        servicios = sdata.get("servicios", [])

        if request.method == "POST":
            form_data = {k: request.form.get(k, "").strip() for k in
                         ["nombre", "apellido", "dni", "telefono", "medico_id", "fecha_cita", "metodo_pago", "servicio_id"]}
            if not all(form_data.values()):
                msg = "Por favor completa todos los campos, selecciona un médico y elige una fecha."
                if _is_ajax():
                    return jsonify({"error": msg}), 400
                flash("campos_vacios")
                return redirect(url_for("citas_page"))

            # Validacion de formato local y rapida (Tarea A): no gastamos un
            # round-trip HTTP con datos que ya sabemos invalidos.
            error_formato = _validar_datos_cita_rapida(
                form_data["nombre"], form_data["apellido"],
                form_data["dni"], form_data["telefono"],
            )
            if error_formato:
                if _is_ajax():
                    return jsonify({"error": error_formato}), 400
                flash(error_formato)
                return redirect(url_for("citas_page"))

            result, status = citas_client.post("/api/citas", form_data)
            if status == 201 and result.get("success"):
                session["cita_pendiente_id"] = str(result["cita_id"])
                redirect_to = url_for("pago_page", cita_id=result["cita_id"])
                if _is_ajax():
                    return jsonify({
                        "success": True,
                        "mensaje": "Cita reservada correctamente.",
                        "redirect": redirect_to,
                    }), 201
                return redirect(redirect_to)
            if _is_ajax():
                return jsonify(result or {"error": "Error al crear cita"}), status
            flash(result.get("error", "Error al crear cita"))

        return render_template("citas.html", terapeutas=terapeutas, servicios=servicios,
                               cita_pendiente=cita_pendiente)

    @app.route("/citas/modificar", methods=["GET", "POST"])
    def modificar_cita_page():
        data, _ = citas_client.get("/api/citas/terapeutas")
        terapeutas = data.get("terapeutas", [])
        citas_encontradas = None
        paso = None
        dni_val = ""
        tel_mask = ""
        error_msg = None

        # Render de pasos via query cuando llegan de la cadena AJAX.
        if request.method == "GET":
            q_paso = request.args.get("paso")
            q_dni = request.args.get("dni", "").strip()
            if q_paso == "verificar" and _dni_ok(q_dni):
                paso, dni_val = "verificar", q_dni
                tel_mask = session.get("otp_tel_mask", "")
            elif q_paso == "citas" and _dni_ok(q_dni):
                # S1: sin verificacion vigente para ESE dni no se piden
                # ni se muestran las citas; se vuelve al paso 1.
                proteccion = _proteccion_otp(q_dni, "modificar")
                if proteccion is not None:
                    return proteccion
                cdata, _ = citas_client.get(f"/api/citas?dni={q_dni}&estado=programada")
                citas_encontradas = cdata.get("citas", [])

        if request.method == "POST":
            accion = request.form.get("accion")
            if accion == "solicitar":
                dni = request.form.get("dni", "").strip()
                if not _dni_ok(dni):
                    if _is_ajax():
                        return jsonify({"error": "DNI inválido, debe tener 8 dígitos"}), 400
                    error_msg = "DNI inválido, debe tener 8 dígitos"
                else:
                    result, status = citas_client.post("/api/citas/otp/solicitar", {"dni": dni, "accion": "modificar"})
                    if status == 200 and result.get("success"):
                        session["otp_tel_mask"] = result.get("tel_mask", "")
                        if _is_ajax():
                            return jsonify({
                                "success": True,
                                "mensaje": "Código enviado por SMS.",
                                "redirect": f"/citas/modificar?paso=verificar&dni={dni}",
                            }), 200
                        paso, dni_val, tel_mask = "verificar", dni, result.get("tel_mask", "")
                    else:
                        msg = result.get("error", "Error.")
                        if _is_ajax():
                            return jsonify({"error": msg}), status
                        error_msg = msg
            elif accion == "verificar":
                dni = request.form.get("dni", "").strip()
                otp = request.form.get("otp", "").strip()
                result, _ = citas_client.post("/api/citas/otp/verificar", {"dni": dni, "otp": otp, "accion": "modificar"})
                r = result.get("resultado", "")
                if r == "ok":
                    # S1: sin este sello el paso siguiente (paso=citas)
                    # no se abre, ni se acepta un cita_id en el POST.
                    _marcar_otp_verificado(dni, "modificar")
                    if _is_ajax():
                        return jsonify({
                            "success": True,
                            "mensaje": "Identidad verificada.",
                            "redirect": f"/citas/modificar?paso=citas&dni={dni}",
                        }), 200
                    cdata, _ = citas_client.get(f"/api/citas?dni={dni}&estado=programada")
                    citas_encontradas = cdata.get("citas", [])
                else:
                    mensajes = {"expirado": "El codigo expiro.", "agotado": "Intentos agotados.", "no_existe": "Solicita uno nuevo."}
                    msg = mensajes.get(r, f"Codigo incorrecto. Quedan {result.get('restantes', '?')} intento(s).")
                    if _is_ajax():
                        return jsonify({"error": msg}), 400
                    error_msg = msg
                    paso, dni_val = "verificar", dni
            elif accion == "guardar":
                # S1: igual que al cancelar. Sin verificacion vigente o
                # con un cita_id que no es del dni verificado, 403 y no
                # se emite el PUT.
                dni_verificado = _dni_verificado("modificar")
                if not dni_verificado or not _cita_pertenece_al_dni(
                    dni_verificado, request.form.get("cita_id")
                ):
                    return _otp_negado()
                cita_id = request.form.get("cita_id")
                nueva_fecha = request.form.get("fecha_cita", "").strip()
                nuevo_medico = request.form.get("medico_id", "").strip()
                if not cita_id or not nueva_fecha or not nuevo_medico:
                    msg = "Se requieren la nueva fecha y el especialista."
                    if _is_ajax():
                        return jsonify({"error": msg}), 400
                    flash(msg)
                else:
                    result, status = citas_client.put(f"/api/citas/{cita_id}", {"fecha_cita": nueva_fecha, "medico_id": nuevo_medico})
                    if status == 200:
                        if _is_ajax():
                            return jsonify({"success": True, "mensaje": "Cita modificada correctamente."}), 200
                        flash("exito:Cita modificada correctamente.")
                    else:
                        msg = result.get("error", "Error al modificar.")
                        if _is_ajax():
                            return jsonify({"error": msg}), status
                        flash(msg)

        return render_template("modificar_cita.html", terapeutas=terapeutas, citas=citas_encontradas,
                               paso=paso, dni=dni_val, tel_mask=tel_mask, error=error_msg)

    @app.route("/citas/cancelar", methods=["GET", "POST"])
    def cancelar_cita_page():
        citas_encontradas = None
        paso = None
        dni_val = ""
        tel_mask = ""
        error_msg = None

        if request.method == "GET":
            q_paso = request.args.get("paso")
            q_dni = request.args.get("dni", "").strip()
            if q_paso == "verificar" and _dni_ok(q_dni):
                paso, dni_val = "verificar", q_dni
                tel_mask = session.get("otp_tel_mask", "")
            elif q_paso == "citas" and _dni_ok(q_dni):
                # S1: sin verificacion vigente para ESE dni no se piden
                # ni se muestran las citas; se vuelve al paso 1.
                proteccion = _proteccion_otp(q_dni, "cancelar")
                if proteccion is not None:
                    return proteccion
                cdata, _ = citas_client.get(f"/api/citas?dni={q_dni}&estado=programada")
                citas_encontradas = cdata.get("citas", [])

        if request.method == "POST":
            accion = request.form.get("accion")
            if accion == "solicitar":
                dni = request.form.get("dni", "").strip()
                if not _dni_ok(dni):
                    if _is_ajax():
                        return jsonify({"error": "DNI inválido, debe tener 8 dígitos"}), 400
                    error_msg = "DNI inválido, debe tener 8 dígitos"
                else:
                    result, status = citas_client.post("/api/citas/otp/solicitar", {"dni": dni, "accion": "cancelar"})
                    if status == 200 and result.get("success"):
                        session["otp_tel_mask"] = result.get("tel_mask", "")
                        if _is_ajax():
                            return jsonify({
                                "success": True,
                                "mensaje": "Código enviado por SMS.",
                                "redirect": f"/citas/cancelar?paso=verificar&dni={dni}",
                            }), 200
                        paso, dni_val, tel_mask = "verificar", dni, result.get("tel_mask", "")
                    else:
                        msg = result.get("error", "Error.")
                        if _is_ajax():
                            return jsonify({"error": msg}), status
                        error_msg = msg
            elif accion == "verificar":
                dni = request.form.get("dni", "").strip()
                otp = request.form.get("otp", "").strip()
                result, _ = citas_client.post("/api/citas/otp/verificar", {"dni": dni, "otp": otp, "accion": "cancelar"})
                r = result.get("resultado", "")
                if r == "ok":
                    _marcar_otp_verificado(dni, "cancelar")
                    if _is_ajax():
                        return jsonify({
                            "success": True,
                            "mensaje": "Identidad verificada.",
                            "redirect": f"/citas/cancelar?paso=citas&dni={dni}",
                        }), 200
                    cdata, _ = citas_client.get(f"/api/citas?dni={dni}&estado=programada")
                    citas_encontradas = cdata.get("citas", [])
                else:
                    mensajes = {"expirado": "El codigo expiro.", "agotado": "Intentos agotados.", "no_existe": "Solicita uno nuevo."}
                    msg = mensajes.get(r, f"Codigo incorrecto. Quedan {result.get('restantes', '?')} intento(s).")
                    if _is_ajax():
                        return jsonify({"error": msg}), 400
                    error_msg = msg
                    paso, dni_val = "verificar", dni
            elif accion == "confirmar":
                # S1: el cuerpo solo trae un cita_id, asi que la
                # identidad sale de la sesion y ademas hay que probar
                # que esa cita es del dni verificado. Si no, 403 antes
                # de llamar al modulo interno de citas.
                dni_verificado = _dni_verificado("cancelar")
                if not dni_verificado or not _cita_pertenece_al_dni(
                    dni_verificado, request.form.get("cita_id")
                ):
                    return _otp_negado()
                cita_id = request.form.get("cita_id")
                result, status = citas_client.delete(f"/api/citas/{cita_id}")
                if status == 200:
                    if _is_ajax():
                        return jsonify({
                            "success": True,
                            "mensaje": "Tu cita ha sido cancelada correctamente.",
                            "redirect": "/citas/cancelar",
                        }), 200
                    flash("exito:Tu cita ha sido cancelada correctamente.")
                else:
                    msg = result.get("error", "No se pudo cancelar la cita.")
                    if _is_ajax():
                        return jsonify({"error": msg}), status
                    flash(msg)

        return render_template("cancelar_cita.html", citas=citas_encontradas,
                               paso=paso, dni=dni_val, tel_mask=tel_mask, error=error_msg)

    @app.route("/tratamiento", methods=["GET", "POST"])
    def tratamiento_page():
        """Continuar tratamiento: el paciente recurrente con un paquete
        activo agenda la siguiente sesion sin repetir sus datos.
        1) OTP por SMS (reusa el flujo de /citas/modificar y /citas/cancelar).
        2) Lista sus paquetes activos y agenda fecha+medico (y metodo de pago).
        La cita se crea con el MISMO POST /api/citas y luego se vincula al
        paquete (incrementa sesiones_usadas) mediante el modulo interno de pagos."""
        data, _ = citas_client.get("/api/citas/terapeutas")
        terapeutas = data.get("terapeutas", [])

        paso = None
        dni_val = ""
        tel_mask = ""
        error_msg = None
        paquetes = []
        paciente = None

        # Reproducir pasos de la cadena AJAX cuando llegan por query.
        if request.method == "GET":
            q_paso = request.args.get("paso")
            q_dni = request.args.get("dni", "").strip()
            if q_paso == "verificar" and _dni_ok(q_dni):
                paso, dni_val = "verificar", q_dni
                tel_mask = session.get("otp_tel_mask", "")
            elif q_paso in ("menu", "sin_paquetes") and _dni_ok(q_dni):
                # S1: el menu de paquetes son datos de salud; sin
                # verificacion vigente para ESE dni se vuelve al paso 1.
                proteccion = _proteccion_otp(q_dni, "tratamiento")
                if proteccion is not None:
                    return proteccion
                paso, dni_val = q_paso, q_dni
                paciente, paquetes = _paquetes_activos_dni(q_dni)
                if paso == "menu" and not paquetes:
                    paso = "sin_paquetes"

        if request.method == "POST":
            accion = request.form.get("accion")
            if accion == "solicitar":
                dni = request.form.get("dni", "").strip()
                if not _dni_ok(dni):
                    msg = "DNI inválido, debe tener 8 dígitos"
                    if _is_ajax():
                        return jsonify({"error": msg}), 400
                    error_msg = msg
                else:
                    result, status = citas_client.post("/api/citas/otp/solicitar", {"dni": dni, "accion": "tratamiento"})
                    if status == 200 and result.get("success"):
                        session["otp_tel_mask"] = result.get("tel_mask", "")
                        if _is_ajax():
                            return jsonify({
                                "success": True,
                                "mensaje": "Código enviado por SMS.",
                                "redirect": f"/tratamiento?paso=verificar&dni={dni}",
                            }), 200
                        paso, dni_val, tel_mask = "verificar", dni, result.get("tel_mask", "")
                    else:
                        msg = result.get("error", "Error.")
                        if _is_ajax():
                            return jsonify({"error": msg}), status
                        error_msg = msg
            elif accion == "verificar":
                dni = request.form.get("dni", "").strip()
                otp = request.form.get("otp", "").strip()
                result, _ = citas_client.post("/api/citas/otp/verificar", {"dni": dni, "otp": otp, "accion": "tratamiento"})
                r = result.get("resultado", "")
                if r == "ok":
                    # S1: OTP superado. Se sella antes de resolver el
                    # paciente para que valga igual en el camino AJAX
                    # y en el normal.
                    _marcar_otp_verificado(dni, "tratamiento")
                    paciente, paquetes = _paquetes_activos_dni(dni)
                    if not paciente:
                        msg = "No se encontró el paciente asociado a ese DNI."
                        if _is_ajax():
                            return jsonify({"error": msg}), 404
                        error_msg = msg
                        paso, dni_val = "verificar", dni
                    else:
                        session["tratamiento_paciente"] = paciente
                        target = "sin_paquetes" if not paquetes else "menu"
                        if _is_ajax():
                            return jsonify({
                                "success": True,
                                "mensaje": "Identidad verificada.",
                                "redirect": f"/tratamiento?paso={target}&dni={dni}",
                            }), 200
                        paso, dni_val = target, dni
                else:
                    mensajes = {"expirado": "El codigo expiro.", "agotado": "Intentos agotados.", "no_existe": "Solicita uno nuevo."}
                    msg = mensajes.get(r, f"Codigo incorrecto. Quedan {result.get('restantes', '?')} intento(s).")
                    if _is_ajax():
                        return jsonify({"error": msg}), 400
                    error_msg = msg
                    paso, dni_val = "verificar", dni
            elif accion == "agendar":
                paquete_id = request.form.get("paquete_id", "").strip()
                fecha = request.form.get("fecha_cita", "").strip()
                medico = request.form.get("medico_id", "").strip()
                metodo = request.form.get("metodo_pago", "").strip()
                paciente = session.get("tratamiento_paciente")

                msg = None
                if not paciente:
                    msg = "Tu sesión ha expirado. Vuelve a verificar tu identidad."
                elif not paquete_id or not fecha or not medico or not metodo:
                    msg = "Selecciona el tratamiento, la fecha, el especialista y el método de pago."
                else:
                    # Revalida que el paquete siga activo y pertenezca al paciente.
                    _, activos = _paquetes_activos_dni(paciente["dni"])
                    paquete = next((p for p in activos if str(p.get("id")) == str(paquete_id)), None)
                    if not paquete:
                        msg = "El tratamiento ya no tiene sesiones disponibles o expiró."
                    else:
                        cita_data = {
                            "nombre": paciente["nombre"],
                            "apellido": paciente["apellido"],
                            "dni": paciente["dni"],
                            "telefono": paciente["telefono"],
                            "medico_id": medico,
                            "fecha_cita": fecha,
                            "metodo_pago": metodo,
                            "servicio_id": paquete["servicio_id"],
                        }
                        result, status = citas_client.post("/api/citas", cita_data)
                        if status == 201 and result.get("success"):
                            cita_id = result["cita_id"]
                            session["cita_pendiente_id"] = cita_id
                            # Vinculacion ADICIONAL de la cita al paquete
                            # (paso posterior a la creacion de la cita).
                            try:
                                pagos_client.post(f"/api/pagos/paquetes/{paquete_id}/usar", {"cita_id": cita_id})
                            except Exception as exc:
                                # La cita ya quedo creada; lo que se
                                # pierde aqui es el vinculo con el
                                # paquete, no el cobro. Se loguea para
                                # poder cazarlo, pero no se rompe el
                                # alta.
                                app.logger.warning(
                                    "No se pudo vincular la cita %s al paquete %s: %s: %s",
                                    cita_id, paquete_id, type(exc).__name__, exc,
                                )
                            redirect_to = url_for("pago_page", cita_id=cita_id)
                            if _is_ajax():
                                return jsonify({
                                    "success": True,
                                    "mensaje": "Sesión agendada correctamente.",
                                    "redirect": redirect_to,
                                }), 201
                            return redirect(redirect_to)
                        msg = result.get("error", "No se pudo agendar la sesión del tratamiento.")
                if _is_ajax():
                    return jsonify({"error": msg}), 400
                error_msg = msg
                if paciente:
                    dni_val = paciente["dni"]
                    paciente, paquetes = _paquetes_activos_dni(dni_val)
                    paso = "menu" if paquetes else "sin_paquetes"

        return render_template("tratamiento.html", terapeutas=terapeutas, paquetes=paquetes,
                               paciente=paciente, paso=paso, dni=dni_val,
                               tel_mask=tel_mask, error=error_msg)

    @app.route("/pago")
    def pago_page():
        cita_id = request.args.get("cita_id")
        if not _cita_autorizada_en_sesion(cita_id):
            return redirect(url_for("citas_page"))
        data, pago_status = pagos_client.get(f"/api/pagos/{cita_id}")
        pago = (data or {}).get("pago")

        cdata, _ = citas_client.get(f"/api/citas/{cita_id}")
        cita = cdata.get("cita", {})

        if pago:
            if pago.get("estado_pago") == "pagado":
                return redirect(url_for("retorno_page", cita_id=cita_id))

            # Se muestra el formulario: esta sesion queda habilitada para
            # iniciar y consultar el cobro de esta cita (ver _pago_denegado).
            _registrar_cita_pagable(cita_id)

            cita["monto"] = float(pago.get("monto") or 0)
            cita["metodo_pago"] = pago.get("metodo_pago", "")
            cita["estado_pago"] = pago.get("estado_pago", "pendiente")
        else:
            # Sin pago asociado: se muestra la pagina con los datos de la cita.
            cita.setdefault("monto", 0)
            cita.setdefault("metodo_pago", "")
            cita.setdefault("estado_pago", "")

        from services.pagos_service.providers import NiubizClient
        niubiz = NiubizClient()
        return render_template(
            "pago.html", cita=cita, niubiz_sdk_url=niubiz.sdk_url,
            niubiz_mode=niubiz.mode, modo_demo=PAGOS_MODO_DEMO,
        )

    @app.route("/retorno")
    def retorno_page():
        cita_id = request.args.get("cita_id")
        if not _cita_autorizada_en_sesion(cita_id, incluir_pagada=True):
            return redirect(url_for("citas_page"))
        data, _ = pagos_client.get(f"/api/pagos/{cita_id}")
        pago = data.get("pago", {})

        # El pago solo figura "pagado" cuando el modulo de pagos lo confirmo
        # contra la pasarela (yape/plin/tarjeta). No hay atajo por sesion:
        # una cita sin confirmar vuelve al paso de pago.
        if pago.get("estado_pago") != "pagado":
            return redirect(url_for("pago_page", cita_id=cita_id))

        # Pago confirmado: la cita ya no esta pendiente de cobro.
        session.pop("cita_pendiente_id", None)
        # Permite recargar /retorno sin perder acceso (paciente sin login).
        session["cita_recien_pagada"] = cita_id

        cdata, _ = citas_client.get(f"/api/citas/{cita_id}")
        cita = cdata.get("cita", {})
        cita["monto"] = float(pago.get("monto") or 0)
        cita["metodo_pago"] = pago.get("metodo_pago", "")
        cita["referencia"] = pago.get("referencia")
        cita["transaccion_id"] = pago.get("transaccion_id")

        fecha_fmt = cita.get("fecha_cita", "")
        try:
            fecha_fmt = datetime.strptime(str(cita["fecha_cita"]), "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception as exc:
            # Se queda con el texto crudo de la fecha en la plantilla;
            # avisar para que no pase desapercibido si llega otro
            # formato.
            app.logger.warning(
                "No se pudo formatear la fecha %r de la cita %s: %s: %s",
                cita.get("fecha_cita"), cita_id, type(exc).__name__, exc,
            )

        return render_template("retorno.html", cita_id=cita_id, cita=cita, fecha_fmt=fecha_fmt)

    @app.route("/panel_admin", methods=["GET", "POST"])
    @_admin_required
    def panel_admin():

        if request.method == "POST":
            accion = request.form.get("accion")
            if accion == "registrar":
                nombre = request.form.get("nombre", "").strip()
                especialidad = request.form.get("especialidad", "").strip()
                correo = request.form.get("correo", "").strip()
                clave = request.form.get("clave", "").strip()
                precio = request.form.get("precio", "").strip()

                if nombre and especialidad and correo and clave:
                    # Las consultas a auth y pacientes se despachan en
                    # proceso. El hash de la clave lo hace el modulo auth.
                    existente, estatus = auth_client.get(f"/api/auth/usuarios/por-nombre/{nombre}")
                    if estatus == 200:
                        flash("Ya existe un terapeuta con ese nombre.")
                    else:
                        try:
                            precio_num = float(precio) if precio else None
                        except ValueError:
                            precio_num = None
                        telefono = request.form.get("telefono", "").strip()

                        creado, cstatus = auth_client.post("/api/auth/usuarios", {
                            "nombre": nombre, "correo": correo,
                            "clave": clave, "rol": "terapeuta", "telefono": telefono or None,
                        })
                        if cstatus not in (200, 201):
                            flash(creado.get("error", "No se pudo crear el usuario."))
                        else:
                            usuario_id = (creado or {}).get("usuario_id")
                            esp, estatus = pacientes_client.get(f"/api/especialidades/por-nombre/{especialidad}")
                            esp_id = (esp or {}).get("id") if estatus == 200 else None
                            pacientes_client.post("/api/terapeutas", {
                                "usuario_id": usuario_id, "especialidad_id": esp_id, "precio": precio_num,
                            })
                            log_accion(
                                usuario_id=session.get("usuario_id"),
                                accion="crear_usuario",
                                tabla_afectada="usuarios",
                                registro_id=usuario_id,
                                detalle=f"Terapeuta creado: nombre={nombre}, correo={correo}",
                            )
                            flash("exito:Terapeuta registrado correctamente.")
                else:
                    flash("Completa todos los campos.")

            elif accion == "actualizar_precio":
                mid = request.form.get("medico_id")
                precio = request.form.get("precio", "").strip()
                if mid and precio:
                    try:
                        pacientes_client.put(f"/api/terapeutas/{mid}/precio", {"precio": float(precio)})
                        flash("exito:Precio actualizado.")
                    except ValueError:
                        flash("Precio invalido.")

            elif accion == "actualizar_telefono":
                uid = request.form.get("usuario_id")
                telefono = request.form.get("telefono", "").strip()
                # Mismo criterio que auth_service: movil peruano de 9 digitos
                # que empieza por 9, o vacio para borrar el telefono.
                if not uid:
                    flash("Usuario no encontrado.")
                elif telefono and not re.fullmatch(r"9\d{8}", telefono):
                    flash("Telefono invalido: se esperan 9 digitos que empiezan por 9.")
                else:
                    # Igual que en el resto de la fase: si el servicio de
                    # auth no responde, el panel no debe caerse.
                    try:
                        resp, estatus = auth_client.put(
                            f"/api/auth/usuarios/{uid}", {"telefono": telefono}
                        )
                    except Exception:
                        resp, estatus = None, 503
                    if estatus in (200, 201):
                        flash("exito:Telefono actualizado.")
                    else:
                        flash((resp or {}).get("error") or "No se pudo guardar el telefono.")

            elif accion == "eliminar":
                mid = request.form.get("medico_id")
                if mid:
                    tdata, _ = pacientes_client.get(f"/api/terapeutas/{mid}")
                    terapeuta = tdata.get("terapeuta", {}) if tdata else {}
                    if terapeuta:
                        pacientes_client.put(f"/api/terapeutas/{mid}/activo", {"activo": 0})
                        if terapeuta.get("usuario_id"):
                            auth_client.put(f"/api/auth/usuarios/{terapeuta['usuario_id']}", {"activo": 0})
                        log_accion(
                            usuario_id=session.get("usuario_id"),
                            accion="desactivar_usuario",
                            tabla_afectada="usuarios",
                            registro_id=terapeuta.get("usuario_id"),
                            detalle=f"Terapeuta id={mid} desactivado",
                        )
                        flash("exito:Terapeuta desactivado.")

            elif accion == "reactivar":
                mid = request.form.get("medico_id")
                if mid:
                    tdata, _ = pacientes_client.get(f"/api/terapeutas/{mid}")
                    terapeuta = tdata.get("terapeuta", {}) if tdata else {}
                    if terapeuta:
                        pacientes_client.put(f"/api/terapeutas/{mid}/activo", {"activo": 1})
                        if terapeuta.get("usuario_id"):
                            auth_client.put(f"/api/auth/usuarios/{terapeuta['usuario_id']}", {"activo": 1})
                        flash("exito:Terapeuta reactivado.")

            elif accion == "cambiar_clave":
                mid = request.form.get("medico_id")
                nc = request.form.get("nueva_clave", "").strip()
                if mid and nc:
                    tdata, _ = pacientes_client.get(f"/api/terapeutas/{mid}")
                    terapeuta = tdata.get("terapeuta", {}) if tdata else {}
                    if terapeuta and terapeuta.get("usuario_id"):
                        # El hash de la clave lo hace el modulo auth.
                        auth_client.put(f"/api/auth/usuarios/{terapeuta['usuario_id']}", {"clave": nc})
                        flash("exito:Contrasena actualizada.")

            return redirect(url_for("panel_admin"))

        tdata, _ = pacientes_client.get("/api/terapeutas")
        medicos = tdata.get("terapeutas", [])
        edata, _ = pacientes_client.get("/api/especialidades")
        especialidades = edata.get("especialidades", [])
        udata, _ = auth_client.get("/api/auth/usuarios")
        usuarios = udata.get("usuarios", [])

        params = "?fecha=" + hoy_lima().strftime("%Y-%m-%d") + "&estado=programada"
        cdata, _ = citas_client.get(f"/api/citas{params}")
        proximas_citas = cdata.get("citas", [])[:20]

        return render_template("paneladmin.html", medicos=medicos, proximas_citas=proximas_citas,
                               especialidades=especialidades, usuarios=usuarios)

    @app.route("/panel_admin/auditoria")
    @_admin_required
    def panel_admin_auditoria():

        usuarios_filtro = []
        try:
            udata, _ustatus = auth_client.get("/api/auth/usuarios")
            usuarios_filtro = [
                u for u in (udata.get("usuarios") or [])
                if u.get("rol") in ("admin", "terapeuta")
            ]
        except Exception:
            usuarios_filtro = []

        filtros = {}
        for key in ("usuario_id", "usuario_tipo", "accion", "fecha_desde", "fecha_hasta", "entidad_tipo"):
            valor = (request.args.get(key) or "").strip()
            if valor:
                filtros[key] = valor

        # El selector "Usuario" unificado solo envia usuario_id; se deriva el
        # usuario_tipo del rol real del usuario elegido para no duplicar el
        # control de tipo en la fila principal (los params no cambian).
        if "usuario_id" in filtros and "usuario_tipo" not in filtros:
            for u in usuarios_filtro:
                if str(u.get("id")) == str(filtros["usuario_id"]):
                    filtros["usuario_tipo"] = u.get("rol")
                    break

        params = ""
        if filtros:
            params = "?" + urlencode(filtros)

        logs = []
        try:
            data, _status = audit_client.get(f"/api/auditoria{params}")
            if isinstance(data, dict):
                logs = data.get("logs") or []
        except Exception:
            logs = []

        return render_template("auditoria.html", logs=logs, filtros=filtros,
                               usuarios_filtro=usuarios_filtro)

    def _rango_kpis():
        """Lee ?desde y ?hasta (YYYY-MM-DD). Por defecto, los ultimos 30 dias de Lima."""
        hoy = hoy_lima()
        por_defecto = (hoy - timedelta(days=30), hoy)
        desde_txt = (request.args.get("desde") or "").strip()
        hasta_txt = (request.args.get("hasta") or "").strip()
        try:
            desde = datetime.strptime(desde_txt, "%Y-%m-%d").date() if desde_txt else por_defecto[0]
            hasta = datetime.strptime(hasta_txt, "%Y-%m-%d").date() if hasta_txt else por_defecto[1]
        except ValueError:
            return por_defecto
        if desde > hasta:
            return por_defecto
        return desde, hasta

    def _cargar_kpis(desde, hasta):
        """Pide los KPIs al servicio de citas. Devuelve (resumen, por_terapeuta, error)."""
        resumen, por_terapeuta, error = None, [], None
        try:
            data, status = citas_client.get(
                f"/api/kpis?desde={desde.isoformat()}&hasta={hasta.isoformat()}")
            if status == 200 and data.get("success"):
                resumen = data.get("resumen") or {}
                por_terapeuta = data.get("por_terapeuta") or []
            else:
                error = (data or {}).get("error") or "No se pudieron cargar los KPIs"
        except Exception:
            error = "Servicio de KPIs no disponible"
        return resumen, por_terapeuta, error

    @app.route("/panel_admin/kpis")
    @_admin_required
    def panel_admin_kpis():
        """Pagina del panel de KPIs. Los datos los dibuja React desde kpis.json."""
        desde, hasta = _rango_kpis()
        return render_template("kpis.html", desde=desde.isoformat(), hasta=hasta.isoformat())

    @app.route("/panel_admin/kpis.json")
    def panel_admin_kpis_json():
        """KPIs en JSON para el panel React. Sin sesion: 401; sin rol admin: 403 (nunca redirect)."""
        if "usuario_id" not in session:
            return jsonify({"success": False, "error": "Sesión expirada"}), 401
        if session.get("rol") != "admin":
            return jsonify({"success": False, "error": "Solo administradores"}), 403
        desde, hasta = _rango_kpis()
        resumen, por_terapeuta, error = _cargar_kpis(desde, hasta)
        return jsonify({
            "desde": desde.isoformat(),
            "hasta": hasta.isoformat(),
            "resumen": resumen,
            "por_terapeuta": por_terapeuta,
            "error": error,
        })

    # ---- MoovaTrack (prototipo con datos simulados) ----

    @app.route("/moovatrack")
    def moovatrack_page():
        """Panel MoovaTrack: solo con sesion (admin o terapeuta), como /interfaz."""
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return render_template("moovatrack.html",
                               nombre_usuario=session.get("usuario_nombre", ""),
                               es_admin=session.get("rol") == "admin")

    @app.route("/api/moovatrack/lectura")
    def moovatrack_lectura():
        """Lectura SIMULADA de un movimiento de flexion/extension.

        En produccion estos datos llegarian por Bluetooth (HC-05) desde el
        Arduino con MPU-6050 (angulo), FSR 402 (fuerza) y Flex Sensor. Aqui se
        genera una onda de 4 s por repeticion mas un poco de ruido.
        """
        if "usuario_id" not in session:
            return jsonify({"success": False, "error": "Sesión expirada"}), 401
        t = time.time()
        fase = math.sin(2 * math.pi * t / 4.0)          # -1 .. 1
        angulo = 90 + 75 * fase + random.uniform(-3, 3)
        angulo = max(0, min(180, angulo))
        # La fuerza sube cuando el movimiento esta cerca de la extension maxima.
        fuerza = 22 + 18 * max(0.0, fase) + random.uniform(-2, 2)
        fuerza = max(0, fuerza)
        return jsonify({
            "success": True,
            "simulado": True,
            "angulo": round(angulo, 1),
            "fuerza": round(fuerza, 1),
            "timestamp": datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        })

    @app.route("/panel_admin/riesgo")
    @_admin_required
    def panel_admin_riesgo():
        """Reporte de pacientes en riesgo de fuga.

        Pide el listado al modulo interno de citas (/api/citas/riesgo). Si
        ocurre un error, se muestra el panel vacio con el aviso
        en vez de una pagina en blanco.
        """
        fecha = (request.args.get("fecha") or "").strip()
        dias_umbral = (request.args.get("dias_umbral") or "").strip()

        params = {}
        if fecha:
            params["fecha"] = fecha
        if dias_umbral:
            params["dias_umbral"] = dias_umbral
        ruta = "/api/citas/riesgo"
        if params:
            ruta += "?" + urlencode(params)

        resumen, error = None, None
        try:
            data, status = citas_client.get(ruta)
            if status == 200 and data.get("success"):
                resumen = data
            else:
                error = (data or {}).get("error") or "No se pudo cargar el reporte de riesgo"
        except Exception:
            error = "Servicio de citas no disponible"

        return render_template(
            "riesgo.html",
            resumen=resumen,
            error=error,
            fecha=fecha,
            dias_umbral=dias_umbral,
        )

    @app.route("/panel_admin/cancelar_cita/<int:cita_id>", methods=["POST"])
    @_admin_required
    def admin_cancelar_cita(cita_id):
        citas_client.delete(f"/api/citas/{cita_id}")
        flash("exito:Cita cancelada.")
        return redirect(url_for("panel_admin"))

    @app.route("/pacientes")
    @_admin_required
    def pacientes_page():
        data, _ = pacientes_client.get("/api/pacientes")
        return render_template("pacientes.html", pacientes=data.get("pacientes", []))

    @app.route("/pacientes/<paciente_dni>")
    @_admin_required
    def detalle_paciente_page(paciente_dni):
        data, _ = pacientes_client.get(f"/api/pacientes/{paciente_dni}")
        paciente = data.get("paciente", {})
        historial = data.get("historial", [])
        paquetes, evaluaciones, consentimientos = _cargar_anexos_paciente(paciente.get("id"))

        return render_template("detalle_paciente.html", paciente=paciente,
                               historial=historial, paquetes=paquetes,
                               evaluaciones=evaluaciones, consentimientos=consentimientos)

    @app.route("/pacientes/<paciente_dni>/ficha-clinica.pdf")
    @_admin_required
    def ficha_clinica_pdf(paciente_dni):
        data, status = pacientes_client.get(f"/api/pacientes/{paciente_dni}")
        if status == 404 or not data.get("paciente"):
            flash("Paciente no encontrado", "danger")
            return redirect(url_for("pacientes_page"))

        paciente = data.get("paciente", {})
        historial = data.get("historial", [])
        paquetes, evaluaciones, consentimientos = _cargar_anexos_paciente(paciente.get("id"))

        pdf_bytes = build_ficha_clinica_pdf(
            paciente, historial, paquetes, evaluaciones, consentimientos,
            generado_por=session.get("usuario_nombre"),
        )
        log_accion(
            usuario_id=session.get("usuario_id"),
            accion="ficha_clinica_pdf",
            tabla_afectada="pacientes",
            registro_id=paciente.get("id"),
            detalle="Descarga de ficha clínica",
        )
        nombre_archivo = f"ficha_clinica_{paciente.get('dni') or paciente_dni}.pdf"
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{nombre_archivo}"'},
        )

    @app.route("/notas/<int:cita_id>", methods=["GET", "POST"])
    @_login_required
    def notas_page(cita_id):
        if "usuario_id" not in session:
            return redirect(url_for("login"))

        cdata, _ = citas_client.get(f"/api/citas/{cita_id}")
        cita = cdata.get("cita", {})

        # Verificar que el usuario tenga permisos: admin o terapeuta de esta cita
        usuario_rol = session.get("rol")
        if usuario_rol != "admin":
            terapeuta_id = _terapeuta_id_de_sesion()
            if (
                terapeuta_id is None
                or str(cita.get("terapeuta_id")) != str(terapeuta_id)
            ):
                return redirect(url_for("index"))

        if request.method == "POST":
            nota = request.form.get("nota", "").strip()
            diagnostico = request.form.get("diagnostico", "").strip()
            # Guardar el terapeuta_id real de la cita, no None
            terapeuta_id = cita.get("terapeuta_id")
            notas_client.post(f"/api/notas/{cita_id}", {
                "nota": nota, "diagnostico": diagnostico,
                "terapeuta_id": terapeuta_id,
                "paciente_id": cita.get("paciente_id"),
            })
            flash("exito:Nota clinica guardada.")
            return redirect(url_for("notas_page", cita_id=cita_id))

        ndata, _ = notas_client.get(f"/api/notas/{cita_id}")
        return render_template("notas_cita.html", cita=cita, notas=ndata.get("notas", []))

    @app.route("/api/verificar_dni", methods=["POST"])
    def verificar_dni():
        cuerpo = request.get_json(silent=True)
        valor_dni = cuerpo.get("dni", "") if isinstance(cuerpo, dict) else ""
        dni = valor_dni.strip() if isinstance(valor_dni, str) else ""
        if not _dni_ok(dni):
            return jsonify({"success": False, "error": "DNI inválido"}), 400

        # Rate limit simple: máximo 5 consultas DNI por sesión para evitar force brute
        historial = session.get("_dn_consultas", [])
        ahora = time.time()
        historial = [t for t in historial if ahora - t < 60]  # último minuto
        if len(historial) >= 5:
            return jsonify({
                "success": False,
                "error": "Demasiadas consultas DNI. Intenta más tarde.",
            }), 429

        ip = ip_del_request(request, TRUST_PROXY)
        consultas_por_ip = app.extensions["consultas_dni_por_ip"]
        with app.extensions["consultas_dni_por_ip_lock"]:
            for ip_registrada, tiempos in list(consultas_por_ip.items()):
                tiempos = [t for t in tiempos if ahora - t < 60]
                if tiempos:
                    consultas_por_ip[ip_registrada] = tiempos
                else:
                    del consultas_por_ip[ip_registrada]
            historial_ip = consultas_por_ip.get(ip, [])
            if len(historial_ip) >= 15:
                return jsonify({
                    "success": False,
                    "error": "Demasiadas consultas DNI. Intenta más tarde.",
                }), 429
            consultas_por_ip[ip] = historial_ip + [ahora]
        session["_dn_consultas"] = historial + [ahora]

        # El servicio de pacientes ya devuelve solo nombres y apellidos.
        try:
            data, status = pacientes_client.post("/api/pacientes/buscar_dni", {"dni": dni})
            return jsonify(data), status
        except Exception:
            return jsonify({
                "success": False,
                "error": "No se pudo consultar el DNI",
            }), 502

    @app.route("/api/estadisticas")
    def api_estadisticas():
        data, _ = citas_client.get("/api/citas/estadisticas")
        return jsonify(data)

    @app.route("/api/disponibilidad/<int:medico_id>", methods=["GET"])
    def api_disponibilidad_medico(medico_id):
        ip = ip_del_request(request, TRUST_PROXY)
        claves = [f"disponibilidad:{ip}"]
        limite = app.extensions["disponibilidad_rate_limit"]
        bloqueado, _ = limite.bloqueado(claves)
        if bloqueado:
            return jsonify({"error": "Demasiadas consultas. Intenta más tarde."}), 429
        limite.registrar_fallo(claves)

        data, status = citas_client.get(
            "/api/citas/ocupadas",
            params={
                "medico_id": medico_id,
                "desde": request.args.get("desde", ""),
                "hasta": request.args.get("hasta", ""),
            },
        )
        return jsonify(data or {}), status

    # Proxy publico de las pasarelas Yape/Plin (QR y consulta de estado).
    # El frontend de pago.html las invoca con ruta relativa al gateway
    # (same-origin), asi que se despachan al modulo interno de pagos preservando el
    # cuerpo JSON y el codigo de estado. No toca el flujo de tarjeta/Niubiz.
    #
    # Son publicos (no tienen _login_required, porque el navegador llega
    # con su cookie de sesion y no con la API_KEY interna), asi que el
    # filtro es _pago_denegado: solo la sesion que abrio /pago para esa
    # cita puede iniciarle o consultarle un cobro. /api/pagos/webhook y el
    # retorno de Niubiz no pasan por aqui y quedan tal cual estaban.
    @app.route("/api/pagos/yape/iniciar", methods=["POST"])
    @app.route("/api/pagos/plin/iniciar", methods=["POST"])
    def proxy_pago_scan_iniciar():
        cuerpo = request.get_json(silent=True) or {}
        denegado = _pago_denegado(cuerpo)
        if denegado:
            return denegado
        data, status = pagos_client.post(request.path, cuerpo)
        return jsonify(data or {}), status

    @app.route("/api/pagos/yape/estado", methods=["POST"])
    @app.route("/api/pagos/plin/estado", methods=["POST"])
    def proxy_pago_scan_estado():
        cuerpo = request.get_json(silent=True) or {}
        denegado = _pago_denegado(cuerpo)
        if denegado:
            return denegado
        data, status = pagos_client.post(request.path, cuerpo)
        return jsonify(data or {}), status

    return app
