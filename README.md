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