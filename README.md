# MOOVA Clinic

Sistema de gestión de una clínica de fisioterapia: agenda de citas,
historia clínica, notas, paquetes de sesiones y cobros por pasarela.

Arquitectura de monolito modular sobre Flask: un solo proceso ejecuta el
gateway y los seis módulos de dominio. Sus rutas se llaman dentro del proceso
bajo `/_internal`; los módulos no se despliegan ni se comunican como procesos
separados.

---

## Arquitectura

```
                   ┌─────────────────────────────────────────┐
                   │ Un proceso Flask/Gunicorn: gateway       │
                   │ páginas + módulos bajo /_internal        │
                   └────────────────────┬────────────────────┘
                                        │ llamadas en proceso
          ┌─────────┬──────────┬────────┼─────────┬────────┐
          ▼         ▼          ▼        ▼         ▼        ▼
       auth     pacientes    citas    pagos     notas   auditoría
          │         │          │        │         │        │
          ▼         ▼          ▼        ▼         ▼        ▼
       esquema   esquema    esquema  esquema   esquema  esquema
          └─────────┴──────────┴────────┴─────────┴────────┘
                       + esquema moovacloud_kpis
```

Cada módulo conserva su propio esquema MySQL. Son siete esquemas en total,
incluido el esquema de KPIs. `shared/service_client.py` mantiene la interfaz
de cliente entre módulos, pero despacha todas las llamadas dentro del mismo
proceso, sin peticiones de red internas.

`services/*/` contiene los módulos de dominio y sus blueprints; `shared/`
contiene configuración, acceso a BD por procedimientos, auditoría,
validación, fechas y el cliente interno.

---

## Requisitos

- Python 3.11 (probado también en 3.12)
- MySQL 8 con las 7 bases creadas desde `db_split/`
- Docker, solo si se quiere levantar con `docker compose`

---

## Puesta en marcha

