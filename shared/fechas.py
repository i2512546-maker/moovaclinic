"""Normalizacion de fechas/horas para presentarlas en las vistas.

Las fechas llegan a las vistas ya serializadas por Flask, que convierte
date/datetime en texto ("Sat, 01 Aug 2026 ..."), y no en objetos datetime.
MySQL TIME, en cambio, llega como timedelta porque mysql-connector-python
lo representa asi. Estas funciones cubren los tres casos para poder
formatear en plantilla y en el PDF sin romper la pagina.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# La clinica esta en Lima y el servidor puede no estarlo (en Render es
# UTC): "hoy" se decide aqui y no con el reloj de la maquina.
ZONA_LIMA = ZoneInfo("America/Lima")

FORMATOS_FECHA = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
    "%a, %d %b %Y %H:%M:%S GMT",
    "%a, %d %b %Y",
    "%H:%M:%S",
    "%H:%M",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
)


def a_datetime(valor):
    """Devuelve datetime, o None si el valor no es una fecha reconocible."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor
    if isinstance(valor, date):
        return datetime(valor.year, valor.month, valor.day)
    if isinstance(valor, timedelta):
        total = int(valor.total_seconds())
        return datetime(1970, 1, 1, total // 3600, (total % 3600) // 60, total % 60)
    texto = str(valor).strip()
    if not texto:
        return None
    for fmt in FORMATOS_FECHA:
        try:
            return datetime.strptime(texto, fmt)
        except ValueError:
            continue
    return None


def fmt_fecha(valor, con_hora=False):
    """Formatea a dd/mm/YYYY (o dd/mm/YYYY HH:MM). Si no reconoce el valor,
    lo devuelve tal cual para no perder informacion en pantalla."""
    dt = a_datetime(valor)
    if dt is None:
        return "" if valor in (None, "") else str(valor)
    return dt.strftime("%d/%m/%Y %H:%M" if con_hora else "%d/%m/%Y")


def fmt_hora(valor):
    """Formatea solo la hora como HH:MM a partir de TIME, timedelta o texto."""
    dt = a_datetime(valor)
    if dt is None:
        return "" if valor in (None, "") else str(valor)
    return dt.strftime("%H:%M")


def ahora_lima():
    """Fecha y hora actuales en America/Lima (con zona, no naive).

    Para lo que se muestra al usuario ("emitido el ... a las ...") o se
    compara con lo que ha elegido en Lima.
    """
    return datetime.now(ZONA_LIMA)


def hoy_lima():
    """Fecha de hoy en America/Lima.

    Todo lo que pregunta "que dia es hoy" pasa por aqui: con el reloj
    de la maquina en UTC, a partir de las 19:00 de Lima el sistema ya
    estaba mirando al dia siguiente.
    """
    return ahora_lima().date()
