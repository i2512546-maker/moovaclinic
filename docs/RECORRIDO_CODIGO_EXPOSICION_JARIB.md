# MOOVA Clinic: recorrido del código para la sustentación de Jarib

**Objetivo:** abrir el repositorio delante del jurado y explicar fragmentos concretos: qué reciben, qué validan, qué llaman, qué guardan, qué devuelven y por qué están escritos así. Esta guía se basa en archivos consultados de la rama main.

## Cómo presentar un fragmento

Para cada bloque, explica: 1) archivo y función; 2) entrada; 3) validación; 4) operación; 5) respuesta; 6) razón de diseño; 7) limitación. No leas el código en voz alta: señala líneas y explica su propósito.

---

## 1. Crear una cita — el fragmento principal

**Abre:** services/citas_service/routes.py  
**Busca:** def crear_cita() (POST /api/citas).

### A. Recibir y validar los campos obligatorios

~~~python
@citas_bp.route("/api/citas", methods=["POST"])
def crear_cita():
    data = request.get_json() or {}
    for campo in [
        "nombre", "apellido", "dni", "telefono", "medico_id", "fecha_cita",
    ]:
        if not data.get(campo):
            return jsonify({"error": f"Campo requerido: {campo}"}), 400
~~~

**Qué decir:** “Esta función atiende una petición POST para registrar una cita. Los datos llegan en JSON y se guardan en data. Antes de consultar la base, recorro los campos indispensables. Si falta uno, devuelvo 400, que significa que la petición está incompleta o no es válida. Así no intento crear una cita con información faltante.”

**Cómo funciona:** el decorador conecta URL y método con la función; get_json lee el cuerpo; data.get consulta el campo; jsonify forma una respuesta JSON; 400 es un error de entrada, no un error interno.

**Si preguntan por qué no basta el formulario:** “El navegador se puede manipular o se puede llamar directamente a la API. El backend debe validar por su cuenta; el frontend mejora la experiencia, pero no es la autoridad de seguridad.”

### B. Validar formato de datos y fecha

~~~python
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
~~~

**Qué decir:** “La función reutilizable valida los datos personales; strip elimina espacios sobrantes. Luego convierto la fecha al formato año-mes-día. Si no se puede interpretar, devuelvo 400; si es anterior a hoy en Lima, también la rechazo. try/except evita que una fecha mal escrita derribe la ruta.”

**Diferencia clave:** formato válido no significa regla de negocio válida. Una fecha puede estar bien escrita y aun así ser pasada.

### C. Comprobar disponibilidad

~~~python
try:
    if not medico_disponible(data["medico_id"], data["fecha_cita"]):
        return jsonify({"error": "El medico ya tiene una cita ese dia"}), 409
except Exception as exc:
    current_app.logger.error(
        "[crear_cita] Error en sp_medico_disponible: %s: %s",
        type(exc).__name__, exc,
    )
    return jsonify({"error": "No se pudo procesar la solicitud, intenta de nuevo"}), 500
~~~

**Qué decir:** “Antes de guardar vuelvo a comprobar la disponibilidad en el servidor. Si ese especialista ya tiene una cita ese día, devuelvo 409, que significa conflicto con el estado actual. Si falla la consulta de base de datos, guardo el detalle técnico en el log y devuelvo un mensaje general con 500.”

**Códigos HTTP:** 400 datos inválidos; 404 recurso inexistente; 409 conflicto; 500 error del servidor; 502 dependencia interna no disponible.

**Si preguntan por dos reservas simultáneas:** “El calendario puede mostrar información desactualizada. Por eso el backend vuelve a comprobar la regla y usa el procedimiento de base de datos. La regla actual es una cita por especialista por día; no es todavía un sistema completo de bloques horarios.”

### D. Buscar o crear al paciente

~~~python
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
~~~

**Qué decir:** “El módulo de citas pregunta al módulo de pacientes si el DNI ya existe. Si existe, reutiliza su ID para no duplicar el registro. Si no, solicita crear un paciente mínimo. La cita se relaciona usando el ID interno del paciente, no solo el DNI escrito.”

**Si preguntan por qué ID y DNI:** el DNI sirve para localizar a la persona; el paciente_id es la clave interna que relaciona registros de citas y pagos.

