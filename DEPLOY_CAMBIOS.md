# Despliegue de MOOVA Clinic

MOOVA Clinic se despliega como un monolito modular: un único servicio web
`moova-gateway` ejecuta Flask/Gunicorn y registra los seis módulos internos
bajo `/_internal`. El runtime actual conecta todos los dominios al esquema
MySQL indicado por `DB_NAME` (en `render.yaml`, `moovacloud_database`).
Render también puede ejecutar tareas programadas para liberar pagos vencidos.

## 1. Migraciones de base de datos

Para la instalación unificada actual, ejecuta las siguientes migraciones
sobre la base configurada en `DB_NAME`, antes de desplegar el código:

| Archivo | Qué agrega |
|---|---|
| `db_split/migraciones/2026-11-03_optimizar_agenda_panel.sql` | Índice y procedimientos para agenda y resumen diario |
| `db_split/migraciones/2026-11-03_disponibilidad_citas_rango.sql` | Consulta de disponibilidad por terapeuta y rango en una sola llamada |
| `db_split/migraciones/2026-11-04_indices_rendimiento.sql` | Índices compuestos para agenda por terapeuta/fecha y pacientes por terapeuta/estado, más índice `pagos.fecha_pago` |
| `db_split/migraciones/2026-11-04_consultas_citas_agrupadas.sql` | Procedimientos para seguimiento semanal y pacientes por terapeuta en una consulta |
| `db_split/migraciones/2026-11-04_kpis_fecha_pago_sargable.sql` | Filtros de fecha de pago compatibles con el índice `idx_fecha` |

Ejemplo (reemplaza el nombre por el valor real de `DB_NAME`):

```bash
mysql -u USUARIO -p moovacloud_database < db_split/migraciones/2026-11-03_optimizar_agenda_panel.sql
mysql -u USUARIO -p moovacloud_database < db_split/migraciones/2026-11-03_disponibilidad_citas_rango.sql
mysql -u USUARIO -p moovacloud_database < db_split/migraciones/2026-11-04_indices_rendimiento.sql
mysql -u USUARIO -p moovacloud_database < db_split/migraciones/2026-11-04_consultas_citas_agrupadas.sql
mysql -u USUARIO -p moovacloud_database < db_split/migraciones/2026-11-04_kpis_fecha_pago_sargable.sql
```

El archivo `database/moovaclinic_unificada.sql` contiene definiciones de
procedimientos almacenados para el esquema unificado; no crea tablas ni
importa datos. El repositorio no incluye un dump unificado completo de DDL,
por lo que la base debe estar previamente provisionada.

**No importes `db_split/*.sql` en la instalación unificada.** Esos archivos
conservan el diseño anterior de siete esquemas independientes y contienen
sentencias `CREATE DATABASE` / `USE`. Las migraciones antiguas que hacen
referencia explícita a `moovacloud_auth`, `moovacloud_pagos` u otros esquemas
solo corresponden a instalaciones que ya mantienen esa estructura; no las
ejecutes contra `DB_NAME` sin adaptar y revisar sus referencias.

Comprueba los procedimientos instalados con:

```sql
SHOW PROCEDURE STATUS WHERE Db = DATABASE();
```

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

## Modo demostración de Yape/Plin

Para la sustentación, define `PAGOS_MODO_DEMO=1` en las variables de
entorno del servicio web. La pantalla mostrará **Confirmar pago de demostración**;
el backend registrará el pago pendiente como pagado en MySQL y permitirá continuar,
sin llamar a Yape, Plin ni Niubiz. La opción está apagada por defecto
(`PAGOS_MODO_DEMO=0`); actívala solo para la demostración y desactívala al
terminar.

## 4. Cron de pagos vencidos

El gateway ejecuta cada hora la liberación de pagos vencidos cuando
`LIBERAR_VENCIDOS_ENABLED=1` (por defecto), sin un cron separado, como en
Railway. El proceso marca el pago como vencido, cancela la cita programada
con la nota `pago vencido` y reintenta si la llamada al servicio de citas
falla. El script `scripts/liberar_pagos_vencidos.py` se conserva para
ejecuciones manuales o instalaciones con un cron externo.

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

El backup debe seguir la misma configuración que la aplicación: define
`DB_NAME` para respaldar el esquema unificado o `DB_LIST` para una instalación
histórica de varios esquemas. No cambies la estructura de bases como parte
de un despliegue de código.
