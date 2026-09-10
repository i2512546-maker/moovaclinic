import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import re
import yaml
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
from urllib.parse import urlencode
from shared.config import REDES_SOCIALES
from shared.service_client import auth_client, pacientes_client, citas_client, pagos_client, notas_client
from shared.audit import log_accion

bcrypt = Bcrypt()


def _is_ajax():
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )


def _dni_ok(valor):
    return bool(re.fullmatch(r"\d{8}", (valor or "").strip()))


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


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = os.getenv("SECRET_KEY", os.urandom(32).hex())
    bcrypt.init_app(app)

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
            "current_user": {
                "id": session.get("usuario_id"),
                "nombre": session.get("usuario_nombre"),
                "rol": session.get("rol"),
                "es_admin": session.get("rol") == "admin",
                "es_terapeuta": session.get("rol") == "terapeuta",
            }
        }

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

            data, status = auth_client.post("/api/auth/login", {"correo": correo, "clave": clave})
            if status == 200 and data.get("success"):
                u = data["usuario"]
                session["usuario_id"] = u["id"]
                session["usuario_nombre"] = u["nombre"]
                session["rol"] = u["rol"]
                session["correo"] = u["correo"]
                if u["rol"] == "admin":
                    return redirect(url_for("panel_admin"))
                return redirect(url_for("interfaz"))
            else:
                flash(data.get("error", "Credenciales incorrectas."))

        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/interfaz")
    def interfaz():
        if "usuario_id" not in session:
            return redirect(url_for("login"))

        fecha_str = request.args.get("fecha", datetime.today().strftime("%Y-%m-%d"))
        try:
            fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d")
        except ValueError:
            fecha_obj = datetime.today()

        ayer = (fecha_obj - timedelta(days=1)).strftime("%Y-%m-%d")
        manana = (fecha_obj + timedelta(days=1)).strftime("%Y-%m-%d")
        dias = ["Domingo", "Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado"]
        dia_semana = dias[fecha_obj.weekday() + 1 if fecha_obj.weekday() < 6 else 0]
        fecha_display = fecha_obj.strftime("%d/%m/%Y")
        es_hoy = fecha_str == datetime.today().strftime("%Y-%m-%d")
        es_admin = session.get("rol") == "admin"

        params = f"?fecha={fecha_str}&estado=programada"
        data, _ = citas_client.get(f"/api/citas{params}")
        # sp_listar_citas ahora devuelve desde p_fecha en adelante (>=);
        # la agenda diaria solo debe mostrar ese día exacto.
        pacientes = [c for c in data.get("citas", []) if str(c.get("fecha_cita", ""))[:10] == fecha_str]

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
        fecha = request.form.get("fecha", datetime.today().strftime("%Y-%m-%d"))

        # FASE 2: completar cita es responsabilidad de citas_service.
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
        # Si ya se creo una cita en esta sesion, no volver a mostrar el
        # formulario: se redirige al pago (paso 3) de esa cita.
        cita_pendiente = session.get("cita_pendiente_id")
        if request.method == "GET" and cita_pendiente:
            return redirect(url_for("pago_page", cita_id=cita_pendiente))

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
                session["cita_pendiente_id"] = result["cita_id"]
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

        return render_template("citas.html", terapeutas=terapeutas, servicios=servicios)

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
        paquete (incrementa sesiones_usadas) via pagos_service."""
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
                            # Vinculacion ADICIONAL de la cita al paquete
                            # (paso posterior a la creacion de la cita).
                            try:
                                pagos_client.post(f"/api/pagos/paquetes/{paquete_id}/usar", {"cita_id": cita_id})
                            except Exception:
                                pass
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
        data, _ = pagos_client.get(f"/api/pagos/{cita_id}")
        pago = data.get("pago", {})

        cdata, _ = citas_client.get(f"/api/citas/{cita_id}")
        cita = cdata.get("cita", {})

        if pago.get("estado_pago") == "pagado":
            return redirect(url_for("retorno_page", cita_id=cita_id))

        cita["monto"] = float(pago.get("monto") or 0)
        cita["metodo_pago"] = pago.get("metodo_pago", "")
        cita["estado_pago"] = pago.get("estado_pago", "pendiente")

        from services.pagos_service.providers import NiubizClient
        niubiz = NiubizClient()
        return render_template("pago.html", cita=cita, niubiz_sdk_url=niubiz.sdk_url, niubiz_mode=niubiz.mode)

    @app.route("/retorno")
    def retorno_page():
        cita_id = request.args.get("cita_id")
        data, _ = pagos_client.get(f"/api/pagos/{cita_id}")
        pago = data.get("pago", {})

        # DEMO/temporal: si la cita es la que se acaba de crear en esta
        # sesion, se permite llegar aunque el pago figure "pendiente"
        # (la simulacion no llama al backend). En produccion real el
        # pago llega como "pagado" y el guard normal aplica igual.
        es_cita_pendiente = str(session.get("cita_pendiente_id") or "") == str(cita_id)
        if pago.get("estado_pago") != "pagado" and not es_cita_pendiente:
            return redirect(url_for("pago_page", cita_id=cita_id))

        # Flujo terminado (pago confirmado o demo): limpiar la cita pendiente.
        session.pop("cita_pendiente_id", None)

        cdata, _ = citas_client.get(f"/api/citas/{cita_id}")
        cita = cdata.get("cita", {})
        cita["monto"] = float(pago.get("monto") or 0)
        cita["metodo_pago"] = pago.get("metodo_pago", "")
        cita["referencia"] = pago.get("referencia")
        cita["transaccion_id"] = pago.get("transaccion_id")

        fecha_fmt = cita.get("fecha_cita", "")
        try:
            fecha_fmt = datetime.strptime(str(cita["fecha_cita"]), "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            pass

        return render_template("retorno.html", cita_id=cita_id, cita=cita, fecha_fmt=fecha_fmt)

    @app.route("/panel_admin", methods=["GET", "POST"])
    def panel_admin():
        if "usuario_id" not in session or session.get("rol") != "admin":
            return redirect(url_for("login"))

        if request.method == "POST":
            accion = request.form.get("accion")
            if accion == "registrar":
                nombre = request.form.get("nombre", "").strip()
                especialidad = request.form.get("especialidad", "").strip()
                correo = request.form.get("correo", "").strip()
                clave = request.form.get("clave", "").strip()
                precio = request.form.get("precio", "").strip()

                if nombre and especialidad and correo and clave:
                    # FASE 2: todo via HTTP (auth para el usuario, pacientes
                    # para terapeuta/especialidad). El hash de la clave lo
                    # hace auth_service.
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
                        # FASE 2: el hash de la clave lo hace auth_service.
                        auth_client.put(f"/api/auth/usuarios/{terapeuta['usuario_id']}", {"clave": nc})
                        flash("exito:Contrasena actualizada.")

            return redirect(url_for("panel_admin"))

        tdata, _ = pacientes_client.get("/api/terapeutas")
        medicos = tdata.get("terapeutas", [])
        edata, _ = pacientes_client.get("/api/especialidades")
        especialidades = edata.get("especialidades", [])
        udata, _ = auth_client.get("/api/auth/usuarios")
        usuarios = udata.get("usuarios", [])

        params = "?fecha=" + datetime.today().strftime("%Y-%m-%d") + "&estado=programada"
        cdata, _ = citas_client.get(f"/api/citas{params}")
        proximas_citas = cdata.get("citas", [])[:20]

        return render_template("paneladmin.html", medicos=medicos, proximas_citas=proximas_citas,
                               especialidades=especialidades, usuarios=usuarios)

    @app.route("/panel_admin/auditoria")
    def panel_admin_auditoria():
        if "usuario_id" not in session or session.get("rol") != "admin":
            return redirect(url_for("login"))

        filtros = {}
        for key in ("usuario_tipo", "accion", "fecha_desde", "fecha_hasta"):
            valor = (request.args.get(key) or "").strip()
            if valor:
                filtros[key] = valor

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

        return render_template("auditoria.html", logs=logs, filtros=filtros)

    @app.route("/panel_admin/cancelar_cita/<int:cita_id>", methods=["POST"])
    def admin_cancelar_cita(cita_id):
        if "usuario_id" not in session or session.get("rol") != "admin":
            return redirect(url_for("login"))
        citas_client.delete(f"/api/citas/{cita_id}")
        flash("exito:Cita cancelada.")
        return redirect(url_for("panel_admin"))

    @app.route("/pacientes")
    def pacientes_page():
        if "usuario_id" not in session or session.get("rol") != "admin":
            return redirect(url_for("login"))
        data, _ = pacientes_client.get("/api/pacientes")
        return render_template("pacientes.html", pacientes=data.get("pacientes", []))

    @app.route("/pacientes/<paciente_dni>")
    def detalle_paciente_page(paciente_dni):
        if "usuario_id" not in session or session.get("rol") != "admin":
            return redirect(url_for("login"))
        data, _ = pacientes_client.get(f"/api/pacientes/{paciente_dni}")
        paciente = data.get("paciente", {})
        historial = data.get("historial", [])
        paciente_id_val = paciente.get("id")

        paquetes, evaluaciones, consentimientos = [], [], []
        if paciente_id_val:
            pdata, _ = pacientes_client.get(f"/api/pacientes/{paciente_id_val}/paquetes")
            paquetes = pdata.get("paquetes", [])
            edata, _ = pacientes_client.get(f"/api/pacientes/{paciente_id_val}/evaluaciones")
            evaluaciones = edata.get("evaluaciones", [])
            cdata, _ = pacientes_client.get(f"/api/pacientes/{paciente_id_val}/consentimientos")
            consentimientos = cdata.get("consentimientos", [])

        return render_template("detalle_paciente.html", paciente=paciente,
                               historial=historial, paquetes=paquetes,
                               evaluaciones=evaluaciones, consentimientos=consentimientos)

    @app.route("/notas/<int:cita_id>", methods=["GET", "POST"])
    def notas_page(cita_id):
        if "usuario_id" not in session:
            return redirect(url_for("login"))

        cdata, _ = citas_client.get(f"/api/citas/{cita_id}")
        cita = cdata.get("cita", {})

        if request.method == "POST":
            nota = request.form.get("nota", "").strip()
            diagnostico = request.form.get("diagnostico", "").strip()
            notas_client.post(f"/api/notas/{cita_id}", {
                "nota": nota, "diagnostico": diagnostico,
                "terapeuta_id": None,
                "paciente_id": cita.get("paciente_id"),
            })
            flash("exito:Nota clinica guardada.")
            return redirect(url_for("notas_page", cita_id=cita_id))

        ndata, _ = notas_client.get(f"/api/notas/{cita_id}")
        return render_template("notas_cita.html", cita=cita, notas=ndata.get("notas", []))

    @app.route("/api/verificar_dni", methods=["POST"])
    def verificar_dni():
        dni = (request.json or {}).get("dni", "").strip()
        data, status = pacientes_client.post("/api/pacientes/buscar_dni", {"dni": dni})
        return jsonify(data), status

    @app.route("/api/estadisticas")
    def api_estadisticas():
        data, _ = citas_client.get("/api/citas/estadisticas")
        return jsonify(data)

    # Proxy publico de las pasarelas Yape/Plin (QR y consulta de estado).
    # El frontend de pago.html las invoca con ruta relativa al gateway
    # (same-origin), asi que se reenvian a pagos_service preservando el
    # cuerpo JSON y el codigo de estado. No toca el flujo de tarjeta/Niubiz.
    @app.route("/api/pagos/yape/iniciar", methods=["POST"])
    @app.route("/api/pagos/plin/iniciar", methods=["POST"])
    def proxy_pago_scan_iniciar():
        data, status = pagos_client.post(request.path, request.get_json() or {})
        return jsonify(data or {}), status

    @app.route("/api/pagos/yape/estado", methods=["POST"])
    @app.route("/api/pagos/plin/estado", methods=["POST"])
    def proxy_pago_scan_estado():
        data, status = pagos_client.post(request.path, request.get_json() or {})
        return jsonify(data or {}), status

    from services.audit_service.routes import audit_bp
    app.register_blueprint(audit_bp)

    return app