### 1. Dependencias

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
source .venv/bin/activate     # Linux/Mac
pip install -r requirements.txt
```

### 2. Bases de datos

Cada `db_split/*.sql` crea su base y sus procedimientos. Son independientes,
así que el orden no importa:

```bash
mysql -u USUARIO -p < db_split/auth_db.sql
mysql -u USUARIO -p < db_split/pacientes_db.sql
mysql -u USUARIO -p < db_split/citas_db.sql
mysql -u USUARIO -p < db_split/pagos_db.sql
mysql -u USUARIO -p < db_split/notas_db.sql
mysql -u USUARIO -p < db_split/audit_db.sql
mysql -u USUARIO -p < db_split/kpis_db.sql
```

Después de aplicar cambios en los `.sql`, hay que volver a importarlos:
el proyecto usa procedimientos almacenados, no un ORM con migraciones.

### 3. Variables de entorno

Copiar `.env.example` a `.env` y completar:

```bash
cp .env.example .env
```

Variables esenciales del gateway:

| Variable | Para qué |
|---|---|
| `SECRET_KEY` | Firma de la sesión. El arranque falla si falta. |
| `API_KEY` | Protege las llamadas internas; sin ella se rechazan con 503. |

El gateway usa las credenciales de conexión comunes y los nombres de esquema
por dominio definidos en `.env.example`; no hace falta crear archivos `.env`
por módulo.

Los `.env` están en `.gitignore`. No se suben nunca.

### 4. Arrancar

Un solo proceso configura el gateway y los seis módulos internos:

```bash
python run.py
```

Con Docker Compose:

```bash
docker compose up --build
```

La app queda en <http://127.0.0.1:5000>. La API interna está documentada
en <http://127.0.0.1:5000/apidocs/>, que pide sesión de administrador
(ver `Documentación de la API solo para administradores`).

---

## Seguridad

- **La auth interna no falla abierta.** Sin `API_KEY`, las rutas internas
  responden `503` y rechazan las llamadas. Para desarrollo local se puede
  desactivar la validación con `ALLOW_INSECURE_INTERNAL_API=1` (solo con
  warning en el log).
  Nunca en producción.
- **Solo el gateway es público.** Las rutas de los módulos bajo `/_internal`
  rechazan llamadas externas; las invocaciones del proceso se autentican con
  `X-Api-Key`. El webhook y el job de mantenimiento tienen excepciones
  específicas.
- **CSRF** activo en todos los POST (`flask_wtf.csrf.CSRFProtect`).
- **`SECRET_KEY` es obligatoria**: el arranque falla sin ella, en lugar de
  generar una que invalide las sesiones en cada reinicio.
- **Cookies de sesión**: `HttpOnly` y `SameSite=Lax`. Para que lleven
  `Secure` (solo HTTPS) hay que definir `FLASK_ENV=production`, que es lo
  que hace `render.yaml` en el gateway.
- **`buscar_dni` devuelve lo mínimo**: el flujo de reserva solo necesita
  nombres y apellidos, así que no se retransmite el expediente completo que
  devuelve APIPERU.
- **El login tiene límite de intentos** (`shared/rate_limit.py`), ver
  detalle más abajo.
- **Limitación aceptada**: `/pago` y `/retorno` no comprueban que la
  cita pertenezca al usuario de la sesión, ver el apartado
  `Oráculo de existencia de citas` más abajo.
- **La documentación de la API es de administradores** (`/apidocs`,
  `/apispec_1.json`), ver detalle más abajo.

### Límite de intentos de login

`/login` aceptaba prueba tras prueba de clave sin que nada se lo
impidiera. El gateway ahora cuenta los fallos y corta el intento
**antes** de llamar al módulo de autenticación, que no recibe los intentos
que ya superaron el límite.

Hay dos contadores independientes y **ambos tienen que pasar**:

| Clave | Corta a |
| --- | --- |
| `ip:<ip>` | quien prueba muchas claves desde un solo equipo |
| `correo:<correo>` | quien prueba un mismo correo desde muchas IPs |

Defaults: `LOGIN_MAX_INTENTOS=5` fallos dentro de `LOGIN_VENTANA_MIN=10`
minutos bloquean `LOGIN_BLOQUEO_MIN=15` minutos. Al entrar bien se borra
el historial de esas claves, para que cinco typos de la mañana no dejen
al usuario real bloqueado.

Los mensajes son fijos y no dependen de lo que devuelva el
módulo interno: ni el bloqueo ni la clave incorrecta dicen si el correo
existe o no, y son indistinguibles entre sí.

Detrás de un proxy (Render, nginx) `request.remote_addr` es la IP del
proxy y todas las peticiones parecen venir del mismo sitio. Con
`TRUST_PROXY=1` se toma el primer valor de `X-Forwarded-For`, que es el
que anotó el proxy. **Sin esa variable el header se ignora**: cualquiera
podría mandarlo inventado y quedar sin contador.

> **Limitación conocida.** El contador vive en un `dict` en memoria del
> proceso, sin base de datos ni dependencias nuevas. Eso significa que
> **cada worker tiene el suyo** (con dos workers un atacante tiene el
> doble de intentos) y que **un reinicio del servicio lo pone a cero**.
> Es suficiente para el alcance actual y es deliberado; si algún día hace
> falta compartirlo entre procesos, lo que hay que reemplazar es el
> almacenamiento del `LimitadorIntentos`, no su lógica.

### Cabeceras de seguridad

Un `after_request` único del gateway (`_cabeceras_de_seguridad`) pone en
**todas** las respuestas, incluidas las de error y las de las plantillas:

| Cabecera | Valor |
| --- | --- |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `SAMEORIGIN` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |

`Strict-Transport-Security: max-age=31536000` se añade **solo con
`FLASK_ENV=production`**. En desarrollo por `http` avisarle al navegador
que use `https` siempre dejaría la app inaccesible en local y no hay una
forma cómoda de deshacerlo.

Se usa `setdefault`, de modo que una ruta que fije una de estas cabeceras
a propósito no la ve pisada.

**Mejora futura pendiente: CSP.** No se define `Content-Security-Policy`
todavía. Plantillas con scripts en línea, `report-uri` y las fuentes de
Google Fonts hacen que una política estricta rompa páginas en cuanto se
mueva una plantilla; plantearlo bien merece una fase aparte con revisión
página por página, no un encabezado de relleno.

### Oráculo de existencia de citas (limitación aceptada)

`/pago` y `/retorno` piden `cita_id` por query y **no comprueban que la
cita pertenezca al usuario de la sesión**: ahí solo hay `_login_required`.
Con una sesión cualquiera, recorrer `GET /pago?cita_id=N` distingue estos
casos (comprobado con el flujo de prueba real):

| Respuesta | Significa |
| --- | --- |
| `302` a `/retorno` | la cita existe y ya está pagada |
| `302` a `/citas` | no hay un pago registrado para esa cita |
| `200` con el importe | existe y está pendiente, con su monto |

Y cuando la cita existe, la página se pinta con lo que enriquece
`citas_service`: nombre y apellido del paciente, terapeuta, especialidad
y fecha; en `/retorno` se añade además la referencia del cobro. No salen
ni el DNI ni el teléfono ni datos clínicos, pero sí a quién pertenece la
cita.

> **Limitación aceptada (FASE S7, punto d).** Es un oráculo de
> existencia, no un robo de dinero: no toca pasarelas ni saldos, y no
> exige nada más que una sesión abierta. **Se documenta en lugar de
> arreglarse** porque corregirlo exige que el gateway resuelva el dueño
> de la cita (usuario → paciente → citas) y filtre `/pago`, `/retorno`
> y la lista `session["citas_pagables"]` con esa comprobación; eso es
> un cambio de la ruta de sesión, no de las pasarelas, y queda fuera de
> S7. Lo que S7 sí cerró está en los puntos a, b y c:
> `/estado` solo confirma con la referencia guardada y comprobando
> referencia y monto, `sp_guardar_referencia` ya no pisa pagos pagados,
> y los cuatro proxies de Yape/Plin exigen que esta misma sesión haya
> abierto `/pago` para esa cita.
>
> A mitad del recorrido tampoco se distingue "no existe" de "ya estaba
> pagada": `pagos_service` devuelve el mismo texto en los dos casos, así
> que el detalle fino solo sale de `/pago`.

### Documentación de la API solo para administradores

flasgger monta `/apidocs` y `/apispec_1.json` sin proteger nada y el
gateway no tenía ningún `before_request`, así que cualquiera podía
leer el plano completo de la API interna: las 54 rutas del
`swagger.yaml`, con los endpoints de Yape/Plin incluidos. No es un
agujero de datos por sí solo —no devuelve nombres, importes ni
claves—, pero sí es el mapa de la casa y el modo de usar cada
endpoint.

Un `before_request` del gateway (`_documentacion_interna`) deja pasar
solo a quien tiene sesión de **administrador**; todo lo demás acaba en
`/login`, igual que hace `_admin_required` con el resto de rutas de
gestión. Cubre `/apidocs`, `/apidocs/...` y cualquier
`/apispec_<n>.json`, de modo que si flasgger sirve otro spec algún día
sigue cubierto.

Sin sesión de admin la documentación sigue disponible en el propio
`swagger.yaml` del repositorio: lo que se restringe es el servicio
publicado, no el código.

---

## Pagos

Anticipo del 50% del precio del terapeuta, creado por `citas_service` al
agendar. Pasarelas: **Yape**, **Plin** (QR) y **Niubiz** (tarjeta).

Los clientes están en `services/pagos_service/providers.py` y son reales:
consultan la API del proveedor y no simulan éxito. Si faltan
credenciales, el módulo responde "proveedor no configurado" en vez de
dar el pago por bueno.

`/retorno` no marca nada como pagado por su cuenta: consulta el estado en
la pasarela y solo confirma si el proveedor dice que se pagó.

### Expiración de pagos pendientes

Una cita abandonada a mitad del pago quedaba bloqueada sin límite. El job
`liberar_pagos_vencidos` marca como `vencido` los pendientes con más de
24 h (configurable) y cancela la cita asociada con la nota `pago vencido`,
para que ese día vuelva a estar disponible. Solo cancela citas programadas;
las completadas no se modifican. Si falla temporalmente la llamada entre
servicios, la siguiente ejecución vuelve a intentar cancelar la cita.

El gateway ejecuta esta tarea cada hora en su propio proceso. Está habilitada
por defecto y se puede desactivar configurando `LIBERAR_VENCIDOS_ENABLED=0`.
No hace falta un cron externo en Railway.

```bash
python scripts/liberar_pagos_vencidos.py 24
```

El script manual se conserva para ejecuciones puntuales y requiere `GATEWAY_URL`
y `API_KEY`. Sale con código distinto de 0 si falla, para que el programador
externo lo reporte.

Un pago que el proveedor confirme después de expirado sigue
confirmándose: `sp_confirmar_pago` acepta `pendiente` y `vencido`. El
dinero entró igual y descartarlo dejaría al paciente cobrado sin cita.

### Webhook

La URL del webhook es
`https://<dominio-del-gateway>/_internal/api/pagos/webhook`. Está exenta de
la API_KEY interna y se autentica con `WEBHOOK_PROVIDER_TOKEN` en
`X-Provider-Token` o `X-Signature`. Si no hay token configurado, responde
503; si el token no coincide, responde 401.

---

## Recordatorios automáticos

El paciente llegaba el día de la cita sin saber que tenía una. Ahora
el módulo de citas envía un SMS de aviso la tarde anterior a las citas del
día siguiente, usando la columna `historial_citas.recordatorio_enviado`,
que hasta ahora no usaba nadie.

### Cómo funciona

- `enviar_recordatorios()` pide las citas del día con
  `sp_citas_pendientes_recordatorio` (solo `programada` y `confirmada`;
  una cancelada no debe recibir SMS).
- Cada cita se **reclama** con `sp_marcar_recordatorio_enviado`. Si dos
  procesos corren a la vez, solo uno recibe `marcadas=1` y el otro la
  salta, así no se mandan SMS duplicados.
- Si el paciente no tiene teléfono, o el SMS falla, se desmarca con
  `sp_desmarcar_recordatorio` para que el siguiente ciclo reintente.

Los datos necesarios de pacientes y terapeutas se obtienen mediante
llamadas en proceso al módulo de pacientes.

### Envío automático (APScheduler)

Deshabilitado por defecto. Para encenderlo, configura estas variables en
el `.env` único del gateway:

```env
RECORDATORIOS_ENABLED=1
RECORDATORIO_HORA=18:00
RECORDATORIO_INTERVALO_MIN=15
```

El scheduler arranca desde `create_app()` solo si
`RECORDATORIOS_ENABLED=1`. Corre un job cada
`RECORDATORIO_INTERVALO_MIN` minutos, pero solo actúa si en
**America/Lima** ya se alcanzó `RECORDATORIO_HORA`, para no mandar
mensajes a cualquier hora. El job nunca tumbaría el proceso: si algo
falla, se loguea y sigue.

### Envío manual

La ruta interna `/_internal/api/citas/recordatorios/enviar` dispara el envío
en el momento. Solo es accesible desde el proceso con la API_KEY interna;
no se expone como endpoint público. El cuerpo es opcional:

```json
{ "fecha": "2026-10-19" }
```

Sin `fecha` usa el día siguiente (America/Lima). Devuelve
`{total, enviados, fallidos, sin_telefono}`.

La invocación interna funciona aunque el scheduler esté apagado y sirve
para pruebas controladas.

### Migración sobre una base existente

Los tres procedimientos nuevos están en `db_split/citas_db.sql`
(instalación nueva) y en
`db_split/migraciones/2026-10-18_recordatorios_citas.sql` (base con
datos). La migración solo define procedimientos: no toca tablas ni
inserta nada. Tampoco hace falta `ALTER TABLE`, porque la columna
`recordatorio_enviado` ya existía.

---

## Reporte de riesgo de fuga

Un paciente que deja de venir casi nunca avisa: nadie se entera hasta
que alguien lo pregunta. El reporte lista a los que muestran señales
de abandono para que reception los llame antes de perderlos.

Se ve en **`/panel_admin/riesgo`** (solo admin) y se sirve en
`GET /api/citas/riesgo`.

### Cómo se decide quién está en riesgo

Todo se calcula con datos de `moovacloud_citas`: no hay consultas
cruzadas entre bases. `sp_pacientes_en_riesgo` marca a un paciente si:

- no tiene ninguna cita futura `programada`/`confirmada` y ya pasaron
  más de `RIESGO_DIAS_UMBRAL` días desde su última cita, o
- faltó (`estado = no_asistio`) tres o más veces.

El SP devuelve las métricas crudas (última cita, días, citas
programadas/completadas/canceladas/perdidas). El módulo agrega el
nombre y el teléfono mediante llamadas en proceso al módulo de pacientes,
más el nivel y un motivo en texto para el panel.

### Nivel de criticidad

- **alto**: faltó tres o más veces, o ya pasó el doble del umbral sin
  venir.
- **medio**: el resto.

### Configuración

```env
RIESGO_DIAS_UMBRAL=30
```

Se puede cambiar por petición con
`?fecha=YYYY-MM-DD&dias_umbral=N`. Las fechas se interpretan como
hoy en America/Lima.

---

## Aviso al terapeuta por SMS

Cuando una cita se cancela o se reprograma, el terapeuta se entera
en el momento en vez de al llegar a la clínica. El aviso va por SMS
(TextBee, el mismo canal que el OTP y los recordatorios).

### Cuándo se envía

Solo cuando cambia algo que le afecta: **fecha, hora o terapeuta**.

- **Cambio de terapeuta**: 2 SMS. Al que pierde la cita:
  `MOOVA Clinic: Se libero tu cita del 25/10 a las 10:00 (paciente Ana).`
  Al que la recibe: `MOOVA Clinic: Te asignaron una cita del 25/10 a las 10:00 (paciente Ana).`
- **Cambia solo fecha u hora**: 1 SMS con la nueva fecha/hora.
- **Cambio que no toca esos tres campos**: 0 SMS.

El texto va en ASCII, sin tildes, y sin DNI ni teléfono del paciente
(a lo sumo el nombre de pila), igual que los demás SMS.

### El teléfono de dónde sale

El enlace es `terapeuta → usuario → teléfono` y se resuelve mediante
llamadas internas en proceso:

1. `terapeuta_id → usuario_id` con `_mapa_terapeutas()`
   (módulo de pacientes).
2. `usuario_id → telefono` (módulo de autenticación).

### Si no hay teléfono

Nada falla. El `DELETE`/`PUT` de la cita responde igual; lo único que
queda es un registro de auditoría con `accion = avisar_terapeuta` y el
motivo (`sin_telefono`, `sms_fallido`, `error`).

### Cargar el teléfono

`/panel_admin` → *Usuarios del Sistema*: la columna **Teléfono** tiene
un input por fila con botón guardar. Acepta 9 dígitos que empiezan por
9 (o vacío para borrar), en el formulario y también en el servidor
(`PUT /api/auth/usuarios/{id}`).

Los registros de `avisar_terapeuta` se guardan en el esquema
`moovacloud_auditoria` mediante el módulo interno de auditoría.

### Migración

`db_split/migraciones/2026-10-18_telefono_usuarios.sql` sobre la base
**`moovacloud_auth`** (no citas). Define solo 2 procedimientos:
`sp_listar_usuarios` (ahora devuelve `telefono`) y el nuevo
`sp_actualizar_telefono_usuario`. El orden entre migración y código es
indiferente: al ser un procedimiento nuevo, editar usuarios sin
teléfono sigue funcionando aunque el código llegue antes.

---

## Desarrollo

### Tests y lint

```bash
pytest              # 27 tests
ruff check .        # debe salir limpio
```

Los tests no tocan MySQL: `shared.proc` se parchea. Igual hay que definir
`SECRET_KEY` y `API_KEY` porque ambos son obligatorios en el arranque.

### Comprobaciones de coherencia

```bash
python scripts/auditar_procs.py    # procedimientos definidos vs invocados
python scripts/verificar_swagger.py  # rutas reales vs swagger.yaml
```

Ambos salen con código 1 si algo no cuadra, y corren en CI.

### CI

`.github/workflows/ci.yml` corre en cada push y PR:

| Job | Qué verifica |
|---|---|
| lint | `ruff check .` |
| tests | `pytest` |
| audit-python | `pip-audit` (CVE conocidas) |
| sql-estatico | procedimientos huérfanos o inexistentes |
| swagger | rutas documentadas == rutas reales |

---

## Despliegue

### Render

`render.yaml` define un solo servicio web, `moova-gateway`, más el cron de
pagos vencidos. Las credenciales se definen en el panel (`sync: false`),
nunca con valores reales en el archivo.
La base de datos **no** se crea desde Render: es el MySQL del hosting.

Las variables y credenciales de base de datos, proveedores, recordatorios y
webhook se configuran en `moova-gateway`; el cron recibe `GATEWAY_URL` y
`API_KEY`.

### Backups

`backup_db.sh` respalda las 7 bases y sale con código 1 si alguna falla.
Se ejecuta desde el cron de Alwaysdata:

```bash
bash ~/backup_db.sh
```

Exige `DB_PASSWORD` en el entorno (nunca en el archivo). Guarda 7 días en
`~/backups` y comprueba el tamaño de cada volcado: `mysqldump` con
credenciales malas produce un `.gz` de ~30 bytes que naïve parece válido.

Alternativa más simple: el backup nativo del panel de Alwaysdata, que
cubre las 7 bases de una vez.

---

## Estructura

```
gateway/            Flask + plantillas Jinja (la UI)
  app.py            rutas, sesión, CSRF, decoradores de acceso
  ficha_pdf.py      generador de la ficha clínica en PDF
services/           seis módulos registrados bajo /_internal
  auth_service/     usuarios, roles, login
  pacientes_service/ pacientes, terapeutas, DNI (APIPERU)
  citas_service/    agenda, disponibilidad, OTP por SMS, KPIs
  pagos_service/    anticipos, pasarelas, webhook, paquetes
  notas_service/    notas clínicas
  audit_service/    registro de auditoría
shared/             código común
  config.py         variables de entorno (falla si falta SECRET_KEY)
  service_auth.py   protección interna del header X-Api-Key
  service_client.py cliente en proceso entre módulos
  proc.py           llamadas a procedimientos almacenados
  db.py             conexión MySQL
  audit.py          auditoría centralizada
  validators.py     validación de datos de paciente
  fechas.py         formateo de fechas
db_split/           un .sql por base de datos
templates/          Jinja2
scripts/            tareas de mantenimiento (cron)
tests/              pytest
```

---

## Documentación adicional

- `INFO_INTERFACES.md` — detalle de cada endpoint interno.
- `swagger.yaml` — especificación de la API interna (54 rutas).
- <http://127.0.0.1:5000/apidocs/> — documentación interactiva (solo
  con sesión de administrador; sin ella manda a `/login`).
- `.env.example` — variables consolidadas del gateway.

---

## Notas conocidas

- La transferencia bancaria no está integrada: solo Yape, Plin y Niubiz.
- No hay reembolsos automáticos. Cancelar una cita cancela el pago
  pendiente, pero no hay flujo de devolución de dinero.
- El rol `paciente` existe en la tabla de roles pero no tiene login: el
  acceso del paciente es por DNI + OTP.
- Cualquier usuario con sesión puede mirar `/pago?cita_id=N` y saber si
  la cita existe, si está pagada y a quién pertenece: el gateway no
  valida la propiedad de la cita. Limitación aceptada de la FASE S7,
  detallada en `Oráculo de existencia de citas` (apartado Seguridad).