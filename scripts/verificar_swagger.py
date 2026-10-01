#!/usr/bin/env python
"""
Verifica que swagger.yaml documente las rutas de los microservicios
(FASE 4, corre en CI).

swagger.yaml documenta las APIs internas (las que consumen otros
servicios). Las rutas HTML del gateway (/login, /interfaz, /pago...)
no van alla: no son API.

Fallar si:
  - swagger declara una ruta que el codigo ya no tiene (documentacion
    que miente, la peor de las tres situaciones).
  - una ruta interna de servicio no esta documentada.

Salida: codigo 0 si cuadra, 1 si hay discrepancias.
"""

import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SERVICIOS = ["auth", "pacientes", "citas", "pagos", "notas", "audit"]

RE_ROUTE = re.compile(r"""\.route\(\s*["'](/[^"']*)["']""")
# Un param de Flask puede traer converter: <int:cita_id>, <dni> o <path:x>.
# Swagger escribe {cita_id}. Se reduce todo a {} para comparar posiciones.
RE_PARAM = re.compile(r"<(?:[A-Za-z_]\w*:)?[A-Za-z_]\w*>|\{[A-Za-z_]\w*\}")
RE_PLACEHOLDER = re.compile(r"\{\w+\}|<\w+>")


def _normaliza(ruta):
    """Compara rutas ignorando sintaxis y nombre del parametro.

    Flask escribe /api/x/<dni> y Swagger /api/x/{dni}. Ademas el codigo
    puede usar <paciente_id> donde la doc usa {id}. Se comparan las
    posiciones: /api/pacientes/{}/paquetes == /api/pacientes/<id>/paquetes.
    """
    return RE_PARAM.sub("{}", ruta)


def rutas_de_codigo():
    rutas = set()
    for svc in SERVICIOS:
        p = os.path.join(BASE, "services", f"{svc}_service", "routes.py")
        txt = open(p, encoding="utf-8", errors="replace").read()
        rutas |= {_normaliza(r) for r in RE_ROUTE.findall(txt)}
    return rutas


def rutas_de_swagger():
    txt = open(os.path.join(BASE, "swagger.yaml"), encoding="utf-8", errors="replace").read()
    # Solo el bloque paths. Se ignoran las rutas que salen en ejemplos.
    rutas = re.findall(r"^  (/[\w<>{}/.\-]+):", txt, re.M)
    return {_normaliza(r) for r in rutas}


def main():
    codigo = rutas_de_codigo()
    swagger = rutas_de_swagger()

    # El gateway no es parte de swagger.yaml (documenta APIs de servicio).
    # /api/servicios y /api/especialidades viven en pacientes_service, ya
    # cubierto por rutas_de_codigo.

    fantasma = swagger - codigo
    sin_documentar = codigo - swagger

    if fantasma or sin_documentar:
        if fantasma:
            print(f"Rutas en swagger.yaml que no existen en el codigo ({len(fantasma)}):")
            for r in sorted(fantasma):
                print(f"  - {r}")
        if sin_documentar:
            print(f"Rutas de servicio sin documentar en swagger.yaml ({len(sin_documentar)}):")
            for r in sorted(sin_documentar):
                print(f"  - {r}")
        return 1

    print(f"OK: {len(codigo)} rutas de servicio, todas documentadas en swagger.yaml.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