**Detalle que debes conocer:** el código actual trata cualquier estado distinto de 200 como motivo para intentar crear el paciente. Una mejora sería distinguir explícitamente un 404 real de errores técnicos 500/502, para no intentar crear cuando el servicio falló.

### E. Crear la cita y dejar auditoría

~~~python
cita = call_proc_one(
    "sp_crear_cita",
    (paciente_id, data["medico_id"], servicio_id, data["fecha_cita"], hora_cita)
)
cita_id = cita["id"] if cita else None

log_accion(
    accion="crear_cita",
    tabla_afectada="historial_citas",
    registro_id=cita_id,
    detalle=f"Cita creada para paciente_id={paciente_id}, medico_id={data['medico_id']}, fecha={data['fecha_cita']}, hora={hora_cita or 'sin hora'}",
    ip_origen=request.remote_addr,
    entidad_tipo="paciente",
    entidad_id=paciente_id,
)
~~~

**Qué decir:** “Con el ID del paciente ejecuto el procedimiento almacenado sp_crear_cita y le paso los valores como parámetros. Recupero el ID generado y registro la acción con log_accion. El procedimiento encapsula la operación SQL; la auditoría deja trazabilidad de la creación.”

**Qué es un procedimiento almacenado:** una rutina SQL guardada en MySQL que el backend invoca por nombre y parámetros. El proyecto centraliza así la lógica de datos en vez de escribir consultas SQL en cada ruta.

**No digas:** “La auditoría hace imposible alterar los datos”. La auditoría ayuda a rastrear acciones; su resistencia a cambios depende también de permisos y diseño de base de datos.

### F. Anticipo: crear registro no es cobrar

El código obtiene el precio del terapeuta y calcula:

~~~python
costo = float(medico.get("precio") or 0)
anticipo = round(costo / 2, 2) if costo > 0 else 0.0
~~~

Después solicita al módulo de pagos crear el registro:

~~~python
pago_data, pago_status = pagos_client.post("/api/pagos/anticipo", {
    "cita_id": cita_id,
    "paciente_id": paciente_id,
    "monto": anticipo,
    "metodo_pago": metodo_pago,
})
~~~

**Qué decir:** “Si el precio es mayor que cero, calculo el 50 % como anticipo y lo redondeo a dos decimales. Luego envío el ID de la cita, paciente, monto y método al módulo de pagos. Crear un pago pendiente no significa que el dinero ya se haya cobrado: son estados distintos.”

---

## 2. Cómo se conectan los módulos — shared/service_client.py

**Abre:** shared/service_client.py y busca _dispatch.

~~~python
def _dispatch(self, method, path, json_data=None, timeout=None, **kwargs):
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("La ruta del servicio debe comenzar con '/'.")

    app = self._get_app()
    headers = dict(self.headers)
    headers.update(kwargs.pop("headers", {}) or {})
    params = kwargs.pop("params", None)
    if params is not None:
        kwargs.setdefault("query_string", params)

    with app.app_context():
        with app.test_client(use_cookies=False) as client:
            response = client.open(
                f"/_internal{path}",
                method=method,
                json=json_data,
                headers=headers,
                environ_overrides={"moova.interno": True},
                **kwargs,
            )
    return response.get_json(silent=True), response.status_code
~~~

**Qué decir:** “Este archivo permite que un módulo llame a otro mediante una interfaz parecida a HTTP, pero en la arquitectura actual el despacho ocurre dentro de la misma aplicación Flask. Se agrega el prefijo /_internal, se envía el método y el JSON, y se devuelve la respuesta junto con el código HTTP. Por eso es un monolito modular, no seis servidores separados.”

**Por qué existe:** citas solicita datos a pacientes sin importar directamente toda su lógica de base de datos; cada módulo conserva su responsabilidad.

**X-Api-Key:** el cliente agrega esa cabecera para identificar llamadas internas. No debe ponerse en el frontend ni publicarse.

**Si preguntan por test_client:** “Flask permite despachar peticiones contra la aplicación sin abrir un socket de red. Aquí se usa como mecanismo de llamada interna; el nombre no significa que la aplicación desplegada sea solo una prueba.”

**Ventaja:** menos complejidad de comunicación y despliegue. **Desventaja:** los módulos no escalan independientemente y un problema del proceso puede afectar a toda la aplicación.

