# INFO_INTERFACES.md - Informe de Interfaces MOOVA Clinic

## 1. Datos Generales

- **Nombre:** MOOVA Clinic
- **Tipo:** Aplicación web de gestión de clínica de rehabilitación (cita, tratamiento, pago)
- **Stack:** Flask 3.1.3 (gateway) + 6 microservicios Python (auth 5001, pacientes 5002, citas 5003, pagos 5004, notas 5005, audit 5006), MySQL 8.0, mysql-connector-python 9.1.0, Bootstrap 5.3.3, HTML5, CSS3, JavaScript, Jinja2 templates
- **Roles:** admin, terapeuta (personal staff), sin rol (público)
- **Base de datos:** 7 bases divididas (`moovacloud_auth`, `moovacloud_pacientes`, `moovacloud_citas`, `moovacloud_pagos`, `moovacloud_notas`, `moovacloud_kpis`) + archivo `procedures.sql` legado monolítico
- **Endpoints API principal:** 24 rutas públicas y protegidas (`/api/auth/*`, `/api/citas/*`, `/api/pacientes/*`, `/api/pagos/*`, `/api/terapeutas/*`, `/api/servicios/*`, `/api/estadisticas`, `/api/kpis`, `/api/auditoria`, `/api/notas/*`, `/api/verificar_dni`)
- **15 pantallas `.html`** definidas en `templates/`, con rutas Flask correspondientes en `gateway/app.py`

---

## 2. Pantallas (en orden del flujo principal)

### 1. Index
- **Archivo/ruta:** `templates/index.html`, ruta `/`
- **Rol:** Público (ningún login requerido)
- **Función:** Página de inicio que muestra estadísticas dinámicas, especialidades y galería.
- **Objetivo:** Presentar el centro y permitir navegar a agendar cita o conocer servicios.
- **Pre-requisitos:** Ninguno.
- **Datos a mostrar:** 
  - Indicadores (pacientes recuperados, especialistas, años experiencia, tasa éxito) obtenidos vía `GET /api/estadisticas` (citas_service.estadisticas) que consultan SPs `sp_estadisticas_recuperados`, `sp_estadisticas_especialistas`, `sp_estadisticas_opiniones` y configuración de año.
  - Tarjetas de 6 especialidades (fisioterapia, neurología, deportiva, ocupacional, hidroterapia, geriátrica) con descripción, técnicas y beneficios definidos en JavaScript inline.
  - Galería de imágenes/video estáticos.
- **Interacciones del usuario:**
  1. Al cargar, `fetch('/api/estadisticas')` pobla los 4 indicadores (línea index.html:483-503); si falla, muestra "000"/"0"/"0%".
  2. Clic en tarjeta de especialidad → abrir modal con ficha descriptiva (icono, título, subtítulo, descripción, lista de `trata`, `tecnicas`, `duracion`, `beneficios`).
  3. Clic en "Más información" → precargar datos para el modal.
  4. Navegación superior: dropdown Citas → Agendar cita / Modificar / Cancelar; Enlaces Galería, Nosotros, Contacto.
  5. En galería: reproducir video (`<video>`) o ver imágenes estáticas.
- **Navega a:** `/login`, `/citas`, `/interfaz` (desde dropdown Citas), `/index#especialidades`, `/index#galeria`
- **Servicios/endpoints/tablas:** 
  - `/api/estadisticas` (GET) → datos derivados de `sp_estadisticas_recuperados`, `sp_estadisticas_especialistas`, `sp_estadisticas_opiniones`, `sp_obtener_configuracion_anio` (pagos_db) y año base 2023.
  - `/api/servicios` (GET) → `sp_listar_servicios` (pacientes_db); devuelve `id`, `nombre`, `precio`, `duracion_min`.
  - Recursos estáticos: `static/video.mp4`, `static/cccc.png`, `static/pp.png`.

### 2. Login
- **Archivo/ruta:** `templates/login.html`, ruta `/login`
- **Rol:** Público (acceso al personal)
- **Función:** Formulario de acceso al personal con correo y contraseña; toggle de visibilidad de clave.
- **Objetivo:** Autenticar al personal (admin/terapeuta) y establecer sesión.
- **Pre-requisitos:** Campos correo y clave completados.
- **Datos a mostrar:** Mensajes de error/éxito vía `flash()`; botón "Mostrar u ocultar contraseña" (JavaScript togglePassword).
- **Interacciones del usuario:**
  1. POST `/api/auth/login` con `{correo, clave}` → si `success`, guarda `session.usuario_id`, `usuario_nombre`, `rol` y redirige: admin → `/panel_admin`, terapeuta → `/interfaz`.
  2. Si credenciales incorrectas → flash `error` y vuelve a mostrar login.
  3. Toggle password muestra/oculta el campo `clave` y cambia ícono `fa-eye`/`fa-eye-slash`.
  4. Links: "Volver al inicio" → `/`.
- **Navega a:** `/`, `/interfaz`, `/panel_admin`
- **Servicios/endpoints/tablas:** 
  - `POST /api/auth/login` (auth_service.routes.login) → `sp_login` (auth_db); verifica correo/clave con bcrypt; devuelve `usuario.id`, `nombre`, `rol_nombre`.
  - `GET /api/auth/roles` → `sp_listar_roles` (devuelve roles id/nombre).
  - `GET /api/auth/usuarios` → `sp_listar_usuarios` (lista todos los usuarios con id, nombre, correo, rol, activo).

### 3. Interfaz
- **Archivo/ruta:** `templates/interfaz.html`, ruta `/interfaz`
- **Rol:** Staff (admin o terapeuta, valida `session.rol == "admin"` para enlaces panel)
- **Función:** Agenda diaria: lista de pacientes del día, navegación por fechas, guardar descripción clínica.
- **Objetivo:** Permitir al personal ver y gestionar las citas programadas para un día concreto.
- **Pre-requisitos:** sesión iniciada (`usuario_id` en session); rol staff.
- **Datos a mostrar:** 
  - Cabecera con fecha actual, flechas para día anterior/siguiente, badge `es_hoy` y `es_admin`.
  - Tabla de pacientes del día: nombre/apellido, DNI, teléfono, estado (nuevo/recurrente), y formulario POST `guardar_descripcion` (historial_id, descripción, fecha).
  - Count `pacientes|length`.
