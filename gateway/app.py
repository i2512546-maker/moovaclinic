import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import yaml
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
from flask_bcrypt import Bcrypt
from datetime import date, datetime
from shared.config import REDES_SOCIALES, SERVICE_URLS
from shared.service_client import auth_client, pacientes_client, citas_client, pagos_client, notas_client
from shared.audit import log_accion
from shared.proc import call_proc, call_proc_one, call_proc_execute

bcrypt = Bcrypt()


def _rehab_payload(form, paciente, usuario_id):
    """Construye el payload de historia clinica en rehabilitacion.
    Compartido por crear y editar para no duplicar los ~30 campos."""
    def _v(campo):
        return form.get(campo, "").strip()

    return {
        "nombres": paciente.get("nombre") or form.get("nombres", ""),
        "apellidos": paciente.get("apellido") or form.get("apellidos", ""),
        "fecha_cita": _v("fecha_cita") or date.today().strftime("%Y-%m-%d"),
        "hora_ingreso": _v("hora_ingreso") or None,
        "hora_salida": _v("hora_salida") or None,
        "numero_expediente": _v("numero_expediente") or None,
        "cama_cubiculo": _v("cama_cubiculo") or None,
        "edad": _v("edad") or None,
        "sexo": _v("sexo") or None,
        "fecha_nacimiento": _v("fecha_nacimiento") or None,
        "domicilio": _v("domicilio") or None,
        "telefono": _v("telefono") or None,
        "email": _v("email") or None,
        "seguro": _v("seguro") or None,
        "deporte": _v("deporte") or None,
        "posicion": _v("posicion") or None,
        "antiguedad_practica": _v("antiguedad_practica") or None,
        "nivel_competitivo": _v("nivel_competitivo") or None,
        "motivo_consulta": _v("motivo_consulta") or None,
        "diagnostico_medico": _v("diagnostico_medico") or None,
        "mecanismo_lesion": _v("mecanismo_lesion") or None,
        "tratamientos_previos": _v("tratamientos_previos") or None,
        "area_tipo": _v("area_tipo") or None,
        "profesional": _v("profesional") or None,
        "peso": _v("peso") or None,
        "talla": _v("talla") or None,
        "antecedentes": _v("antecedentes") or None,
        "examen_fisico": _v("examen_fisico") or None,
        "tratamiento": _v("tratamiento") or None,
        "observaciones": _v("observaciones") or None,
        "evolucion": _v("evolucion") or None,
        "estado": _v("estado") or "registrada",
        "proxima_cita": _v("proxima_cita") or None,
        "registrado_por": usuario_id,
    }


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
        if specs:
            Swagger(app, template=specs)
        else:
            Swagger(app)
    except Exception:
        pass

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

        # Flechas del calendario: saltan entre fechas que SÍ tienen pacientes
        # (citas programadas), ocultando los días vacíos en la navegación.
        anterior = None
        siguiente = None
        try:
            todas, _ = citas_client.get("/api/citas?estado=programada")
            fechas = sorted({str(c.get("fecha_cita") or "")[:10] for c in todas.get("citas", [])})
            for f in reversed(fechas):
                if f < fecha_str:
                    anterior = f
                    break
            for f in fechas:
                if f > fecha_str:
                    siguiente = f
                    break
        except Exception:
            pass

        dias = ["Domingo", "Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado"]
        dia_semana = dias[fecha_obj.weekday() + 1 if fecha_obj.weekday() < 6 else 0]
        fecha_display = fecha_obj.strftime("%d/%m/%Y")
        es_hoy = fecha_str == datetime.today().strftime("%Y-%m-%d")
        es_admin = session.get("rol") == "admin"

        params = f"?fecha={fecha_str}&estado=programada"
        data, _ = citas_client.get(f"/api/citas{params}")
        pacientes = data.get("citas", [])

        return render_template(
            "interfaz.html", pacientes=pacientes,
            fecha_actual=fecha_str, fecha_display=fecha_display,
            dia_semana=dia_semana, anterior=anterior, siguiente=siguiente,
            es_hoy=es_hoy, nombre_usuario=session.get("usuario_nombre"), es_admin=es_admin,
        )

    @app.route("/guardar_descripcion", methods=["POST"])
    def guardar_descripcion():
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        historial_id = request.form.get("historial_id")
        descripcion = request.form.get("descripcion", "").strip()
        fecha = request.form.get("fecha", datetime.today().strftime("%Y-%m-%d"))

        call_proc_execute("sp_completar_cita", (historial_id, descripcion))
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
        data, _ = citas_client.get("/api/citas/terapeutas")
        terapeutas = data.get("terapeutas", [])
        sdata, _ = pacientes_client.get("/api/servicios")
        servicios = sdata.get("servicios", [])

        if request.method == "POST":
            form_data = {k: request.form.get(k, "").strip() for k in
                         ["nombre", "apellido", "dni", "telefono", "medico_id", "fecha_cita", "metodo_pago", "servicio_id"]}
            if not all(form_data.values()):
                flash("campos_vacios")
                return redirect(url_for("citas_page"))

            result, status = citas_client.post("/api/citas", form_data)
            if status == 201 and result.get("success"):
                return redirect(url_for("pago_page", cita_id=result["cita_id"]))
            else:
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

        if request.method == "POST":
            accion = request.form.get("accion")
            if accion == "solicitar":
                dni = request.form.get("dni", "").strip()
                result, status = citas_client.post("/api/citas/otp/solicitar", {"dni": dni, "accion": "modificar"})
                if status == 200 and result.get("success"):
                    paso, dni_val, tel_mask = "verificar", dni, result["tel_mask"]
                else:
                    error_msg = result.get("error", "Error.")
            elif accion == "verificar":
                dni = request.form.get("dni", "").strip()
                otp = request.form.get("otp", "").strip()
                result, _ = citas_client.post("/api/citas/otp/verificar", {"dni": dni, "otp": otp, "accion": "modificar"})
                r = result.get("resultado", "")
                if r == "ok":
                    cdata, _ = citas_client.get(f"/api/citas?dni={dni}&estado=programada")
                    citas_encontradas = cdata.get("citas", [])
                else:
                    mensajes = {"expirado": "El codigo expiro.", "agotado": "Intentos agotados.", "no_existe": "Solicita uno nuevo."}
                    error_msg = mensajes.get(r, f"Codigo incorrecto. Quedan {result.get('restantes', '?')} intento(s).")
                    paso, dni_val = "verificar", dni
            elif accion == "guardar":
                cita_id = request.form.get("cita_id")
                nueva_fecha = request.form.get("fecha_cita", "").strip()
                nuevo_medico = request.form.get("medico_id", "").strip()
                result, status = citas_client.put(f"/api/citas/{cita_id}", {"fecha_cita": nueva_fecha, "medico_id": nuevo_medico})
                if status == 200:
                    flash("exito:Cita modificada correctamente.")
                else:
                    flash(result.get("error", "Error al modificar."))

        return render_template("modificar_cita.html", terapeutas=terapeutas, citas=citas_encontradas,
                               paso=paso, dni=dni_val, tel_mask=tel_mask, error=error_msg)

    @app.route("/citas/cancelar", methods=["GET", "POST"])
    def cancelar_cita_page():
        citas_encontradas = None
        paso = None
        dni_val = ""
        tel_mask = ""
        error_msg = None

        if request.method == "POST":
            accion = request.form.get("accion")
            if accion == "solicitar":
                dni = request.form.get("dni", "").strip()
                result, status = citas_client.post("/api/citas/otp/solicitar", {"dni": dni, "accion": "cancelar"})
                if status == 200 and result.get("success"):
                    paso, dni_val, tel_mask = "verificar", dni, result["tel_mask"]
                else:
                    error_msg = result.get("error", "Error.")
            elif accion == "verificar":
                dni = request.form.get("dni", "").strip()
                otp = request.form.get("otp", "").strip()
                result, _ = citas_client.post("/api/citas/otp/verificar", {"dni": dni, "otp": otp, "accion": "cancelar"})
                r = result.get("resultado", "")
                if r == "ok":
                    cdata, _ = citas_client.get(f"/api/citas?dni={dni}&estado=programada")
                    citas_encontradas = cdata.get("citas", [])
                else:
                    mensajes = {"expirado": "El codigo expiro.", "agotado": "Intentos agotados.", "no_existe": "Solicita uno nuevo."}
                    error_msg = mensajes.get(r, f"Codigo incorrecto. Quedan {result.get('restantes', '?')} intento(s).")
                    paso, dni_val = "verificar", dni
            elif accion == "confirmar":
                cita_id = request.form.get("cita_id")
                result, _ = citas_client.delete(f"/api/citas/{cita_id}")
                flash("exito:Tu cita ha sido cancelada correctamente.")

        return render_template("cancelar_cita.html", citas=citas_encontradas,
                               paso=paso, dni=dni_val, tel_mask=tel_mask, error=error_msg)

    @app.route("/pago")
    def pago_page():
        cita_id = request.args.get("cita_id")
        data, _ = pagos_client.get(f"/api/pagos/{cita_id}")
        pago = data.get("pago", {})

        cdata, _ = citas_client.get(f"/api/citas/{cita_id}")
        cita = cdata.get("cita", {})

        if pago.get("estado_pago") == "pagado":
            return redirect(url_for("retorno_page", cita_id=cita_id))

        cita["monto"] = pago.get("monto", 0)
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

        if pago.get("estado_pago") != "pagado":
            return redirect(url_for("pago_page", cita_id=cita_id))

        cdata, _ = citas_client.get(f"/api/citas/{cita_id}")
        cita = cdata.get("cita", {})
        cita["monto"] = pago.get("monto", 0)
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
                    if call_proc_one("sp_obtener_usuario_por_nombre", (nombre,)):
                        flash("Ya existe un terapeuta con ese nombre.")
                    else:
                        try:
                            precio_num = float(precio) if precio else None
                        except ValueError:
                            precio_num = None
                        telefono = request.form.get("telefono", "").strip()
                        clave_hash = bcrypt.generate_password_hash(clave).decode("utf-8")
                        rol = call_proc_one("sp_obtener_rol_id_terapeuta")
                        rol_id = rol["id"] if rol else 2
                        creado = call_proc_one("sp_crear_usuario_admin", (
                            nombre, correo, telefono or None, clave_hash, rol_id,
                        ))
                        usuario_id = creado["id"] if creado else None
                        esp = call_proc_one("sp_obtener_especialidad_id", (especialidad,))
                        esp_id = esp["id"] if esp else None
                        call_proc_execute("sp_crear_terapeuta", (usuario_id, esp_id, precio_num))
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
                        call_proc_execute("sp_actualizar_precio", (mid, float(precio)))
                        flash("exito:Precio actualizado.")
                    except ValueError:
                        flash("Precio invalido.")

            elif accion == "eliminar":
                mid = request.form.get("medico_id")
                if mid:
                    terapeuta = call_proc_one("sp_obtener_usuario_id_terapeuta", (mid,))
                    if terapeuta:
                        call_proc_execute("sp_set_terapeuta_activo", (mid, 0))
                        if terapeuta.get("usuario_id"):
                            call_proc_execute("sp_set_usuario_activo", (terapeuta["usuario_id"], 0))
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
                    terapeuta = call_proc_one("sp_obtener_usuario_id_terapeuta", (mid,))
                    if terapeuta:
                        call_proc_execute("sp_set_terapeuta_activo", (mid, 1))
                        if terapeuta.get("usuario_id"):
                            call_proc_execute("sp_set_usuario_activo", (terapeuta["usuario_id"], 1))
                        flash("exito:Terapeuta reactivado.")

            elif accion == "cambiar_clave":
                mid = request.form.get("medico_id")
                nc = request.form.get("nueva_clave", "").strip()
                if mid and nc:
                    terapeuta = call_proc_one("sp_obtener_usuario_id_terapeuta", (mid,))
                    if terapeuta and terapeuta.get("usuario_id"):
                        h = bcrypt.generate_password_hash(nc).decode("utf-8")
                        call_proc_execute("sp_cambiar_clave_usuario", (terapeuta["usuario_id"], h))
                        flash("exito:Contrasena actualizada.")

            return redirect(url_for("panel_admin"))

        medicos = call_proc("sp_consultar_medicos_admin")
        especialidades = call_proc("sp_listar_especialidades")
        usuarios = call_proc("sp_listar_usuarios")

        params = "?fecha=" + datetime.today().strftime("%Y-%m-%d") + "&estado=programada"
        cdata, _ = citas_client.get(f"/api/citas{params}")
        proximas_citas = cdata.get("citas", [])

        return render_template("paneladmin.html", medicos=medicos, proximas_citas=proximas_citas,
                               especialidades=especialidades, usuarios=usuarios)

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

        data = {}
        rehab = {}
        try:
            d, st = pacientes_client.get(f"/api/pacientes/{paciente_dni}/historial")
            if st == 200:
                data = d
        except Exception:
            pass
        try:
            r, st = pacientes_client.get(f"/api/rehabilitaciones/{paciente_dni}")
            if st == 200:
                rehab = r
        except Exception:
            pass

        return render_template("detalle_paciente.html",
                               paciente=data.get("paciente", {}),
                               historial=data.get("historial", []),
                               paquetes=data.get("paquetes", []),
                               evaluaciones=data.get("evaluaciones", []),
                               consentimientos=data.get("consentimientos", []),
                               rehabilitaciones=sorted(rehab.get("rehabilitaciones", []),
                                                      key=lambda c: str(c.get("fecha_cita") or "")),
                               rehab_resumen=rehab.get("resumen", {}),
                               terapeutas=rehab.get("terapeutas", []),
                               areas=rehab.get("areas", []))

    @app.route("/pacientes/<paciente_dni>/rehabilitacion", methods=["GET", "POST"])
    def registro_rehabilitacion_page(paciente_dni):
        if "usuario_id" not in session or session.get("rol") != "admin":
            return redirect(url_for("login"))

        # Cargar datos del paciente (endpoint base, siempre disponible)
        data = {}
        try:
            d, st = pacientes_client.get(f"/api/pacientes/{paciente_dni}")
            if st == 200:
                data = d
        except Exception:
            pass

        paciente = data.get("paciente", {})
        if not paciente:
            flash("Paciente no encontrado.")
            return redirect(url_for("pacientes_page"))

        # Cargar estado de rehabilitaciones (opcional, no debe impedir abrir el formulario)
        rehab = {}
        try:
            r, st = pacientes_client.get(f"/api/rehabilitaciones/{paciente_dni}")
            if st == 200:
                rehab = r
        except Exception:
            pass

        resumen = rehab.get("resumen", {}) or {}
        total = int(resumen.get("total_registradas") or resumen.get("ultima_cita") or 0)
        try:
            ultima = int(resumen.get("ultima_cita") or 0)
        except (TypeError, ValueError):
            ultima = 0
        proxima_cita = ultima + 1

        if request.method == "POST":
            form = request.form
            motivo = form.get("motivo_consulta", "").strip()
            diag = form.get("diagnostico_medico", "").strip()
            if not motivo and not diag:
                flash("Completa al menos el motivo de consulta o el diagnostico medico.")
                return redirect(url_for("registro_rehabilitacion_page", paciente_dni=paciente_dni))

            payload = _rehab_payload(form, paciente, session.get("usuario_id"))
            payload["numero_cita"] = proxima_cita

            try:
                result, status = pacientes_client.post(
                    f"/api/rehabilitaciones/{paciente_dni}", payload)
                if status == 201 and result.get("success"):
                    flash("exito:Cita {} de rehabilitacion registrada correctamente.".format(result.get("numero_cita")))
                    return redirect(url_for("detalle_paciente_page", paciente_dni=paciente_dni))
                flash(result.get("error", "No se pudo registrar la rehabilitacion."))
            except Exception:
                flash("Error de conexion con el servicio de pacientes.")

        return render_template("registro_rehabilitacion.html",
                               paciente=paciente,
                               total_citas=total,
                               ultima_cita=ultima,
                               proxima_cita=proxima_cita,
                               terapeutas=rehab.get("terapeutas", []),
                               areas=rehab.get("areas", []),
                               rehabilitaciones=rehab.get("rehabilitaciones", []),
                               cita={},
                               modo="crear")

    @app.route("/pacientes/<paciente_dni>/rehabilitacion/<int:cita_id>/editar", methods=["GET", "POST"])
    def editar_rehabilitacion_page(paciente_dni, cita_id):
        if "usuario_id" not in session or session.get("rol") != "admin":
            return redirect(url_for("login"))

        # Obtener la cita a editar
        data = {}
        try:
            d, st = pacientes_client.get(
                f"/api/rehabilitaciones/{paciente_dni}/{cita_id}")
            if st == 200:
                data = d
        except Exception:
            pass

        paciente = data.get("paciente", {})

        info = {}
        st2 = 0
        try:
            info, st2 = pacientes_client.get(f"/api/rehabilitaciones/{paciente_dni}")
            terapeutas = (info or {}).get("terapeutas", []) if st2 == 200 else []
            areas = (info or {}).get("areas", []) if st2 == 200 else []
        except Exception:
            terapeutas, areas = [], []

        cita = data.get("cita", {})
        if not cita or not paciente:
            flash("Cita no encontrada.")
            return redirect(url_for("detalle_paciente_page", paciente_dni=paciente_dni))

        if request.method == "POST":
            form = request.form
            motivo = form.get("motivo_consulta", "").strip()
            diag = form.get("diagnostico_medico", "").strip()
            if not motivo and not diag:
                flash("Completa al menos el motivo de consulta o el diagnostico medico.")
                return redirect(url_for("editar_rehabilitacion_page", paciente_dni=paciente_dni, cita_id=cita_id))

            payload = _rehab_payload(form, paciente, session.get("usuario_id"))

            try:
                result, status = pacientes_client.put(
                    f"/api/rehabilitaciones/{paciente_dni}/{cita_id}", payload)
                if status == 200 and result.get("success"):
                    flash("exito:Cita {} actualizada correctamente.".format(cita.get("numero_cita")))
                    return redirect(url_for("detalle_paciente_page", paciente_dni=paciente_dni))
                flash(result.get("error", "No se pudo actualizar la cita."))
            except Exception:
                flash("Error de conexion con el servicio de pacientes.")

        total = 0
        ultima = 0
        try:
            resumen = (info or {}).get("resumen", {}) if st2 == 200 else {}
            ultima = int(resumen.get("ultima_cita") or 0)
            total = int(resumen.get("total_registradas") or ultima)
        except (TypeError, ValueError):
            ultima, total = 0, 0

        return render_template("registro_rehabilitacion.html",
                               paciente=paciente,
                               cita=cita,
                               modo="editar",
                               proxima_cita=int(cita.get("numero_cita") or ultima + 1),
                               ultima_cita=ultima,
                               total_citas=total,
                               terapeutas=terapeutas,
                               areas=areas,
                               rehabilitaciones=[])

    @app.route("/pacientes/<paciente_dni>/citas/<int:cita_id>")
    def ver_cita_page(paciente_dni, cita_id):
        if "usuario_id" not in session or session.get("rol") != "admin":
            return redirect(url_for("login"))

        data = {}
        try:
            d, st = pacientes_client.get(
                f"/api/rehabilitaciones/{paciente_dni}/{cita_id}")
            if st == 200:
                data = d
        except Exception:
            pass

        paciente = data.get("paciente", {})
        cita = data.get("cita", {})
        if not cita or not paciente:
            flash("Cita no encontrada.")
            return redirect(url_for("detalle_paciente_page", paciente_dni=paciente_dni))

        return render_template("detalle_cita.html", paciente=paciente, cita=cita)

    @app.route("/pacientes/<paciente_dni>/exportar")
    def exportar_historia_page(paciente_dni):
        if "usuario_id" not in session or session.get("rol") != "admin":
            return redirect(url_for("login"))

        formato = request.args.get("formato", "html")
        cita_id = request.args.get("cita_id")
        alcance = request.args.get("alcance", "todo")  # todo | una

        # Datos del paciente + historial
        data = {}
        try:
            d, st = pacientes_client.get(f"/api/rehabilitaciones/{paciente_dni}")
            if st == 200:
                data = d
        except Exception:
            pass

        paciente = data.get("paciente", {})
        if not paciente:
            flash("Paciente no encontrado.")
            return redirect(url_for("pacientes_page"))

        citas = list(data.get("rehabilitaciones", []))
        cita = None
        if alcance == "una" and cita_id:
            try:
                cita_id = int(cita_id)
            except (TypeError, ValueError):
                cita_id = None
            if cita_id is not None:
                cita = next((c for c in citas if c.get("id") == cita_id), None)
                if cita:
                    citas = [cita]

        citas = sorted(citas, key=lambda c: str(c.get("fecha_cita") or ""))

        if formato == "pdf":
            url = SERVICE_URLS["pacientes"] + "/api/pacientes/{}/historia_rehab_pdf".format(paciente_dni)
            if alcance == "una" and cita_id:
                url += "?cita_id={}".format(cita_id)
            try:
                resp = requests.get(url, timeout=30)
            except Exception:
                flash("No se pudo generar el PDF.")
                return redirect(url_for("detalle_paciente_page", paciente_dni=paciente_dni))
            if resp.status_code != 200:
                flash("No se pudo generar el PDF.")
                return redirect(url_for("detalle_paciente_page", paciente_dni=paciente_dni))
            nombre_archivo = "historia_rehab_{}.pdf".format(paciente_dni)
            return Response(
                resp.content,
                mimetype="application/pdf",
                headers={"Content-Disposition": "attachment; filename={}".format(nombre_archivo)},
            )

        html = render_template("export_historia.html",
                               paciente=paciente,
                               citas=citas,
                               alcance=alcance,
                               generar_fecha=datetime.now().strftime("%d/%m/%Y %H:%M"))

        if formato == "word":
            nombre = "historia_rehab_{}.doc".format(paciente_dni)
            return Response(
                html,
                mimetype="application/msword",
                headers={"Content-Disposition": "attachment; filename={}".format(nombre)},
            )

        # formato html: vista imprimible
        return render_template("export_historia.html",
                               paciente=paciente,
                               citas=citas,
                               alcance=alcance,
                               imprimir=True,
                               generar_fecha=datetime.now().strftime("%d/%m/%Y %H:%M"))

    @app.route("/pacientes/<int:paciente_id>/pdf")
    def ficha_clinica_pdf(paciente_id):
        if "usuario_id" not in session or session.get("rol") != "admin":
            return redirect(url_for("login"))
        try:
            resp = requests.get(
                SERVICE_URLS["pacientes"] + "/api/pacientes/{}/pdf".format(paciente_id),
                timeout=30,
            )
        except Exception:
            flash("No se pudo generar la ficha PDF.")
            return redirect(url_for("pacientes_page"))
        if resp.status_code != 200:
            flash("No se pudo generar la ficha PDF.")
            return redirect(url_for("pacientes_page"))
        cd = resp.headers.get("Content-Disposition", "attachment; filename=ficha_clinica.pdf")
        return Response(resp.content, mimetype="application/pdf",
                        headers={"Content-Disposition": cd})

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

    @app.route("/api/rehabilitaciones/<paciente_dni>", methods=["GET"])
    def api_rehabilitaciones(paciente_dni):
        data, status = pacientes_client.get(f"/api/rehabilitaciones/{paciente_dni}")
        return jsonify(data), status

    @app.route("/api/rehabilitaciones/<paciente_dni>", methods=["POST"])
    def api_crear_rehabilitacion(paciente_dni):
        data, status = pacientes_client.post(f"/api/rehabilitaciones/{paciente_dni}", request.get_json() or {})
        return jsonify(data), status

    @app.route("/api/estadisticas")
    def api_estadisticas():
        data, _ = citas_client.get("/api/citas/estadisticas")
        return jsonify(data)

    return app
