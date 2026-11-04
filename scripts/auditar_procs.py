#!/usr/bin/env python
"""
Verifica que el codigo Python y los procedimientos SQL esten alineados
(corre en CI).

Detecta en ambos sentidos:
  - Procedimientos definidos en db_split/*.sql que nadie invoca
    (codigo muerto que se arrastra desde cambios anteriores).
  - Llamadas a procedimientos que no existen en ninguna base.

Salida: codigo 0 si todo cuadra, 1 si hay discrepancias.
"""

import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(BASE, "db_split")

# Procedimientos que el codigo invoca por nombre pero que son internos a
# otra capa o se llaman con SQL dinamico, asi que no aparecen como
# call_proc("sp_...").
EXCLUIDOS = set()

RE_DEFINE = re.compile(r"CREATE\s+PROCEDURE\s+`?(sp_\w+)`?", re.I)
RE_LLAMADA = re.compile(r"""["'](sp_\w+)["']""")


def procedimientos_definidos():
    """Lee esquemas base y migraciones versionadas de db_split/."""
    definidos = set()
    for root, dirs, files in os.walk(DB_DIR):
        dirs.sort()
        for nombre in sorted(files):
            if not nombre.endswith(".sql"):
                continue
            ruta = os.path.join(root, nombre)
            with open(ruta, encoding="utf-8", errors="replace") as archivo:
                definidos |= set(RE_DEFINE.findall(archivo.read()))
    return definidos


def llamadas_al_codigo():
    """Nombres de procedimiento que aparecen entrecomillados en el .py."""
    llamadas = set()
    for root, dirs, files in os.walk(BASE):
        dirs[:] = [
            d
            for d in dirs
            if d not in (".git", "__pycache__", ".venv", "venv", "instance")
        ]
        for f in files:
            if not f.endswith(".py"):
                continue
            txt = open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
            llamadas |= set(RE_LLAMADA.findall(txt))
    return llamadas


def main():
    definidos = procedimientos_definidos()
    llamadas = llamadas_al_codigo() - EXCLUIDOS

    huerfanos = definidos - llamadas
    inexistentes = llamadas - definidos

    if huerfanos or inexistentes:
        if huerfanos:
            print(f"Procedimientos definidos y nunca invocados ({len(huerfanos)}):")
            for p in sorted(huerfanos):
                print(f"  - {p}")
        if inexistentes:
            print(f"Procedimientos invocados pero inexistentes ({len(inexistentes)}):")
            for p in sorted(inexistentes):
                print(f"  - {p}")
        return 1

    print(f"OK: {len(definidos)} procedimientos definidos, todos referenciados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
