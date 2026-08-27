#!/bin/bash
# ============================================================
# MOOVA Clinic - Backup diario automatico de moovacloud_db
# HOSTING: Alwaysdata (Linux). Se ejecuta via Cron Job del panel.
#
# VENTAJA: mysqldump corre EN el servidor del hosting, asi el
# backup queda en la misma infraestructura y cubre TODA la base
# sin importar cuantos servicios Flask la escriban.
#
# CONFIGURAR EN EL PANEL ALWAYSDATA:
#   1. Entra a alwaysdata.net > tu sitio moovacloud
#   2. Ve a "Avanzado > Tareas programadas (Cron)"
#   3. Crea una tarea que ejecute:  bash /home/moovacloud/backup_db.sh
#      - Periodicidad: diaria, p.ej. 2:30  (recomendado)
#   4. Asegurate de subir este archivo a tu home con:
#         chmod +x /home/moovacloud/backup_db.sh
#
# ALTERNATIVA (backup nativo del hosting):
#   Alwaysdata ofrece "Backups / Restauración" en la seccion de
#   bases de datos del panel. Puedes activar backups automaticos
#   ahi mismo sin script. Esto es lo MAS SIMPLE y recomendado si
#   tu plan lo incluye.
#
# RETENCION: conserva los ultimos N backups (7 = una semana).
# ============================================================

# --- Configuracion: reemplaza con los datos reales ---
DB_NAME="moovacloud_db"
DB_USER="moovacloud"
# OJO: nunca pongas la password en claro en un archivo versionado.
# Define esta variable en la tarea cron del panel o en ~/.my.cnf
DB_PASSWORD="${DB_PASSWORD:?Define DB_PASSWORD como variable de entorno}"

# Directorio destino dentro de tu cuenta de alwaysdata
BACKUP_DIR="${HOME}/backups"
RETENTION_DAYS=7

mkdir -p "${BACKUP_DIR}"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${BACKUP_DIR}/moovacloud_db_${STAMP}.sql.gz"

# Volcado completo (todas las tablas, estructura + datos)
mysqldump -u "${DB_USER}" -p"${DB_PASSWORD}" "${DB_NAME}" | gzip > "${OUT}"

# Pequena verificacion: el archivo no debe estar vacio
if [ -s "${OUT}" ]; then
    echo "OK backup: ${OUT}"
    # Eliminar backups de hace mas de RETENTION_DAYS dias
    find "${BACKUP_DIR}" -name "moovacloud_db_*.sql.gz" -mtime +"${RETENTION_DAYS}" -delete
else
    echo "ERROR: backup vacio o fallo en mysqldump"
    rm -f "${OUT}"
    exit 1
fi
