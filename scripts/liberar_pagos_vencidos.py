#!/usr/bin/env python
"""
Expira los pagos pendientes sin confirmar (FASE 4).

Sin este job, una cita abandonada a mitad del pago queda bloqueada de
forma indefinida: el pago sigue en 'pendiente' y el paciente no puede
volver a reservar.

USO (desde cron del hosting, no necesita navegador):
    python scripts/liberar_pagos_vencidos.py [horas]

    horas  Antiguedad a partir de la cual se expira. Por defecto 24.

Variables de entorno requeridas:
    PAGOS_SERVICE_URL   p.ej. http://127.0.0.1:5004
    API_KEY             misma clave que el resto de servicios

Salida: codigo 0 si la llamada fue exitosa, 1 si fallo. Compatible con
el envio de correo de error de las tareas programadas.

EJEMPLO en el cron de Alwaysdata (una vez por hora):
    0 * * * * cd /home/moovacloud && /usr/bin/python3 scripts/liberar_pagos_vencidos.py
"""

import json
import os
import sys
import urllib.error
import urllib.request

TIMEOUT_SEG = 30


def main():
    horas = sys.argv[1] if len(sys.argv) > 1 else "24"
    url_servicio = (os.getenv("PAGOS_SERVICE_URL") or "http://127.0.0.1:5004").rstrip("/")
    api_key = os.getenv("API_KEY") or ""

    if not api_key:
        print(
            "ERROR: falta API_KEY en el entorno. El job no puede llamar al "
            "servicio (la auth interna esta cerrada sin clave).",
            file=sys.stderr,
        )
        return 1

    endpoint = f"{url_servicio}/api/pagos/mantenimiento/liberar_vencidos"
    cuerpo = json.dumps({"horas": int(horas)}).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=cuerpo,
        headers={"Content-Type": "application/json", "X-Api-Key": api_key},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEG) as resp:
            salida = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as exc:
        detalle = exc.read().decode("utf-8", "replace")
        print(f"ERROR: el servicio respondio {exc.code}: {detalle}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError) as exc:
        print(f"ERROR: no se pudo contactar {endpoint}: {exc}", file=sys.stderr)
        return 1

    if status != 200:
        print(f"ERROR: status inesperado {status}: {salida}", file=sys.stderr)
        return 1

    print(f"OK {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())