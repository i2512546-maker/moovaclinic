#!/bin/bash
# Arranca los 6 microservicios + el gateway en UN solo servicio de Railway.
# Los servicios se hablan por 127.0.0.1 (valores por defecto de shared/config.py).
# La base de datos es el plugin MySQL de Railway (servicio aparte).
set -e
cd "$(dirname "$0")/.."

PORT="${PORT:-8080}"
export DB_HOST="${DB_HOST:-$MYSQLHOST}"
export DB_PORT="${DB_PORT:-${MYSQLPORT:-3306}}"
export DB_USER="${DB_USER:-$MYSQLUSER}"
export DB_PASSWORD="${DB_PASSWORD:-$MYSQLPASSWORD}"
[ -n "$DB_HOST" ] || { echo "[railway] Falta DB_HOST (o MYSQLHOST)"; exit 1; }
[ -n "$SECRET_KEY" ] || { echo "[railway] Falta SECRET_KEY en Variables"; exit 1; }
export API_KEY="${API_KEY:-$(python -c 'import secrets; print(secrets.token_hex(16))')}"
export SMS_MODE="${SMS_MODE:-console}"

MYSQL_CMD=(mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" "-p$DB_PASSWORD")

echo "[railway] esperando MySQL en $DB_HOST:$DB_PORT"
for i in $(seq 1 60); do
  "${MYSQL_CMD[@]}" -e "select 1" >/dev/null 2>&1 && break
  sleep 2
done
"${MYSQL_CMD[@]}" -e "select 1" >/dev/null 2>&1 || { echo "[railway] no se pudo conectar a MySQL"; exit 1; }

if ! "${MYSQL_CMD[@]}" -N -e "show databases like 'moovacloud_auth'" | grep -q moovacloud_auth; then
  echo "[railway] importando db_split/*.sql (solo la primera vez)"
  for f in db_split/*.sql; do "${MYSQL_CMD[@]}" < "$f"; done
fi

start() { # servicio puerto base_de_datos
  DB_NAME=$3 gunicorn "services.$1.app:create_app()" --bind 127.0.0.1:$2 --workers 1 --timeout 60 --log-level warning &
}
start auth_service      5001 moovacloud_auth
start pacientes_service 5002 moovacloud_pacientes
start citas_service     5003 moovacloud_citas
start pagos_service     5004 moovacloud_pagos
start notas_service     5005 moovacloud_notas
start audit_service     5006 moovacloud_auditoria
sleep 4
echo "[railway] gateway en 0.0.0.0:$PORT"
exec gunicorn "gateway.app:create_app()" --bind 0.0.0.0:$PORT --workers 1 --timeout 60