- **Interacciones del usuario:**
  1. Flechas izquierda/derecha cambian `fecha` query param → recarga `GET /api/citas?fecha=...&estado=programada` (citas_service.listar_citas).
  2. Filtrar por DNI `p.dni` y mostrar `total_visitas`.
  3. Formulario `guardar_descripcion` → POST `/guardar_descripcion` (gateway) que llama a `citas_client.put(f"/api/citas/{historial_id}/completar", {"descripcion": descripcion})` y `log_accion`.
  4. Si `p.total_visitas == 1` muestra badge "Nuevo", si >1 "Recurrente".
- **Navega a:** `/panel_admin` (solo admin), `/pacientes`, `/logout`, `/index`
- **Servicios/endpoints/tablas:** 
  - `GET /api/citas` (citas_service.listar_citas) → `sp_listar_citas('programada', None, fecha, medico_id)`; Enriquece con `_mapa_pacientes()` y `_mapa_terapeutas()` (pacientes_service).
  - `POST /guardar_descripcion` (gateway.guardar_descripcion) → `citas_client.put("/api/citas/{historial_id}/completar", ...)` y `log_accion(accion="completar_cita", ...)`.
  - Datos locales de `citas_db`: `historial_id`, `paciente_id`, `descripcion`, `fecha_cita`.

### 4. Citas (agendar)
- **Archivo/ruta:** `templates/citas.html`, ruta `/citas`
- **Rol:** Staff (requiere sesión activa; forma pública sin login pero valida DNI)
- **Función:** Wizard de 4 pasos para agendar cita nueva: datos personales → especialidad/pago → confirmación.
- **Objetivo:** Reservar una nueva cita con validación de formato, disponibilidad de médico y anticipo de pago.
- **Pre-requisitos:** DNI 8 dígitos, nombre/apellido con solo letras/espacios, teléfono 9 dígitos, fecha futura, hora HH:MM, médico disponible.
- **Datos a mostrar:** 
  - Pasos del wizard (indicadores 1-4 con conectores).
  - Step 1: campos Nombre, Apellido, DNI (máx 8), Teléfono (9 dígitos), Fecha cita (mínimo hoy).
  - Step 2: selector de servicio (listado `/api/servicios`), costo y anticipo (50%), selector de método pago (Yape/Plin/Tarjeta/Transferencia), lista de médicos disponibles (desde `/api/citas/terapeutas`).
  - Step 3/4: confirmación de datos y redirección.
- **Interacciones del usuario:**
  1. **Paso 1 → 2:** Clic "Siguente" valida campos y ejecuta `irPaso(2)`; muestra popup si faltan datos.
  2. **Autocompletado DNI:** Al escribir DNI, `fetch('/api/verificar_dni', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':csrfToken()}, body:JSON.stringify({dni)})` devuelve datos del paciente (nombres, apellidos) y los llena en los campos; si no existe, avisa "DNI no encontrado".
  3. **Seleccionar médico:** Clic en "Elegir" en cada fila de la tabla de médicos (`onclick=seleccionarMedico`) → rellena `#medico_id`, `#medico-nombre-badge`, actualiza precios (`actualizarPrecios(precio)`) y habilita botón "Agendar Cita".
  4. **Cambio de método/pago:** Al cambiar `#servicio_id` o `#metodo_pago`, `actualizarBoton()` habilita/deshabilita el botón submit.
  5. **Submit del formulario:** `enviarFormAjax` POST al action del form (que es `/citas`, gateway) con `X-Requested-With: XMLHttpRequest`, `Accept: application/json`, y `X-CSRFToken`. Si `success` y `redirect` → muestra popup y navega a `data.redirect` (normalmente `/pago?cita_id=...`).
  6. **Errores:** Si validación rápida devuelve error → `mostrarPopup(..., 'error')`; si médico no disponible → 409; si DNI no encontrado → popup error.
- **Navega a:** `/pago?cita_id=...`, `/retorno?cita_id=...`, `/tratamiento` (si tiene paquete activo), `/index`
- **Servicios/endpoints/tablas:** 
  - `POST /api/citas` (citas_service.crear_cita) → validación estricta `_validar_datos_cita`; `sp_crear_cita(paciente_id, medico_id, servicio_id, fecha_cita, hora_cita)` en citas_db; `call_proc("sp_resumen_pacientes")`; creación de paciente mínimo vía `/api/pacientes/min` si DNI nuevo; POST a `/api/pagos/anticipo` (pagos_service) si método_pago y anticipo > 0.
  - `GET /api/citas/terapeutas` → lista terapeutas desde pacientes_service (lista `ID`, `Nombre`, `Especialidad`, `precio`).
  - `GET /api/servicios` → lista servicios (`id`, `nombre`, `precio`).
  - `GET /api/verificar_dni` (gateway, via pacientes_client.post) → `call_proc("sp_obtener_paciente_id_dni", (dni,))`.
  - `GET /api/citas/estadisticas` (mostrado en index).

### 5. Modificar Cita
- **Archivo/ruta:** `templates/modificar_cita.html`, ruta `/citas/modificar`
- **Rol:** Staff (requiere sesión; verificación OTP en dos pasos)
- **Función:** Modificar fecha y especialista de una cita existente mediante verificación por SMS (OTP de 6 dígitos).
- **Objetivo:** Permitir al personal cambiar los datos de una cita agendada con seguridad de identidad.
- **Pre-requisitos:** DNI válido, recibir código SMS, OTP correcto.
- **Datos a mostrar:** 
  - Paso 1: formulario DNI (máx 8 dígitos) → envía SMS.
  - Paso 2: ingresar código OTP de 6 dígitos.
  - Lista de citas del paciente (después de verificación) con checkbox para seleccionar y formulario para nueva fecha + nuevo médico.