---

## 3. Cómo Python llama a MySQL — shared/proc.py

**Abre:** shared/proc.py.

~~~python
def call_proc(proc_name, params=(), dictionary=True, fetch=True, commit=True, db_name=None):
    return _run(proc_name, params, dictionary, fetch, commit, db_name=db_name)

def call_proc_one(proc_name, params=(), dictionary=True, db_name=None):
    rows = _run(proc_name, params, dictionary, fetch=True, commit=True, db_name=db_name)
    return rows[0] if rows else None

def call_proc_execute(proc_name, params=(), db_name=None):
    return _run(proc_name, params, dictionary=False, fetch=False, commit=True, drain=True, db_name=db_name)
~~~

**Qué decir:** “Este helper centraliza las llamadas a procedimientos almacenados. call_proc devuelve una lista de filas; call_proc_one devuelve la primera fila o None; call_proc_execute sirve para operaciones de escritura que no necesitan devolver registros.”

**Ejemplos del repo:** sp_crear_cita necesita devolver el ID; sp_listar_citas devuelve una lista; sp_actualizar_ultimo_acceso ejecuta una actualización.

**Por qué pasar params:** los valores se pasan como argumentos del procedimiento en vez de interpolarse dentro de una cadena SQL construida con datos del usuario.

**Por qué commit:** confirma cambios de la operación. Si varios pasos deben ser atómicos juntos, hay que diseñar y comprobar explícitamente la transacción y el tratamiento de errores.

**No exageres:** usar procedimientos almacenados no elimina automáticamente todo riesgo SQL; también deben estar escritos de forma segura.

---

## 4. Integración externa y privacidad — APIPERU

**Abre:** services/pacientes_service/routes.py; busca _resumen_dni y buscar_dni.

~~~python
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
                resumen = _resumen_dni(api_data)
                if resumen["nombres"]:
                    return jsonify({"success": True, "data": resumen})
    except Exception as exc:
        current_app.logger.error(
            "[buscar_dni] Error consultando APIPERU (dni=%s): %s: %s",
            dni, type(exc).__name__, exc,
        )
    return jsonify({"success": False, "error": "DNI no encontrado"}), 404
~~~

**Qué decir:** “La ruta comprueba que el DNI tenga ocho dígitos y consulta APIPERU con un timeout de cinco segundos. El proveedor puede devolver más datos personales de los que necesita el formulario. _resumen_dni filtra la respuesta para devolver solo nombres y apellidos.”

**Por qué:** minimizar datos reduce exposición innecesaria. Si el formulario solo necesita autocompletar nombre y apellidos, no necesita recibir dirección, teléfonos, ubigeo y otros datos.

**Limitación real:** actualmente un fallo externo puede terminar con la misma respuesta 404 que un DNI no encontrado. Sería más claro devolver 502 cuando el proveedor no está disponible y reservar 404 para una consulta exitosa sin resultado.

**Seguridad:** el token de APIPERU debe estar en variables de entorno, no en el frontend ni en el repositorio.

---

## 5. Contraseñas — services/auth_service/routes.py

Busca login() y crear_usuario().

~~~python
usuario = call_proc_one("sp_login", (correo,))

if not usuario or not bcrypt.check_password_hash(usuario["clave"], clave):
    return jsonify({"error": "Correo o contrasena incorrectos."}), 401
~~~

**Qué decir:** “Busco el usuario por correo. Si no existe o la contraseña no coincide con el hash guardado, respondo 401. Uso el mismo mensaje para ambos casos para no revelar si un correo está registrado.”

Al crear usuario:

~~~python
clave_hash = bcrypt.generate_password_hash(clave).decode("utf-8")
~~~

“En lugar de guardar la contraseña legible, bcrypt genera un hash para comprobarla después. En el login, check_password_hash compara la contraseña ingresada con ese hash.”

**Precisión:** un hash no es cifrado reversible; no se descifra para recuperar la contraseña.

**Limitación:** el contador de intentos de login descrito en la guía está en memoria. Puede reiniciarse con el proceso y no compartirse entre workers. Una mejora sería persistirlo en un almacenamiento compartido.

---

## 6. OTP y autorización de la cita — gateway/app.py

