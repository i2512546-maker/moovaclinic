"""Horarios de atencion por terapeuta (slots de 1 hora).

Funciones puras y faciles de testear. Sin dependencias de BD ni de Flask.
"""
from datetime import datetime, time

from shared.config import CUPO_POR_SLOT, DURACION_SLOT_MIN, HORA_FIN, HORA_INICIO


def _a_minutos(hora):
    """Convierte 'HH:MM' o time/datetime a minutos desde medianoche."""
    if isinstance(hora, str):
        h, m = hora.strip().split(":")
        return int(h) * 60 + int(m)
    if isinstance(hora, time):
        return hora.hour * 60 + hora.minute
    if isinstance(hora, datetime):
        return hora.hour * 60 + hora.minute
    raise ValueError(f"Hora no reconocida: {hora!r}")


def generar_slots():
    """Lista de slots 'HH:MM' entre HORA_INICIO y HORA_FIN."""
    slots = []
    inicio = HORA_INICIO * 60
    fin = HORA_FIN * 60
    t = inicio
    while t + DURACION_SLOT_MIN <= fin:
        slots.append(f"{t // 60:02d}:{t % 60:02d}")
        t += DURACION_SLOT_MIN
    return slots


_SLOTS_VALIDOS = None


def _slots_validos():
    global _SLOTS_VALIDOS
    if _SLOTS_VALIDOS is None:
        _SLOTS_VALIDOS = set(generar_slots())
    return _SLOTS_VALIDOS


def validar_slot(hora):
    """True si `hora` es un slot valido (formato y dentro del horario)."""
    try:
        texto = str(hora).strip()[:5]
        if texto not in _slots_validos():
            return False
        # valida formato HH:MM
        h, m = texto.split(":")
        int(h)
        int(m)
        return True
    except Exception:
        return False


def contar_ocupados(ocupados):
    """Cuenta cuantas citas hay por slot a partir de una lista de horas."""
    conteo = {}
    for h in (ocupados or []):
        try:
            slot = str(h).strip()[:5]
        except Exception:
            continue
        if slot:
            conteo[slot] = conteo.get(slot, 0) + 1
    return conteo


def slots_libres(ocupados, fecha, ahora_lima=None):
    """Devuelve los slots libres para `fecha`.

    - `ocupados`: lista de horas (str/time) de citas ya reservadas en esa
      fecha para el terapeuta.
    - Si `fecha` es hoy (segun `ahora_lima`), descarta los slots pasados.
    """
    conteo = contar_ocupados(ocupados)
    libres = []
    for slot in generar_slots():
        if conteo.get(slot, 0) >= CUPO_POR_SLOT:
            continue
        if ahora_lima is not None:
            hoy = getattr(ahora_lima, "date", lambda: None)()
            if hoy is not None and str(fecha)[:10] == str(hoy):
                slot_min = _a_minutos(slot)
                ahora_min = ahora_lima.hour * 60 + ahora_lima.minute
                if slot_min <= ahora_min:
                    continue
        libres.append(slot)
    return libres


def slot_disponible(ocupados, slot):
    """True si `slot` aun tiene cupo."""
    conteo = contar_ocupados(ocupados)
    return conteo.get(str(slot).strip()[:5], 0) < CUPO_POR_SLOT


def autoasignar(ocupados, fecha, ahora_lima=None):
    """Primer slot libre o None si el dia esta lleno."""
    libres = slots_libres(ocupados, fecha, ahora_lima)
    return libres[0] if libres else None