- **Interacciones del usuario:**
  1. **Paso 1 (solicitar OTP):** Clic "Enviar código SMS" POST `/api/citas/otp/solicitar` con `{"dni":dni, "accion":"modificar"}`. Si éxito, guarda `session.otp_tel_mask` y navega a `?paso=verificar&dni={dni}` mostrando el tel_mask enmascarado (ej. `998***,****`).
  2. **Paso 2 (verificar OTP):** Formulario código de 6 dígitos → POST `/api/citas/otp/verificar` con `{"dni":dni, "otp":otp, "accion":"modificar"}`. Si `resultado == "ok"` → lista citas programadas del paciente (`GET /api/citas?dni={dni}&estado=programada`) y muestra en pantalla; si `expirado`/`agotado`/`no_existe` muestra mensaje correspondiente.
  3. **Seleccionar cita y editar:** Al elegir una cita, muestra formulario con `fecha_cita` y `medico_id` (lista terapeutas); submit POST con `accion=guardar` → PUT `/api/citas/{cita_id}` con `{"fecha_cita": nueva_fecha, "medico_id": nuevo_medico}`. Si éxito → flash `exito:Cita modificada correctamente.`
- **Navega a:** `/citas`, `/pago?cita_id=...`, `/index`
- **Servicios/endpoints/tablas:** 
  - `POST /api/citas/otp/solicitar` → valida DNI, obtiene datos paciente vía `pacientes_client.get("/api/pacientes/{dni}")`, genera código `secrets.randbelow(900000)+100000`, ejecuta `sp_invalidar_otps_previos(dni, accion)` y `sp_insertar_otp(dni, codigo, accion, expira)`, envía SMS por TextBEE, devuelve `tel_mask`.
  - `POST /api/citas/otp/verificar` → `call_proc_one("sp_obtener_otp", (dni, accion))`; valida intentos (`OTP_MAX_INTENTOS=3`), expiración (`OTP_EXPIRA_MIN=10`), código correcto; si ok ejecuta `sp_marcar_otp_usado` y devuelve `{"resultado":"ok"}`.
  - `PUT /api/citas/{cita_id}` (citas_service.modificar_cita) → `sp_modificar_cita(cita_id, nueva_fecha, nuevo_medico, hora_cita)`; log `reprogramar_cita`.
  - `GET /api/citas?dni=...` → `sp_listar_citas(estado='programada', None, fecha, medico_id)` enlistadas con enriquecimiento de datos paciente y terapeuta.

### 6. Cancelar Cita
- **Archivo/ruta:** `templates/cancelar_cita.html`, ruta `/citas/cancelar`
- **Rol:** Staff (verificación OTP en dos pasos)
- **Función:** Cancelar una cita agendada mediante verificación por SMS.
- **Objetivo:** Dar de baja una cita con autorización del paciente/terapeuta.
- **Pre-requisitos:** DNI válido, OTP correcto, cita con estado `programada`.
- **Datos a mostrar:** 
  - Paso 1: formulario DNI → enviar SMS.
  - Paso 2: ingresar OTP → listar citas programadas del paciente.
  - Lista de citas con botón "Cancelar esta cita" (confirma `¿Seguro que deseas cancelar esta cita?`).
- **Interacciones del usuario:**
  1. **Paso 1 (solicitar):** Igual que en modificar_cita: POST `/api/citas/otp/solicitar` con `accion="cancelar"`.
  2. **Paso 2 (verificar):** POST `/api/citas/otp/verificar` con `accion="cancelar"`. Si `ok` → lista citas programadas y muestra cada una con formulario POST `accion=confirmar` → DELETE `/api/citas/{cita_id}`.
  3. **Confirmar cancelación:** Al submit, valida `data-confirm` ("¿Seguro que deseas cancelar esta cita?") y si acepta, envía `fetch(DELETE, ...)`. Si éxito → flash `exito:Tu cita ha sido cancelada correctamente.` y recarga lista.
- **Navega a:** `/citas`, `/index`
- **Servicios/endpoints/tablas:** 
  - `POST /api/citas/otp/solicitar (accion=cancelar)` y `verificar` idéntico al de modificar, con `accion="cancelar"`.
  - `DELETE /api/citas/{cita_id}` (citas_service.cancelar_cita) → `sp_cancelar_cita(cita_id)`; POST a `/api/pagos/{cita_id}/cancelar` (pagos_service) para cancelar pago pendiente; log `cancelar_cita`.

### 7. Tratamiento
- **Archivo/ruta:** `templates/tratamiento.html`, ruta `/tratamiento`
- **Rol:** Staff (requiere sesión; flujo de continuidad para paciente con paquete activo)
- **Función:** Continuar tratamiento: verificación OTP, seleccionar paquete activo y agendar siguiente sesión sin repetir datos.
- **Objetivo:** Permitir al paciente recurrente agenda la siguiente sesión usando su paquete de sesiones vigente.
- **Pre-requisitos:** Paciente debe tener al menos un paquete activo con sesiones disponibles.
- **Datos a mostrar:** 
  - Paso 1: formulario DNI (máx 8 dígitos).
  - Paso 2 (verificar OTP): muestra tel_mask y, si paquetes activos, navega a `paso=menu` con listado de paquetes (servicio, sesiones usadas/restantes, fecha vencimiento); si no hay paquetes → `paso="sin_paquetes"`.
  - Si en `paso=menu`: mini-formulario para agendar sesión: fecha cita, especialista (médico), método pago (Yape/Plin/Tarjeta/Transferencia).
- **Interacciones del usuario:**
  1. **Paso 1 (solicitar OTP):** POST `/api/citas/otp/solicitar` con `accion="tratamiento"`; valida que el paciente tenga al menos un paquete activo con sesiones disponibles (consulta `GET /api/pagos/pacientes/{paciente_id}/paquetes` y revisa `estado=='activo' and sesiones_usadas < total_sesiones`). Si no tiene paquete activo → error "No tienes tratamientos activos pendientes de pago."
  2. **Paso 2 (verificar OTP):** POST `/api/citas/otp/verificar` con `accion="tratamiento"`; si `ok` → muestra pacient data y lista paquetes activos. Si no hay paquetes → `paso="sin_paquetes"` y sugiere agendar cita nueva.
  3. **Si hay paquetes (`paso=menu`):** Clic en "Agendar siguiente sesión" en cada paquete → llena `#paquete_id` y muestra panel de agendamiento con fecha, médico, método pago. Submit POST con `accion="agendar"` → crea cita vía `POST /api/citas` (misma lógica que citar nueva) y luego POST `/api/pagos/paquetes/{paquete_id}/usar` (incrementa `sesiones_usadas`).
  4. **Si no hay paquetes:** Navega a `/citas` para agendar cita normal.