Busca _otp_vigente, _dni_verificado y _cita_pertenece_al_dni.

~~~python
def _otp_vigente(dni, accion, ahora=None):
    verificacion = (session.get("otp_verificado") or {}).get(accion)
    if not verificacion:
        return False
    if str(verificacion.get("dni") or "") != str(dni or ""):
        return False
    ts = verificacion.get("ts") or 0
    transcurrido = (time.time() if ahora is None else ahora) - ts
    return 0 <= transcurrido <= OTP_SESION_MIN * 60
~~~

**Qué decir:** “Esta función no envía el código; verifica si una validación previa sigue vigente. Comprueba que exista el sello, que corresponda al mismo DNI y que no haya caducado.”

Después muestra:

~~~python
def _cita_pertenece_al_dni(dni, cita_id):
    if not dni or cita_id in (None, ""):
        return False
    try:
        data, status = citas_client.get(f"/api/citas?dni={dni}&estado=programada")
        if status != 200:
            return False
        return any(str(c.get("id")) == str(cita_id) for c in (data.get("citas") or []))
    except Exception:
        return False
~~~

**Qué decir:** “Tras verificar el teléfono, también se comprueba que la cita pertenece al DNI verificado. Si la consulta falla, devuelve False: se rechaza la acción en vez de autorizarla sin verificar. A eso se le llama fallar cerrado.”

**Por qué separar acciones:** verificar para cancelar no debe autorizar automáticamente modificar una cita o entrar al tratamiento.

---

## 7. Verificar pagos — services/pagos_service/routes.py

Busca _cobro_valido_para_cita y api_pago_yape_estado.

~~~python
def _cobro_valido_para_cita(respuesta, cita_id, monto_pendiente):
    datos = (respuesta or {}).get("datos_respuesta") or {}
    if not isinstance(datos, dict):
        return False

    referencia = next(
        (datos[c] for c in _CAMPOS_REFERENCIA if datos.get(c) not in (None, "")), None
    )
    if referencia is None or str(referencia).strip() != str(cita_id):
        return False

    monto_respuesta = next(
        (datos[c] for c in _CAMPOS_MONTO if datos.get(c) not in (None, "")), None
    )
    if monto_respuesta is None:
        return False
    try:
        return abs(float(monto_respuesta) - float(monto_pendiente)) < 0.01
    except (TypeError, ValueError):
        return False
~~~

**Qué decir:** “Que el proveedor diga pagado no basta. Esta función comprueba que la respuesta sea válida, que la referencia corresponda a la cita y que el monto coincida con el pendiente, con una tolerancia de un céntimo. Si falta referencia o monto, devuelve falso y no confirma.”

El estado Yape obtiene la referencia guardada en la base de datos e ignora el cobro_id arbitrario que pudiera mandar el navegador.

**Qué decir:** “El navegador no decide qué transacción verificar. El backend recupera la referencia almacenada y consulta al proveedor con esa referencia. Luego compara referencia y monto antes de confirmar.”

**Distingue los pasos:** confirmar el pago actualiza el estado; auditoría registra la acción; SMS notifica. Si falla el SMS, no significa automáticamente que el pago confirmado se haya deshecho.

**Limitación de autorización:** validar referencia y monto no demuestra que la sesión tenga derecho a pagar esa cita. El README de la rama consultada documenta una limitación en las páginas de pago/retorno que debe reforzarse. No afirmes que toda la autorización está resuelta.

**Demo o real:** depende de la configuración y credenciales del entorno. Si está activo el modo demo, la transacción es simulada; no la describas como dinero cobrado realmente.

---

## 8. React y el algoritmo de MoovaTrack

**Abre:** frontend/src/moovatrack.jsx.

### Historial acotado

~~~javascript
const INTERVALO_MS = 400
const MAX_PUNTOS = 75
const UMBRALES_INICIALES = { alto: 120, bajo: 60 }

