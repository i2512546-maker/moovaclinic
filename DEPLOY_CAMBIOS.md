# Despliegue de los cambios de `mejoras-sustentacion`

Orden recomendado: **primero la base de datos, después el código**.
Las bases viven en Always Data (phpMyAdmin) y los servicios en Render
(`render.yaml`). Las migraciones solo contienen `DROP PROCEDURE IF EXISTS` +
`CREATE PROCEDURE`: no tocan tablas ni datos, así que se pueden ejecutar más
de una vez sin riesgo. **No reimportes los `db_split/*.sql` completos.**

## 1. Migraciones (phpMyAdmin → pestaña SQL de cada base)

Cada archivo va en SU base. Si se ejecuta en otra, los procedimientos quedan
en el lugar equivocado y el servicio seguirá sin encontrarlos.

| Archivo de `db_split/migraciones/` | Base donde se ejecuta | Qué agrega |
|---|---|---|
| `2026-10-18_recordatorios_citas.sql` | `moovacloud_citas` | 3 procedimientos de recordatorios SMS |
| `2026-10-18_pacientes_en_riesgo.sql` | `moovacloud_citas` | reporte de pacientes en riesgo |
| `2026-10-18_telefono_usuarios.sql` | `moovacloud_auth` | teléfono del usuario/terapeuta (listar y actualizar) |
| `2026-10-19_pagos_guardar_referencia.sql` | `moovacloud_pagos` | `sp_guardar_referencia` solo actualiza pagos pendientes |

Para cada archivo: abrir la base → pestaña **SQL** → pegar el contenido →
**Continuar**. Los archivos usan `DELIMITER $$`; si phpMyAdmin se queja, pega
el contenido sin las líneas `DELIMITER` y con el cuadro «Delimitador» de la
pestaña SQL en `$$`.

Comprobación rápida (en cada base): `SHOW PROCEDURE STATUS WHERE Db = DATABASE();`
debe listar los procedimientos nuevos.

## 2. Variables de entorno en Render

Servicio **moova-citas** → Environment. Se agregan a mano (no están en
`render.yaml`, y por defecto los recordatorios están apagados):

| Variable | Valor |
|---|---|
| `RECORDATORIOS_ENABLED` | `1` |
| `RECORDATORIO_HORA` | `18:00` |
| `RECORDATORIO_INTERVALO_MIN` | `15` |

Las demás variables (TextBee, `API_KEY`, etc.) ya existen y no cambian.
`pip install` ahora instala también APScheduler (está en `requirements.txt`).

### Importante: el servicio no debe dormirse
El planificador corre **dentro** del proceso de `moova-citas`. Si el servicio
está en un plan que se duerme por inactividad (el plan gratuito de Render lo
hace), a las 18:00 no habrá nadie despierto y **no se enviará ningún
recordatorio**. `render.yaml` no fija el plan, así que revisa en el panel de
Render cuál tiene `moova-citas`. Con un plan siempre activo funciona; con uno
gratuito, el recordatorio solo saldrá si el servicio está despierto a esa hora.

### Antes de activarlo en serio
Los SMS son reales (TextBee). Prueba primero con tu propio número cargado como
paciente de prueba, o llama a `POST /api/citas/recordatorios/enviar` con una
fecha concreta y la `API_KEY` interna.

## 3. Frontend React (paneles KPIs y MoovaTrack)

Los bundles compilados ya están en el repositorio (`static/react/kpis.js` y
`static/react/moovatrack.js`), así que **Render y Docker no necesitan Node**.
Solo hace falta Node 20 para modificar los paneles:

```
cd frontend
npm ci
npm run build
```

Después de recompilar, vuelve a commitear los dos `.js` de `static/react/`.
`node_modules` nunca se sube (está en `.gitignore` y en `.dockerignore`).

## 4. Redesplegar

1. Haz el merge (PR de `mejoras-sustentacion` hacia `branch-jarib`) y espera el
   CI en verde.
2. Render redespliega los servicios. Si no tienes auto-deploy, usa
   **Manual Deploy → Deploy latest commit** en cada servicio que cambió
   (gateway, citas, auth y pagos).
3. Verifica: inicia sesión como admin → **Panel Admin → KPIs** (debe cargar los
   gráficos), `/panel_admin/riesgo`, y como terapeuta `/moovatrack`.

## Lo que no se puede verificar desde el código
- Que la base de producción sea efectivamente la de Always Data indicada en las
  cabeceras de las migraciones.
- El plan de Render de `moova-citas` (ver advertencia de arriba).
- Que TextBee tenga el dispositivo conectado a la hora de los recordatorios.