- **Navega a:** `/pago?cita_id=...`, `/citas`, `/index`
- **Servicios/endpoints/tablas:** 
  - `POST /api/citas/otp/solicitar (accion=tratamiento)` → valida paquete activo (via `pacientes_client.get("/api/pagos/pacientes/{paciente_id}/paquetes")` y `pagos_client.get("/api/pagos/pacientes/{paciente_id}/paquetes")`).
  - `POST /api/citas/otp/verificar (accion=tratamiento)` → mismo flujo que otros OTPs.
  - `POST /api/citas` (crear cita) → misma validación que agendar nueva cita, usando datos del paciente (nombre, apellido, dni, telefono) traídos de `session.tratamiento_paciente`.
  - `POST /api/pagos/paquetes/{paquete_id}/usar` (pagos_service.usar_sesion_paquete) → `sp_usar_sesion_paquete(paquete_id, cita_id)`; incrementa `sesiones_usadas` y registra log `usar_sesion_paquete`.

### 8. Pago
- **Archivo/ruta:** `templates/pago.html`, ruta `/pago?cita_id=X`
- **Rol:** Staff (después de crear cita pendiente; requiere `session.cita_pendiente_id`)
- **Función:** Mostrar resumen de cita y panel de pago (QR Yape/Plin, tarjeta Niubiz, o transferencia).
- **Objetivo:** Cobrar el anticipo (50%) de la cita y marcarla como pagada.
- **Pre-requisitos:** `cita_pendiente_id` en session y cita con `estado_pago == "pendiente"`.
- **Datos a mostrar:** 
  - Resumen de cita: paciente, especialista, fecha, Especialidad, monto del anticipo (50%).
  - Según método_pago: panel Yape (QR), Plin (QR), tarjeta (form Niubiz) o transferencia.
  - Wizzard de pasos completados (1-4 todos "completed").
- **Interacciones del usuario:**
  1. **Yape/Plin:** Clic "Mostrar código QR de Yape" → fetch `POST /api/pagos/yape/iniciar` con `{cita_id}`; devuelve `qr` (base64) y `cobro_id`; muestra imagen en modal. Clic "Ya realicé el pago" → `verificarYape()` → hace `POST /api/pagos/yape/estado` con `{cita_id, cobro_id}`; si la respuesta trae `pagado: true` cierra el modal y muestra overlay `overlayExito`, si no muestra el error del servicio y reactiva el botón.
  2. **Tarjeta:** Llena formulario número, titular, vencimiento (MM/AA), CVV; submit `POST /api/pagos/tarjeta/iniciar` (obtiene `sessionKey`, `merchantId` de NiubizClient) → luego `POST /api/pagos/tarjeta/cobrar` con `cardToken`, `cvv`, `purchaseNumber`. Si `res.ok && res.pagado` → overlay éxito.
  3. **Transferencia:** Clic "Confirmar pago" → muestra mensaje "método requiere cuenta bancaria configurada. Contacta con administración." (placeholders).
  4. Después de pago exitoso → `irARetorno()` → navega a `/retorno?cita_id=X`.
- **Navega a:** `/retorno?cita_id=X`, `/index`
- **Servicios/endpoints/tablas:** 
  - `GET /api/pagos/{cita_id}` (pagos_service.estado_pago) → `call_proc_one("sp_obtener_pago", (cita_id,))`; devuelve `estado_pago`, `monto`, `metodo_pago`, `referencia`.
  - `POST /api/pagos/yape/iniciar` → `YapeClient().crear_cobro(monto, concepto, referencia)`; guarda referencia vía `sp_guardar_referencia(cita_id, cobro_id)`; devuelve `qr` (URL base64) y `cobro_id`.
  - `POST /api/pagos/yape/estado` → `YapeClient().consultar_pago(cobro_id or referencia)`; si `res["pagado"]` → `confirmar_pago_servicio(cita_id, referencia, datos_respuesta)` que ejecuta `sp_confirmar_pago` y logs; devuelve `{"ok":True,"pagado":True}`.
  - Igual flujo para `POST /api/pagos/plin/iniciar` y `/plin/estado` usando `PlinClient`.
  - `POST /api/pagos/tarjeta/iniciar` → `NiubizClient().get_session_key()` → devuelve `sessionKey`, `merchantId`, `monto`, `purchaseNumber`.
  - `POST /api/pagos/tarjeta/cobrar` → `NiubizClient().cobrar(card_token, cvv, purchase_number, monto)`; si ok → `confirmar_pago_servicio(cita_id, referencia=res["transaccion_id"], datos_respuesta=res.get("datos_respuesta"))`; devuelve `{"ok":True,"pagado":True,"transaccion_id":res["transaccion_id"]}`.
  - Verificación real: `verificarYape()`/`verificarPlin()` llaman a `verificarCobro()`, que hace `POST /api/pagos/yape|plin/estado` con `{cita_id, cobro_id}`. Solo si la respuesta trae `pagado: true` se cierra el modal y se muestra el overlay de éxito; el pago se confirma en `pagos_service`, no en el navegador.

### 9. Retorno
- **Archivo/ruta:** `templates/retorno.html`, ruta `/retorno?cita_id=X`
- **Rol:** Staff (después de que `pagos_service` confirma el pago)
- **Función:** Pantalla de confirmación final: cita agendada con éxito, datos resumidos y contactos.
- **Objetivo:** Confirmar al usuario que su cita quedó registrada y facilitar contacto posterior.
- **Pre-requisitos:** `cita_id` como query param y pago en estado `pagado` (confirmado por `pagos_service`); si no lo está, redirige de vuelta a `/pago`.
- **Datos a mostrar:** 
  - Círculo de confirmación con check.
  - Título "¡Tu cita ha sido agendada!".
  - Datos resumidos: paciente nombre/apellido, especialista, fecha formateada dd/mm/YYYY, anticipo pagado S/XX.XX, método pago.
  - Si `cita.referencia` existe → muestra número de operación.
  - Botones: "Volver al inicio", "Ver nuestros servicios", contactos WhatsApp/Facebook/X con enlaces a REDES_SOCIALES.
