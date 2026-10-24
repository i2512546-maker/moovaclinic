# Despliegue de MOOVA Clinic

MOOVA Clinic se despliega como un monolito modular: un único servicio web
`moova-gateway` ejecuta Flask/Gunicorn y registra los seis módulos internos
bajo `/_internal`. Render también ejecuta un cron separado para liberar pagos
vencidos. Las siete bases MySQL siguen siendo independientes; no se deben
recrear ni combinar durante este despliegue.

## 1. Migraciones de base de datos

Ejecuta cada archivo en la base indicada, antes de desplegar el código. Estas
migraciones actualizan procedimientos almacenados y no sustituyen la
importación inicial de las bases.

| Archivo de `db_split/migraciones/` | Base donde se ejecuta | Qué agrega |
|---|---|---|
| `2026-10-18_recordatorios_citas.sql` | `moovacloud_citas` | Procedimientos de recordatorios SMS |
| `2026-10-18_pacientes_en_riesgo.sql` | `moovacloud_citas` | Reporte de pacientes en riesgo |
| `2026-10-18_telefono_usuarios.sql` | `moovacloud_auth` | Consulta y actualización del teléfono del usuario |
| `2026-10-19_pagos_guardar_referencia.sql` | `moovacloud_pagos` | Guardado de referencia de pago pendiente |

Para cada archivo: abre la base correspondiente en phpMyAdmin, entra a
**SQL**, pega el contenido y ejecuta. No importes nuevamente todos los
`db_split/*.sql` en una base existente. Comprueba el resultado con:
`SHOW PROCEDURE STATUS WHERE Db = DATABASE();`.

Las migraciones por base siguen igual aunque la aplicación se ejecute en un
solo proceso: cada módulo mantiene su esquema y sus procedimientos.

## 2. Servicio web, variables y recordatorios

`render.yaml` define un solo servicio web, **`moova-gateway`**, que contiene
las variables comunes, las credenciales de base de datos, integraciones
externas y configuración del scheduler. Los secretos se cargan en el panel
de Render; no deben guardarse en el repositorio.

Los recordatorios se ejecutan en el proceso del gateway. Para habilitarlos,
configura en el entorno de **`moova-gateway`**:

| Variable | Valor de referencia |
|---|---|
| `RECORDATORIOS_ENABLED` | `1` |
| `RECORDATORIO_HORA` | `18:00` |
| `RECORDATORIO_INTERVALO_MIN` | `15` |

Verifica también `TEXTBEE_API_KEY` y `TEXTBEE_DEVICE_ID`. El scheduler se
inicia una sola vez y solo cuando `RECORDATORIOS_ENABLED=1`. El servicio web
debe permanecer activo a la hora programada para que se envíen los SMS.
Antes de activarlo en producción, prueba con un paciente y número controlados.

## 3. Webhook de pagos

Configura en el proveedor la URL:

`https://<dominio-del-gateway>/_internal/api/pagos/webhook`

Define `WEBHOOK_PROVIDER_TOKEN` en el entorno de `moova-gateway` y configura
el mismo token en el proveedor. El webhook no usa `API_KEY`; valida el token
del proveedor. Si el token no está configurado, el endpoint falla cerrado.

## 4. Cron de pagos vencidos

Render mantiene el cron `liberar-pagos-vencidos`, que apunta a
`GATEWAY_URL` y usa la `API_KEY` del gateway. El cron llama al endpoint
protegido `/_internal/api/pagos/mantenimiento/liberar_vencidos`; no hace
falta desplegar un servicio de pagos separado.

## 5. Frontend React

Los bundles compilados de `static/react/` están versionados; Render y Docker
no necesitan Node para desplegar. Para modificar los paneles:

```bash
cd frontend
npm ci
npm run build
```

Después de recompilar, incluye los bundles actualizados en el cambio.

## 6. Despliegue y verificación

1. Ejecuta las migraciones pendientes en sus respectivas bases.
2. Despliega primero a un servicio de prueba con sus propias variables y
   credenciales de prueba; no uses credenciales reales de pago para validar.
3. Verifica inicio de sesión, agendación, pago, paneles, webhook con token
   válido y recordatorios en modo controlado.
4. Tras aprobar la prueba, despliega el mismo commit a producción.
5. Comprueba los logs del gateway y la ejecución del cron.

No se debe combinar ni renombrar las bases como parte del despliegue. Los
backups de AlwaysData continúan aplicándose a los siete esquemas actuales.
