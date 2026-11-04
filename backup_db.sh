#!/bin/bash
# ============================================================
# MOOVA Clinic - Backup diario automatico de TODAS las bases
# HOSTING: Alwaysdata (Linux). Se ejecuta via Cron Job del panel.
#
# El runtime actual usa DB_NAME (un esquema compartido). Para una
# instalacion antigua de siete esquemas, define DB_LIST en el cron.
# DB_LIST tiene prioridad sobre DB_NAME. Si no se define ninguno,
# se conserva la lista historica de siete esquemas.
#
# CONFIGURAR EN EL PANEL ALWAYSDATA:
#   1. Entra a alwaysdata.net > tu sitio moovacloud
#   2. Ve a "Avanzado > Tareas programadas (Cron)"
#   3. Crea una tarea que ejecute:  bash /home/moovacloud/backup_db.sh
#      - Periodicidad: diaria, p.ej. 2:30  (recomendado)
#      - Correo de salida: MARCA, para enterarte si falla.
#   4. Asegurate de subir este archivo a tu home con:
#         chmod +x /home/moovacloud/backup_db.sh
#
# ALTERNATIVA (backup nativo del hosting):
#   Alwaysdata ofrece "Backups / Restauracion" en la seccion de
#   bases de datos del panel. Puedes activar backups automaticos
#   ahi mismo sin script. Selecciona todos los esquemas activos del
#   proyecto si tu plan lo incluye.
#
# RETENCION: conserva los ultimos N dias (7 = una semana).
# ============================================================

set -o pipefail

# --- Configuracion: credenciales via entorno, nunca en el archivo ---
DB_USER="${DB_USER:-moovacloud}"
# OJO: nunca pongas la password en claro en un archivo versionado.
# Define esta variable en la tarea cron del panel o en ~/.my.cnf
DB_PASSWORD="${DB_PASSWORD:?Define DB_PASSWORD como variable de entorno}"

# Prioridad: DB_LIST explicito (instalacion split) > DB_NAME (actual)
# > lista historica de siete esquemas.
if [ -z "${DB_LIST:-}" ]; then
    if [ -n "${DB_NAME:-}" ]; then
        DB_LIST="${DB_NAME}"
    else
        DB_LIST="moovacloud_auth moovacloud_pacientes moovacloud_citas moovacloud_pagos moovacloud_notas moovacloud_auditoria moovacloud_kpis"
    fi
fi

# Directorio destino dentro de tu cuenta de Alwaysdata.
BACKUP_DIR="${BACKUP_DIR:-${HOME}/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

mkdir -p "${BACKUP_DIR}"

STAMP="$(date +%Y%m%d_%H%M%S)"

fallos=0
exitos=0

for db in ${DB_LIST}; do
    OUT="${BACKUP_DIR}/${db}_${STAMP}.sql.gz"

    # Volcado completo (estructura + datos). pipefail hace que el fallo
    # de mysqldump NO se oculte: sin el, el script reportaria OK
    # siempre, porque gzip genera un archivo valido (solo cabecera)
    # aunque mysqldump haya fallado por credenciales o BD inexistente.
    if ! mysqldump -u "${DB_USER}" -p"${DB_PASSWORD}" --single-transaction \
            --routines --triggers --databases "${db}" 2>>"${BACKUP_DIR}/backup_errores.log" \
            | gzip > "${OUT}"; then
        echo "ERROR backup ${db}: fallo mysqldump (ver backup_errores.log)"
        rm -f "${OUT}"
        fallos=$((fallos + 1))
        continue
    fi

    # gzip de una entrada vacia ocupa ~30 bytes (cabecera + CRC).
    # Un umbral de 100 bytes distingue un volcado real de un fallo.
    tam=$(wc -c < "${OUT}" | tr -d ' ')
    if [ "${tam}" -lt 100 ]; then
        echo "ERROR backup ${db}: archivo vacio o truncado (${tam} bytes)"
        rm -f "${OUT}"
        fallos=$((fallos + 1))
        continue
    fi

    echo "OK backup ${db}: ${OUT} (${tam} bytes)"
    exitos=$((exitos + 1))

    # Retencion acotada al esquema actual; no borra respaldos de otros DB_LIST.
    find "${BACKUP_DIR}" -maxdepth 1 -type f -name "${db}_*.sql.gz" \
        -mtime +"${RETENTION_DAYS}" -delete
done

echo "Resumen: ${exitos} respaldos correctos, ${fallos} fallidos"

# exit != 0 para que la tarea cron reporte el fallo por correo
[ "${fallos}" -eq 0 ] || exit 1