- **Interacciones del usuario:** Ninguna beyond view; botón "Continuar" (después de pago) navega a `/index`; enlaces sociales abren en nueva pestaña.
- **Navega a:** `/index`, `/#especialidades`
- **Servicios/endpoints/tablas:** 
  - `GET /api/pagos/{cita_id}` (mismo que en pago) para obtener datos de pago.
  - `GET /api/citas/{cita_id}` (citas_service.detalle_cita) para datos de cita (nombre, apellido, terapeuta, Especialidad, fecha_cita, monto, metodo_pago).
  - Guarda: si el pago no figura `pagado` redirige a `/pago?cita_id=...`; en caso contrario limpia `session["cita_pendiente_id"]` y renderiza la plantilla.

### 10. Panel Admin
- **Archivo/ruta:** `templates/paneladmin.html`, ruta `/panel_admin`
- **Rol:** Admin sólo (`session.rol == "admin"` y `current_user.es_admin`)
- **Función:** Gestión de médicos, usuarios, citas próximas y logs de auditoría.
- **Objetivo:** Administrar el personal médico, ver/gestionar usuarios y próximas citas.
- **Pre-requisitos:** sesión iniciada y `rol == "admin"`.
- **Datos a mostrar:** 
  - Formulario "Nuevo Médico": nombre, especialidad, correo, teléfono, contraseña, costo consulta (S/).
  - Listado de médicos registrados con botones: actualizar precio, cambiar clave, desactivar/ reactivar.
  - Listado de usuarios del sistema (nombre, correo, rol, estado, último acceso).
  - Próximas citas programadas (tabla con fecha, paciente, DNI, teléfono, especialista, estado, botón cancelar).
  - Modal "Cambiar contraseña" para un médico seleccionado.
- **Interacciones del usuario:**
  1. **Registrar médico:** POST form con `accion=registrar` → valida campos; llama a `auth_client.post("/api/auth/usuarios", {...})` (crea usuario con rol `terapeuta` y hash de clave) → luego `pacientes_client.post("/api/terapeutas", {"usuario_id": ..., "especialidad_id": ..., "precio": ...})`; log `crear_usuario`; flash éxito.
  2. **Actualizar precio:** Form inline con input `precio` y button "Guardar precio" → PUT `/api/terapeutas/{medico_id}/precio` (pacientes_service); flash éxito.
  3. **Cambiar clave:** Abre modal con `medico_id` y nombre; POST con `accion=cambiar_clave` y `nueva_clave` → PUT `/api/auth/usuarios/{usuario_id}` (auth_service) con clave en claro (el hash lo hace auth_service internamente); flash éxito.
  4. **Desactivar/Reactivar médico:** Form POST con `accion=eliminar` o `reactivar` → PUT `/api/terapeutas/{id}/activo` (pacientes_service) y PUT `/api/auth/usuarios/{usuario_id}` (auth_service) para activar/desactivar; flash éxito.
  5. **Listar usuarios:** GET `/api/auth/usuarios` → devuelve tabla con nombre, correo, rol (capitalizado), estado (badge activo/inactivo), último acceso.
  6. **Próximas citas:** GET `/api/citas?fecha=hoy&estado=programada` (primeras 20) → tabla con fecha, paciente nombre/apellido, DNI, teléfono, terapeuta, estado (programada/cancelada/completada), botón cancelar (POST admin_cancelar_cita).
- **Navega a:** `/panel_admin/kpis`, `/panel_admin/auditoria`, `/interfaz`, `/logout`, `/index`
- **Servicios/endpoints/tablas:** 
  - `GET /api/terapeutas` (pacientes_service.listar_terapeutas) → lista terapeutas enriquecidos con nombre (desde usuarios), teléfono, especialidad, precio.
  - `GET /api/terapeutas/{id}` → devuelve objeto terapeuta completo.
  - `PUT /api/terapeutas/{id}/precio` → `sp_actualizar_precio(medico_id, precio)`.
  - `PUT /api/terapeutas/{id}/activo` → `sp_set_terapeuta_activo(medico_id, 1|0)`.
  - `GET /api/auth/usuarios` → lista usuarios (id, nombre, correo, rol, activo, último acceso).
  - `PUT /api/auth/usuarios/{id}` (auth_service) → actualiza usuario (clave hash, activo, rol).
  - `GET /api/citas?fecha=hoy&estado=programada` → primeras 20 citas programadas.
  - `POST /admin_cancelar_cita/{cita_id}` (gateway) → DELETE `/api/citas/{cita_id}` y flash éxito.
  - Modal cambiar clave: form POST `accion=cambiar_clave`, `medico_id`, `nueva_clave`.

### 11. Panel Admin Auditoría
- **Archivo/ruta:** `templates/auditoria.html`, ruta `/panel_admin/auditoria`
- **Rol:** Admin sólo
- **Función:** Listado y filtrado de logs de auditoría del sistema.
- **Objetivo:** Revisar todas las acciones realizadas en el sistema (crear cita, marcar pago, crear usuario, etc.) con filtros por usuario, tipo de acción, fecha y entidad.
- **Pre-requisitos:** sesión admin.
- **Datos a mostrar:** 
  - Formulario de filtros: Usuario (select con lista de admin/terapeuta), Acción (select con crear_cita, reprogramar_cita, cancelar_cita, completar_cita, marcar_pago, usar_sesion_paquete, crear_usuario, desactivar_usuario), Fecha desde/hasta (input type date), Tipo de usuario (admin/terapeuta/paciente/sistema), Entidad tipo (paciente/medico).
  - Tabla de logs: columnas Fecha/Hora, Usuario, Tipo, Acción, Relacionado con, Detalles, IP.
