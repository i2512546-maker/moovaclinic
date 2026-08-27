import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_bcrypt import Bcrypt
from datetime import datetime, timedelta
from shared.config import REDES_SOCIALES, SERVICE_URLS
from shared.service_client import auth_client, pacientes_client, citas_client, pagos_client, notas_client
from shared.db import db_connection

bcrypt = Bcrypt()


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = os.getenv("SECRET_KEY", os.urandom(32).hex())
    bcrypt.init_app(app)

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
        pacientes = data.get("citas", [])

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

        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE historial_citas SET descripcion=%s, estado='completada' WHERE id=%s",
                (descripcion, historial_id),
            )
            conn.commit()
        return redirect(url_for("interfaz", fecha=fecha))

    @app.route("/citas", methods=["GET", "POST"])
    def citas_page():
        data, _ = citas_client.get("/api/citas/terapeutas")
        terapeutas = data.get("terapeutas", [])

        if request.method == "POST":
            form_data = {k: request.form.get(k, "").strip() for k in
                         ["nombre", "apellido", "dni", "telefono", "medico_id", "fecha_cita", "metodo_pago"]}
            if not all(form_data.values()):
                flash("campos_vacios")
                return redirect(url_for("citas_page"))

            result, status = citas_client.post("/api/citas", form_data)
            if status == 201 and result.get("success"):
                return redirect(url_for("pago_page", cita_id=result["cita_id"]))
            else:
                flash(result.get("error", "Error al crear cita"))

        return render_template("citas.html", terapeutas=terapeutas)

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

        with db_connection() as conn:
            cursor = conn.cursor(dictionary=True)

            if request.method == "POST":
                accion = request.form.get("accion")
                if accion == "registrar":
                    nombre = request.form.get("nombre", "").strip()
                    especialidad = request.form.get("especialidad", "").strip()
                    correo = request.form.get("correo", "").strip()
                    clave = request.form.get("clave", "").strip()
                    precio = request.form.get("precio", "").strip()

                    if nombre and especialidad and correo and clave:
                        with db_connection() as conn2:
                            cur2 = conn2.cursor(dictionary=True)
                            cur2.execute("SELECT u.id FROM usuarios u WHERE u.nombre=%s", (nombre,))
                            if cur2.fetchone():
                                flash("Ya existe un terapeuta con ese nombre.")
                            else:
                                try:
                                    precio_num = float(precio) if precio else None
                                except ValueError:
                                    precio_num = None
                                telefono = request.form.get("telefono", "").strip()
                                clave_hash = bcrypt.generate_password_hash(clave).decode("utf-8")
                                cur2.execute("SELECT id FROM roles WHERE nombre='terapeuta'")
                                rol = cur2.fetchone()
                                cur2.execute(
                                    "INSERT INTO usuarios (nombre, correo, telefono, clave, rol_id) VALUES (%s,%s,%s,%s,%s)",
                                    (nombre, correo, telefono or None, clave_hash, rol["id"] if rol else 2),
                                )
                                conn2.commit()
                                usuario_id = cur2.lastrowid
                                cur2.execute("SELECT id FROM especialidades WHERE nombre=%s", (especialidad,))
                                esp = cur2.fetchone()
                                esp_id = esp["id"] if esp else None
                                cur2.execute("INSERT INTO terapeutas (usuario_id, especialidad_id, precio) VALUES (%s,%s,%s)",
                                             (usuario_id, esp_id, precio_num))
                                conn2.commit()
                                flash("exito:Terapeuta registrado correctamente.")
                    else:
                        flash("Completa todos los campos.")

                elif accion == "actualizar_precio":
                    mid = request.form.get("medico_id")
                    precio = request.form.get("precio", "").strip()
                    if mid and precio:
                        try:
                            cursor.execute("UPDATE terapeutas SET precio=%s WHERE id=%s", (float(precio), mid))
                            conn.commit()
                            flash("exito:Precio actualizado.")
                        except ValueError:
                            flash("Precio invalido.")

                elif accion == "eliminar":
                    mid = request.form.get("medico_id")
                    if mid:
                        cursor.execute("SELECT usuario_id FROM terapeutas WHERE id=%s", (mid,))
                        terapeuta = cursor.fetchone()
                        if terapeuta:
                            cursor.execute("UPDATE terapeutas SET activo=0 WHERE id=%s", (mid,))
                            if terapeuta.get("usuario_id"):
                                cursor.execute("UPDATE usuarios SET activo=0 WHERE id=%s", (terapeuta["usuario_id"],))
                            conn.commit()
                            flash("exito:Terapeuta desactivado.")

                elif accion == "reactivar":
                    mid = request.form.get("medico_id")
                    if mid:
                        cursor.execute("SELECT usuario_id FROM terapeutas WHERE id=%s", (mid,))
                        terapeuta = cursor.fetchone()
                        if terapeuta:
                            cursor.execute("UPDATE terapeutas SET activo=1 WHERE id=%s", (mid,))
                            if terapeuta.get("usuario_id"):
                                cursor.execute("UPDATE usuarios SET activo=1 WHERE id=%s", (terapeuta["usuario_id"],))
                            conn.commit()
                            flash("exito:Terapeuta reactivado.")

                elif accion == "cambiar_clave":
                    mid = request.form.get("medico_id")
                    nc = request.form.get("nueva_clave", "").strip()
                    if mid and nc:
                        cursor.execute("SELECT usuario_id FROM terapeutas WHERE id=%s", (mid,))
                        terapeuta = cursor.fetchone()
                        if terapeuta and terapeuta.get("usuario_id"):
                            h = bcrypt.generate_password_hash(nc).decode("utf-8")
                            cursor.execute("UPDATE usuarios SET clave=%s WHERE id=%s", (h, terapeuta["usuario_id"]))
                            conn.commit()
                            flash("exito:Contrasena actualizada.")

                return redirect(url_for("panel_admin"))

            cursor.execute(
                """SELECT t.id AS ID, u.nombre AS Nombre, u.telefono AS Telefono, t.precio, t.activo,
                          e.nombre AS Especialidad
                   FROM terapeutas t
                   JOIN usuarios u ON t.usuario_id = u.id
                   LEFT JOIN especialidades e ON t.especialidad_id = e.id
                   ORDER BY u.nombre""")
            medicos = cursor.fetchall()
            cursor.execute("SELECT id, nombre FROM especialidades WHERE activa=1 ORDER BY nombre")
            especialidades = cursor.fetchall()
            cursor.execute(
                """SELECT u.id, u.nombre, u.correo, r.nombre AS rol, u.activo, u.ultimo_acceso
                   FROM usuarios u JOIN roles r ON u.rol_id = r.id ORDER BY r.nombre, u.nombre""")
            usuarios = cursor.fetchall()

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

    return app
