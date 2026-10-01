"""Normalizacion de fechas/horas para presentarlas en las vistas.

Las fechas llegan al gateway desde los microservicios ya serializadas por
Flask, que convierte date/datetime en texto HTTP ("Sat, 01 Aug 2026 ..."), y
no en objetos datetime. MySQL TIME, en cambio, llega como timedelta porque
mysql-connector-python lo representa asi. Estas funciones cubren los tres
casos para poder formatear en plantilla y en el PDF sin romper la pagina.
"""
from datetime import date, datetime, timedelta

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