- **Interacciones del usuario:**
  1. Aplicar filtros: envía GET `panel_admin_auditoria?usuario_id=X&accion=Y&fecha_desde=...&fecha_hasta=...`; el gateway construye parámetros `filtros` y llama a `GET /api/auditoria?filtros` (audit_service).
  2. Tabla renderiza los logs devueltos (`data.logs`); si está vacía muestra "No hay registros de auditoría".
  3. Filtro "Usuario" único: si selecciona un usuario y no selecciona `usuario_tipo`, el gateway deriva `usuario_tipo` del rol real del usuario elegido (bucles `usuarios_filtro`).
  4. Filtro "Más filtros" collapsable muestra selector "Tipo de usuario" y "Relacionado con" (paciente/medico, este último disabled "Próximamente").
- **Navega a:** `/panel_admin`, `/panel_admin/kpis`, `/logout`, `/index`
- **Servicios/endpoints/tablas:** 
  - `GET /api/auditoria` (audit_service.listar_auditoria) → `call_proc("sp_listar_auditoria", (usuario_id, usuario_tipo, accion, fecha_desde, fecha_hasta, entidad_tipo))`; devuelve array de objetos con `fecha_creacion`, `usuario_nombre`, `usuario_tipo|capitalize`, `accion`, `entidad_nombre`, `detalles`, `ip_origen`.
  - `POST /api/auditoria` (audit_service.registrar_auditoria) → `call_proc_execute("sp_insertar_log_auditoria", ...)`; usado internamente por `log_accion` pero la interfaz solo lee.
  - `ACCIONES_VALIDAS` en `shared/audit.py`: `["crear_cita","reprogramar_cita","cancelar_cita","completar_cita","marcar_pago","usar_sesion_paquete","crear_usuario","desactivar_usuario"]`.

### 12. Panel Admin KPIs
- **Archivo/ruta:** `templates/kpis.html`, ruta `/panel_admin/kpis`
- **Rol:** Admin sólo
- **Función:** Indicadores clave de negocio (citas, ingresos, paquetes, sesiones) por rango de fechas.
- **Objetivo:** Visualizar el desempeño del negocio y por terapeuta en un período seleccionado.
- **Pre-requisitos:** sesión admin.
- **Datos a mostrar:** 
  - Tarjetas resumen: Total de citas, Citas completadas (con tasa %), Citas programadas, Ingresos confirmados/pendientes (S/), Paquetes vendidos, Sesiones consumidas.
  - Tabla "Por Terapeuta": nombre, total citas, completadas, tasa completadas (%), ingresos (S/).
  - Selector de rango de fechas (desde/hasta) con opción "Últimos 30 días".
  - Mensaje de error si el servicio no está disponible.
- **Interacciones del usuario:**
  1. Cambiar fechas `desde`/`hasta` y clic "Aplicar" → POST `panel_admin/kpis?desde=YYYY-MM-DD&hasta=YYYY-MM-DD` → llama a `GET /api/kpis?desde=...&hasta=...` (citas_service.kpis_resumen).
  2. Si éxito → muestra `resumen` (objeto con `total_citas`, `citas_completadas`, `tasa_completadas`, `citas_programadas`, `ingresos_confirmados`, `ingresos_pendientes`, `paquetes_vendidos`, `sesiones_consumidas`) y tabla `por_terapeuta` (array de objetos `terapeuta_nombre`, `total_citas`, `citas_completadas`, `tasa_completadas`, `ingresos`).
  3. Si error (service down o formato de fecha inválido) → muestra `error` en alerta roja.
  4. Enlace "Últimos 30 días" → autocompleta `desde = hoy - 30 días`, `hasta = hoy` y aplica.
- **Navega a:** `/panel_admin`, `/panel_admin/auditoria`, `/logout`, `/index`
- **Servicios/endpoints/tablas:** 
  - `GET /api/kpis?desde=YYYY-MM-DD&hasta=YYYY-MM-DD` (citas_service.kpis_resumen) → valida formato y que `desde <= hasta`; llama a `call_proc_one("sp_kpis_resumen", (desde, hasta), db_name="moovacloud_kpis")` y `call_proc("sp_kpis_por_terapeuta", (desde, hasta), db_name="moovacloud_kpis")` o `[]`; devuelve `{"success":True,"resumen":{...},"por_terapeuta":[...]}`.
  - SP `sp_kpis_resumen` y `sp_kpis_por_terapeuta` viven en `moovacloud_kpis` (`db_split/kpis_db.sql`) y son de reporte cross-DB: leen de las demás bases, no escriben.

### 13. Pacientes
- **Archivo/ruta:** `templates/pacientes.html`, ruta `/pacientes`
- **Rol:** Admin sólo
- **Función:** Listado general de pacientes con búsqueda y enlaces a ficha detallada.
- **Objetivo:** Permitir al admin ver todos los pacientes registrados y acceder a su historial.
- **Pre-requisitos:** sesión admin.
- **Datos a mostrar:** 
  - Lista de pacientes traída de `GET /api/pacientes` (pacientes_service.listar_pacientes): cada ficha muestra DNI, nombre, apellido, teléfono, estado (badge color), total de citas, última cita.
  - Input de búsqueda `buscarPaciente` (keypress `onkeyup=filtrarPacientes()`) que filtra client‑side mostrando/ocultando cards según coincidencia en `data-buscar` (nombre + apellido + DNI).
  - Cada card enlaza a `detalle_paciente_page` con el DNI.
- **Interacciones del usuario:**
  1. Al escribir en `buscarPaciente` (mínimo 1 carácter, patrón `\d{8}`) → `filtrarPacientes()` oculta cards que no contengan el texto en `data-buscar` (minúsculas).
  2. Clic en "Ver historial" de cualquier card → navega a `/pacientes/{dni}`.
  3. Cada ficha muestra badge `estado|capitalize` (ej. "activo", "inactivo", "pendiente").
- **Navega a:** `/pacientes/{dni}`, `/index`, `/logout`
- **Servicios/endpoints/tablas:** 
  - `GET /api/pacientes` (pacientes_service.listar_pacientes) → `call_proc("sp_listar_pacientes")`; enriquece cada ficha con `total_citas` y `ultima_cita` desde `citas_service.resumen_pacientes` (`/api/citas/resumen_pacientes`).
  - Búsqueda client‑side no toca backend.

