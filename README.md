# MOOVA Clinic

Sistema de gestión de una clínica de fisioterapia: agenda de citas,
historia clínica, notas, paquetes de sesiones y cobros por pasarela.

Arquitectura de microservicios sobre Flask. El gateway es la única cara
visible; toda la lógica de negocio vive en los servicios, que se comunican
por HTTP interno y nunca se exponen al público.

---

## Arquitectura

```
                    ┌──────────────┐
                    │   Gateway    │  :5000  (único puerto público)
                    │  Flask + Jinja│
                    └──────┬───────┘
                           │  X-Api-Key (auth interna)
        ┌──────────┬───────┼───────┬──────────┬──────────┐
        ▼          ▼       ▼       ▼          ▼          ▼
    ┌───────┐ ┌─────────┐ ┌─────┐ ┌───────┐ ┌───────┐ ┌──────┐
    │ auth  │ │pacientes│ │citas│ │pagos  │ │notas  │ │audit │
    │ :5001 │ │  :5002  │ │:5003│ │ :5004 │ │ :5005 │ │ :5006│
    └───┬───┘ └────┬────┘ └──┬──┘ └───┬───┘ └───┬───┘ └──┬───┘
        │         │         │        │         │        │
   moovacloud_ moovacloud_ moovacloud_ moovacloud_ moovacloud_ moovacloud_
     _auth       _pacientes  _citas     _pagos    _notas    _auditoria
                                                              │
                                              ┌───────────────┴──┐
                                              │  moovacloud_kpis │
                                              │  (solo lectura)  │
                                              └──────────────────┘
```

Cada servicio tiene su propia base de datos en el mismo servidor MySQL.
**No hay consultas cruzadas entre bases**: cuando un servicio necesita
datos de otro, lo pide por HTTP (`shared/service_client.py`). Ese fue el
cambio central de la FASE 2.

`services/*/` contiene un servicio, `shared/` el código común
(configuración, acceso a BD por procedimientos, auditoría, validación,
fechas, cliente HTTP entre servicios, auth interna).

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

Obligatorias en todas partes:

| Variable | Para qué |
|---|---|
| `SECRET_KEY` | Firma de la sesión. El arranque falla si falta. |
| `API_KEY` | Auth interna. Sin ella los servicios responden 503. |

Cada servicio necesita además sus credenciales de BD en
`services/<servicio>/.env` (ver `services/<servicio>/.env.example`).

Los `.env` están en `.gitignore`. No se suben nunca.

### 4. Arrancar

Un solo proceso (requiere las variables `*_SERVICE_URL` apuntando a los
servicios ya levantados):

```bash
python run.py
```

Los 7 a la vez con Docker:

```bash
docker compose up --build
```

Solo el gateway publica el puerto `5000`. Para desarrollo en paralelo,
cada servicio se puede lanzar por separado:

```bash
python -m services.auth_service.run      # :5001
python -m services.pacientes_service.run # :5002
python -m services.citas_service.run     # :5003
python -m services.pagos_service.run     # :5004
python -m services.notas_service.run     # :5005
python -m services.audit_service.run     # :5006
```

La app queda en <http://127.0.0.1:5000>. La API interna está documentada
en <http://127.0.0.1:5000/apidocs/>.

---

## Seguridad

- **La auth interna no falla abierta.** Sin `API_KEY`, un servicio
  responde `503` y rechaza todo. Para desarrollo local se puede desteure
  con `ALLOW_INSECURE_INTERNAL_API=1` (solo con warning en el log).
  Nunca en producción.
- **Solo el gateway es público.** En Docker Compose los servicios no
  publican puertos; en Render cada uno exige el `X-Api-Key` del gateway.
- **CSRF** activo en todos los POST (`flask_wtf.csrf.CSRFProtect`).
- **`SECRET_KEY` es obligatoria**: el arranque falla sin ella, en lugar de
  generar una que invalide las sesiones en cada reinicio.
- **Cookies de sesión**: `HttpOnly` y `SameSite=Lax`. Para que lleven
  `Secure` (solo HTTPS) hay que definir `FLASK_ENV=production`, que es lo
  que hace `render.yaml` en el gateway.
- **`buscar_dni` devuelve lo mínimo**: el flujo de reserva solo necesita
  nombres y apellidos, así que no se retransmite el expediente completo que
  devuelve APIPERU.

---

## Pagos

Anticipo del 50% del precio del terapeuta, creado por `citas_service` al
agendar. Pasarelas: **Yape**, **Plin** (QR) y **Niubiz** (tarjeta).

Los clientes están en `services/pagos_service/providers.py` y son reales:
consultan la API del proveedor y no simulan éxito. Si faltan
credenciales, el servicio responde "proveedor no configurado" en vez de
dar el pago por bueno.

`/retorno` no marca nada como pagado por su cuenta: consulta el estado en
la pasarela y solo confirma si el proveedor dice que se pagó.

### Expiración de pagos pendientes