const leer = useCallback(async () => {
  try {
    const d = await pedirJson(urlDatos)
    setError(null)
    setLectura(d)
    contador.current += 1
    setHistorial((h) => [...h, {
      n: contador.current, angulo: d.angulo, fuerza: d.fuerza
    }].slice(-MAX_PUNTOS))
~~~

**Qué decir:** “El componente consulta la URL de lecturas mediante pedirJson, guarda la lectura actual y añade una muestra al historial. slice(-MAX_PUNTOS) conserva los últimos 75 puntos, evitando que la gráfica acumule una lista infinita.”

- useState guarda valores que al cambiar redibujan la interfaz.
- useRef conserva valores entre renderizados sin provocar un render cada vez que cambian.
- useCallback conserva la referencia de una función mientras no cambien sus dependencias.

### Contar repeticiones con histéresis

~~~javascript
const { alto, bajo } = umbralesRef.current
if (faseRef.current === 'abajo' && d.angulo >= alto) {
  faseRef.current = 'arriba'
} else if (faseRef.current === 'arriba' && d.angulo <= bajo) {
  faseRef.current = 'abajo'
  setRepeticiones((r) => r + 1)
}
~~~

**Qué decir:** “Hay dos fases. Empieza abajo. Al llegar a 120 grados o más cambia a arriba. Solo cuando después baja a 60 grados o menos vuelve a abajo y suma una repetición. No suma otra hasta completar un nuevo ciclo.”

**Por qué dos umbrales:** con un solo límite, el ruido alrededor de ese punto podría contar varias repeticiones falsas. Separar 120° y 60° reduce el doble conteo; eso es histéresis.

### Temporizador y limpieza

~~~javascript
useEffect(() => {
  if (!corriendo) return undefined
  leer()
  const id = setInterval(leer, INTERVALO_MS)
  return () => clearInterval(id)
}, [corriendo, leer])
~~~

**Qué decir:** “Cuando la sesión está activa hago una lectura inmediata y repito cada 400 milisegundos. La función de limpieza cancela el intervalo al pausar o desmontar el componente, evitando que quede un temporizador innecesario.”

### Alertas y estado del prototipo

~~~javascript
const anguloFuera = angulo !== null &&
  (angulo < rangos.anguloMin || angulo > rangos.anguloMax)
const fuerzaFuera = fuerza !== null && fuerza > rangos.fuerzaMax
const hayAlerta = anguloFuera || fuerzaFuera
~~~

**Qué decir:** “Comparo la lectura con los rangos configurados. Si el ángulo queda fuera o la fuerza supera el máximo, la interfaz muestra una alerta.”

**Dilo explícitamente:** el componente indica PROTOTIPO: datos simulados. Arduino, MPU-6050, FSR 402, Flex Sensor y HC-05 son la integración prevista, no lecturas físicas conectadas en esta entrega. Los umbrales no son un diagnóstico clínico validado.

---

## 9. KPIs — validar parámetros y consultar el esquema de reportes

**Abre:** services/citas_service/routes.py, función kpis_resumen().

~~~python
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
~~~

**Qué decir:** “Los indicadores dependen de un periodo. La ruta exige ambas fechas, valida el formato y comprueba que la inicial no sea posterior a la final.”

Después:

~~~python
resumen = call_proc_one("sp_kpis_resumen", (desde, hasta), db_name=KPIS_DB_NAME)
por_terapeuta = call_proc(
    "sp_kpis_por_terapeuta", (desde, hasta), db_name=KPIS_DB_NAME
) or []
~~~

**Qué decir:** “Dos procedimientos almacenados consultan el esquema dedicado a KPIs: uno devuelve el resumen general y otro los datos por terapeuta. El backend envía ambos en JSON para que la interfaz los presente.”

**Por qué un esquema separado:** organiza la responsabilidad de reportes; no significa que exista otro servidor de aplicación.

---

## 10. Mapa mental del flujo completo

~~~text
Formulario web
    ↓ POST /api/citas
services/citas_service/routes.py :: crear_cita
    ↓ valida datos y disponibilidad
shared/service_client.py
    ↓ llamada interna a pacientes_service
services/pacientes_service/routes.py
    ↓ busca/crea paciente
shared/proc.py
    ↓ callproc(...)
MySQL: sp_crear_cita
    ↓ devuelve ID de cita
log_accion
    ↓ registra creación
pagos_client.post(...)
    ↓ services/pagos_service/routes.py
MySQL: sp_crear_pago_anticipo
    ↓ pago queda pendiente
~~~

**Explicación de 20 segundos:** “El módulo de citas valida y coordina la reserva; el cliente interno conecta módulos dentro del proceso Flask; shared/proc.py centraliza las llamadas a procedimientos almacenados; MySQL guarda los datos; auditoría registra la acción; y, si corresponde, pagos crea el anticipo pendiente. La reserva y el cobro real son etapas distintas.”

## 11. Orden recomendado para mostrar el código

| Orden | Archivo | Qué señalar |
|---|---|---|
| 1 | services/citas_service/routes.py → crear_cita | campos requeridos, fecha y disponibilidad |
| 2 | mismo archivo | pacientes_client, sp_crear_cita y log_accion |
| 3 | shared/service_client.py | _dispatch y prefijo /_internal |
| 4 | shared/proc.py | call_proc_one y call_proc_execute |
| 5 | services/pagos_service/routes.py | _cobro_valido_para_cita |
| 6 | gateway/app.py | _otp_vigente y _cita_pertenece_al_dni |
| 7 | services/auth_service/routes.py | check_password_hash y generate_password_hash |
| 8 | services/pacientes_service/routes.py | buscar_dni y _resumen_dni |
| 9 | frontend/src/moovatrack.jsx | histéresis, useEffect y datos simulados |
| 10 | services/citas_service/routes.py → kpis_resumen | validación de fechas y SP |

No intentes abrir todo el repositorio. Ensaya estos puntos y deja el resto para preguntas.

## 12. Preguntas difíciles sobre estos fragmentos

**¿Qué pasa si falta un campo?** La ruta devuelve 400 antes de consultar la base.

**¿Qué pasa si el terapeuta ya está ocupado?** Devuelve 409. La regla actual es una cita por especialista y día; no hay selector de bloques horarios.

**¿Por qué no escribir SQL directamente en la ruta?** Los procedimientos almacenados centralizan las operaciones de datos y mantienen la ruta enfocada en validar y coordinar.

**¿Qué pasa si falla pacientes_service?** La ruta captura la excepción y devuelve 502, indicando que una dependencia interna no pudo completar la solicitud.

**¿Por qué APIPERU puede devolver 404 ante un fallo?** Es una limitación actual: el fallo externo puede compartir respuesta con un DNI sin resultado. Sería mejor usar 502 para proveedor no disponible.

**¿El pago se confirma porque lo dice el navegador?** No. El backend consulta la referencia guardada con el proveedor y compara referencia y monto. Aun así debe comprobar autorización de la sesión para esa cita.

**¿Los sensores están conectados?** No en esta versión; la propia interfaz avisa que los datos son simulados.

**¿Qué mejorarías primero?** Reforzaría autorización por propietario en pago/retorno, distinguiría mejor fallos de APIPERU, persistiría bloqueos de login y completaría pruebas de integración.

## 13. Plantilla para no quedarte en blanco

“Esta función recibe [entrada]. Primero valida [regla] para no procesar datos incorrectos. Después llama a [módulo/procedimiento] para [acción]. Si sale bien, devuelve [respuesta]; si falla, responde [código] y registra el error. Está diseñada así para [seguridad/orden/mantenimiento].”

Si no recuerdas un detalle exacto, no lo inventes. Explica la responsabilidad y di que verificarás el nombre concreto del procedimiento o campo antes de afirmarlo.

## Referencias del repositorio

- [Crear cita](https://github.com/i2512546-maker/moovaclinic/blob/main/services/citas_service/routes.py)
- [Cliente interno](https://github.com/i2512546-maker/moovaclinic/blob/main/shared/service_client.py)
- [Procedimientos almacenados](https://github.com/i2512546-maker/moovaclinic/blob/main/shared/proc.py)
- [Pacientes y APIPERU](https://github.com/i2512546-maker/moovaclinic/blob/main/services/pacientes_service/routes.py)
- [Autenticación](https://github.com/i2512546-maker/moovaclinic/blob/main/services/auth_service/routes.py)
- [Pagos](https://github.com/i2512546-maker/moovaclinic/blob/main/services/pagos_service/routes.py)
- [OTP y gateway](https://github.com/i2512546-maker/moovaclinic/blob/main/gateway/app.py)
- [MoovaTrack React](https://github.com/i2512546-maker/moovaclinic/blob/main/frontend/src/moovatrack.jsx)