### 14. Detalle Paciente
- **Archivo/ruta:** `templates/detalle_paciente.html`, ruta `/pacientes/<dni>`
- **Rol:** Admin sólo
- **Función:** Ficha completa del paciente: datos personales, historial de citas, paquetes de sesiones, evaluaciones iniciales, consentimientos informados.
- **Objetivo:** Proporcionar al admin una visión integral del paciente para su seguimiento clínico.
- **Pre-requisitos:** DNI válido; sesión admin.
- **Datos a mostrar:** 
  - Datos principales: DNI, teléfono, email (o "No registrado"), estado (badge), fecha de nacimiento, sexo, dirección, seguro.
  - Historial de citas: tabla con fecha, terapeuta, especialidad, estado (badge), monto, estado pago.
  - Paquetes de sesiones: tabla con servicio nombre, sesiones usadas/sesiones totales, progreso (barra de progreso), fecha de compra, vencimiento, estado.
  - Evaluaciones iniciales: tabla con fecha, terapeuta, motivo consulta, dolor EVA (0-10), rango movimiento, objetivos terapéuticos.
  - Consentimientos informados: tabla con tipo, versión, fecha aceptación (dd/mm/YYYY HH:MM), IP origen.
  - Botón "Descargar Ficha PDF" → `GET /pacientes/<dni>/ficha-clinica.pdf` (endpoint `ficha_clinica_pdf`, solo admin). Genera el PDF con `reportlab` (`gateway/ficha_pdf.py`): encabezado, datos del paciente, historial de citas, paquetes, evaluaciones iniciales, consentimientos y pie con la fecha de emisión. Se abre en una pestaña nueva.
- **Interacciones del usuario:** Ninguna beyond view; scroll dentro de la página.
- **Navega a:** `/pacientes`, `/index`, `/logout`
- **Servicios/endpoints/tablas:** 
  - `GET /api/pacientes/{dni}` (pacientes_service.detalle_paciente) → devuelve `{paciente, historial, paquetes, evaluaciones, consentimientos}`.
    - `historial` = `call_proc("sp_listar_citas_paciente", (paciente_id,))` enriquecido con terapeuta/especialidad y datos de pago (desde `pagos_client.get("/api/pagos/pacientes/{paciente_id}")`).
    - `paquetes` = `call_proc("sp_listar_paquetes_paciente", (paciente_id,))` enriquecido con nombre de servicio (desde `pacientes_client.get("/api/servicios")`).
    - `evaluaciones` = `call_proc("sp_listar_evaluaciones", (paciente_id,))` con `terapeuta_nombre` enriquecido.
    - `consentimientos` = `call_proc("sp_listar_consentimientos", (paciente_id,))`.
  - `GET /api/pacientes/{id}/paquetes` (pacientes_service.listar_paquetes) → lista paquetes con servicio y duración.
  - `GET /api/pacientes/{id}/evaluaciones` → lista evaluaciones.
  - `GET /api/pacientes/{id}/consentimientos` → lista consentimientos.

### 15. Notas Cita
- **Archivo/ruta:** `templates/notas_cita.html`, ruta `/notas/<cita_id>`
- **Rol:** Staff (requiere `usuario_id` en sesión)
- **Función:** Registrar y ver notas clínicas asociadas a una cita concreta.
- **Objetivo:** Permitir al personal anotar el progreso o aspectos relevantes de cada sesión.
- **Pre-requisitos:** cita_id válida; sesión iniciada.
- **Datos a mostrar:** 
  - Datos de la cita actual (nombre paciente, apellido, DNI, fecha, terapeuta, especialidad).
  - Formulario para nueva nota: campo "Diagnóstico (opcional)", textarea "Nota de la sesión".
  - Lista de notas previas: cada una muestra autor (enriquecido desde terapeutas), fecha creación, texto de la nota, y diagnóstico si existe.
  - Si no hay notas previas → mensaje "No hay notas clínicas registradas para esta cita."
- **Interacciones del usuario:**
  1. **Crear nota:** POST `/api/notas/{cita_id}` con `{"nota": texto, "diagnostico": diag, "terapeuta_id": None, "paciente_id": cita.paciente_id}` (notas_service.crear_nota). Si éxito → flash `exito:Nota clínica guardada.` y vuelve a renderizar la lista.
  2. **Listar notas previas:** GET `/api/notas/{cita_id}` (notas_service.listar_notas) → `call_proc("sp_listar_notas", (cita_id), db_name="moovacloud_notas")`; enriquece `autor` desde `_mapa_terapeutas()` (pacientes_service).
  3. Si el campo `nota` está vacío → error `La nota no puede estar vacia.` devuelto por `POST /api/notas/{cita_id}`.
- **Navega a:** `/pacientes/{dni}`, `/index`, `/logout`
- **Servicios/endpoints/tablas:** 
  - `GET /api/notas/{cita_id}` (notas_service.listar_notas) → `call_proc("sp_listar_notas", (cita_id), db_name="moovacloud_notas")`; enriquece `autor` name from terapeutas.
  - `POST /api/notas/{cita_id}` (notas_service.crear_nota) → `call_proc_one("sp_crear_nota", (cita_id, paciente_id, terapeuta_id, nota, diagnostico), db_name="moovacloud_notas")`; devuelve `nota_id`.
  - `sp_listar_notas` y `sp_crear_nota` operan sobre la base `moovacloud_notas` (separada de las 7 DBs principales).

---

## 3. Matriz Resumen