Una cita abandonada a mitad del pago quedaba bloqueada sin límite. El job
`liberar_pagos_vencidos` marca como `vencido` los pendientes con más de
24 h (configurable) para que la cita vuelva a estar disponible.

```bash
python scripts/liberar_pagos_vencidos.py 24
```

Requiere `PAGOS_SERVICE_URL` y `API_KEY`. Sale con código distinto de 0 si
falla, para que cron lo reporte. En Render ya está configurado el cron
`liberar-pagos-vencidos` (cada hora).

Un pago que el proveedor confirme después de expirado sigue
confirmándose: `sp_confirmar_pago` acepta `pendiente` y `vencido`. El
dinero entró igual y descartarlo dejaría al paciente cobrado sin cita.

### Webhook

`POST /api/pagos/webhook` es la única ruta exenta de la API_KEY interna.
Se autentica con `WEBHOOK_PROVIDER_TOKEN` en `X-Provider-Token` o
`X-Signature`. **Si la variable está vacía, el webhook acepta cualquier
petición**: defínela siempre, también en desarrollo.

---

## Recordatorios automáticos

El paciente llegaba el día de la cita sin saber que tenía una. Ahora
`citas_service` envía un SMS de aviso la tarde anterior a las citas del
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

Los datos del paciente y del terapeuta se piden por HTTP a
`pacientes_service`: no hay consultas cruzadas entre bases.

### Envío automático (APScheduler)

Deshabilitado por defecto. Para encenderlo, en el `.env` de
`citas_service`:

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

`POST /api/citas/recordatorios/enviar` dispara el envío en el momento.
Va protegido con la API_KEY interna. El cuerpo es opcional:

```json
{ "fecha": "2026-10-19" }
```

Sin `fecha` usa el día siguiente (America/Lima). Devuelve
`{total, enviados, fallidos, sin_telefono}`.

Funciona aunque el scheduler esté apagado: sirve para un disparo
manual o para pruebas.

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
programadas/completadas/canceladas/perdidas). El servicio agrega el
nombre y el teléfono, que se piden por HTTP a `pacientes_service`, más
el nivel y un motivo en texto para el panel.

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

El enlace es `terapeuta → usuario → teléfono` y se resuelve **todo por
HTTP**, sin consultas cruzadas entre bases:

1. `terapeuta_id → usuario_id` con `_mapa_terapeutas()`
   (`GET /api/terapeutas` de `pacientes_service`).
2. `usuario_id → telefono` con `GET /api/auth/usuarios` (`auth_service`).

### Si no hay teléfono

Nada falla. El `DELETE`/`PUT` de la cita responde igual; lo único que
queda es un registro de auditoría con `accion = avisar_terapeuta` y el
motivo (`sin_telefono`, `sms_fallido`, `error`). Las llamadas HTTP del
aviso usan timeout de 5 s.

### Cargar el teléfono

`/panel_admin` → *Usuarios del Sistema*: la columna **Teléfono** tiene
un input por fila con botón guardar. Acepta 9 dígitos que empiezan por
9 (o vacío para borrar), en el formulario y también en el servidor
(`PUT /api/auth/usuarios/{id}`).

> Si `moovacloud_auth` no tiene `AUDIT_SERVICE_URL`, los registros de
> `avisar_terapeuta` no llegarán a la base de auditoría en producción
> (el error se traga y nada se rompe).

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

`render.yaml` define los 7 servicios web más el cron de pagos. Las
credenenciales se definen en el panel (`sync: false`), nunca en el archivo.
La base de datos **no** se crea desde Render: es el MySQL del hosting.

Al desplegar hay que definir como mínimo: `SECRET_KEY`, `API_KEY`,
credenciales de BD en los 6 servicios, credenciales de las pasarelas y
`WEBHOOK_PROVIDER_TOKEN`.

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
services/           un microservicio por dominio
  auth_service/     usuarios, roles, login
  pacientes_service/ pacientes, terapeutas, DNI (APIPERU)
  citas_service/    agenda, disponibilidad, OTP por SMS, KPIs
  pagos_service/    anticipos, pasarelas, webhook, paquetes
  notas_service/    notas clínicas
  audit_service/    registro de auditoría
shared/             código común
  config.py         variables de entorno (falla si falta SECRET_KEY)
  service_auth.py   auth interna del header X-Api-Key
  service_client.py cliente HTTP entre servicios
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
- `swagger.yaml` — especificación de la API interna (52 rutas).
- <http://127.0.0.1:5000/apidocs/> — documentación interactiva.
- `.env.example` — todas las variables, con las de cada servicio comentadas.

---

## Notas conocidas

- La transferencia bancaria no está integrada: solo Yape, Plin y Niubiz.
- No hay reembolsos automáticos. Cancelar una cita cancela el pago
  pendiente, pero no hay flujo de devolución de dinero.
- El rol `paciente` existe en la tabla de roles pero no tiene login: el
  acceso del paciente es por DNI + OTP.