| Interfaz | Pre‑requisito | Datos a mostrar | Interacción |
|---|---|---|---|
| Index | Ninguno | `/api/estadisticas`, tarjetas de especialidades, galería | Fetch al cargar, clic en tarjetas → modal, navegación dropdown |
| Login | Campos completos | `POST /api/auth/login`, roles | Submit form, toggle password, mensajes flash |
| Interfaz | sesión activa, rol staff | `GET /api/citas?fecha=...`, form `guardar_descripcion` | Flechas fecha, form descripcion, badges estado |
| Citas (agendar) | DNI 8 dígitos, valida campos | `/api/citas`, `/api/servicios`, `/api/citas/terapeutas`, `/api/verificar_dni` | Wizard 4 pasos, autocompletado DNI, selección médico, submit AJAX |
| Modificar Cita | DNI + OTP verificado | `POST /api/citas/otp/solicitar/verificar`, `PUT /api/citas/{id}` | 2‑step OTP, listar citas, editar fecha/médico |
| Cancelar Cita | DNI + OTP verificado | Igual que modificar, `DELETE /api/citas/{id}` | 2‑step OTP, confirmar cancelación |
| Tratamiento | Paciente con paquete activo | `POST /api/citas/otp/solicitar (accion=tratamiento)`, paquetes API | OTP, listar paquetes, agendar sesión + usar sesión paquete |
| Pago | `cita_pendiente_id` en sesión | `GET /api/pagos/{id}`, `/api/pagos/yape/iniciar`, `/api/pagos/plin/iniciar`, `/api/pagos/yape/estado`, `/api/pagos/plin/estado`, `/api/pagos/tarjeta/iniciar/cobrar` | QR Yape/Plin con verificación real, form tarjeta Niubiz, transferencia (placeholder) |
| Retorno | pago confirmado por `pagos_service` | `GET /api/pagos/{id}`, `GET /api/citas/{id}` | Pantalla estática, botones volver/inicios/Contacto |
| Panel Admin | rol admin | `/api/terapeutas`, `/api/auth/usuarios`, `/api/citas` | CRUD médicos, actualizar precio, cambiar clave, desactivar/ reactivar, listar usuarios, citas próximas |
| Auditoría | rol admin, filtros opcionales | `GET /api/auditoria?filtros` | Aplicar filtros, tabla logs, "No hay registros" |
| KPIs | rol admin, rango fechas | `GET /api/kpis?desde=...&hasta=...` | Selector de fechas, tarjetas resumen, tabla por terapeuta |
| Pacientes | rol admin | `GET /api/pacientes` | Buscador client‑side, cards con badge estado, enlaces historial |
| Detalle Paciente | DNI válido, admin | `GET /api/pacientes/{dni}`, `/paquetes`, `/evaluaciones`, `/consentimientos` | Ficha completa: datos, historial, paquetes, evaluaciones, consentimientos, descarga del PDF |
| Notas Cita | sesión activa, cita_id | `GET /api/notas/{cita_id}`, `POST /api/notas/{cita_id}` | Form nueva nota, lista notas previas, flash éxito |

---

## 4. Diagrama Mermaid del Flujo Principal

```mermaid
flowchart TD
    A[Index /] -->|Login| B[Login /login]
    B -->|rol admin| C[Panel Admin /panel_admin]
    B -->|rol terapeuta| D[Interfaz /interfaz]
    D -->|Abrir Citas| E[Citas /citas (agendar)]
    E -->|Con pago| F[Pago /pago?cita_id=X]
    F -->|Éxito| G[Retorno /retorno?cita_id=X]
    E -->|Tratamiento| H[Tratamiento /tratamiento]
    H -->|Paquetes activos| I[Seleccionar paquete + agendar sesión]
    I -->|Post‑pago| F
    C -->|Gestión médicos/usuarios/citas| J[Panel Admin sub‑views]
    J -->|Auditoría| K[Panel Admin Auditoría /panel_admin/auditoria]
    J -->|KPIs| L[Panel Admin KPIs /panel_admin/kpis]
    style A fill:#f9f,stroke:#333,stroke-width:2px
    style B fill:#bbf,stroke:#333,stroke-width:2px
    style C fill:#ccf,stroke:#333,stroke-width:2px
    style D fill:#bbf,stroke:#333,stroke-width:2px
    style E fill:#cfc,stroke:#333,stroke-width:2px
    style F fill:#cfc,stroke:#333,stroke-width:2px
    style G fill:#cfc,stroke:#333,stroke-width:2px
```

---

## 5. Conclusión

MOOVA Clinic presenta una arquitectura de microservicios Flask totalmente separada por dominio (auth, pacientes, citas, pagos, notas, auditoría) sobre bases de datos divididas, lo que garantiza aislamiento y escalabilidad. El flujo de usuario cubre todo el ciclo de vida de una cita: desde la primera visita en la página pública, pasando por la autenticación del personal, la agendación con validaciones de formato y disponibilidad, la elección y cobro del método de pago (Yape, Plin y tarjeta Niubiz, todos confirmados en el backend) hasta la confirmación final y la gestión administrativa. Todas las pantallas están cubiertas por vistas HTML con Bootstrap 5 y Javascript interactivo, y los datos de origen se obtienen mediante endpoints API bien definidos y stored procedures sobre las 7 bases de datos `moovacloud_*`. Queda pendiente únicamente la configuración de credenciales reales en producción (APIPERU, TextBEE, Yape, Plin y Niubiz) y la confirmación de los roles más allá de `admin`/`terapeuta`.

---

## 6. Pendiente de verificar en producción

- **Credenciales de proveedores externos:** los clientes de Yape, Plin y Niubiz (`shared/payments/`), APIPERU y TextBEE ya están implementados y devuelven un error explícito al usuario cuando faltan credenciales, pero requieren valores reales en el `.env` de producción para funcionar.
- **APIPERU validación DNI:** el endpoint `/api/verificar_dni` consulta a una API externa; su éxito depende de la clave `APIPERU_TOKEN` y de la disponibilidad del servicio.
- **TextBEE SMS:** usa `TEXTBEE_API_KEY`, `TEXTBEE_DEVICE_ID` y `TEXTBEE_URL`. Sin ellos, el envío de OTP responde `500 "No se pudo enviar el SMS."` (falla de forma visible). Los SMS de confirmación de pago son avisos de cortesía y se omiten en silencio si fallan, sin afectar el cobro ya confirmado.
- **Roles adicionales:** el código distingue `admin` y `terapeuta`; no se observan roles de `paciente` en el flujo de sesión (el público accede a citas/pago/retorno sin login). Queda confirmar si el paciente tiene un rol propio en bases o es puramente público.
- **Transferencia bancaria:** el panel de pago informa que el método no tiene integración contratada y que hay que contactar con administración; no hay cobro automático.