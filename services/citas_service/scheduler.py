# ============================================================
# Planificador de recordatorios (citas_service)
#
# Arranca APScheduler desde create_app() SOLO si RECORDATORIOS_ENABLED=1.
# El job corre cada RECORDATORIO_INTERVALO_MIN minutos, pero solo
# actua si en America/Lima ya se alcanzo RECORDATORIO_HORA, para
# mandar el aviso de las citas del dia siguiente en la tarde y no a
# cualquier hora.
#
# El job NUNCA debe tumbar el proceso: cualquier excepcion se atrapa
# y se loguea.
# ============================================================

from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from shared.config import (
    RECORDATORIO_HORA,
    RECORDATORIO_INTERVALO_MIN,
    RECORDATORIOS_ENABLED,
)

ZONA = ZoneInfo("America/Lima")

# Singleton: create_app puede llamarse mas de una vez y no queremos
# dos planificadores mandando los mismos SMS.
_scheduler = None


def _hora_pasada(hora_minima):
    """True si la hora actual en America/Lima ya alcanzo hora_minima
    ('HH:MM'). Un valor malo no bloquea el envio: por eso se usa la
    hora por defecto (18:00) si no se pudo interpretar."""
    try:
        horas, minutos = (int(x) for x in str(hora_minima).split(":", 1))
        objetivo = (horas, minutos)
    except Exception:
        objetivo = (18, 0)
    ahora = datetime.now(ZONA)
    return (ahora.hour, ahora.minute) >= objetivo


def _job_recordatorios(app):
    """Job del scheduler: envia los recordatorios del dia siguiente.

    Se atrapa cualquier excepcion: una excepcion sin atrapar haria
    que APScheduler deje de ejecutar este job y el sistema quedaria
    silenciosamente sin recordatorios.
    """
    from services.citas_service.routes import enviar_recordatorios

    if not _hora_pasada(RECORDATORIO_HORA):
        return
    try:
        with app.app_context():
            resumen = enviar_recordatorios()
        app.logger.info("[recordatorios] %s", resumen)
    except Exception as exc:
        app.logger.error(
            "[recordatorios] fallo el job: %s: %s", type(exc).__name__, exc
        )


def iniciar_scheduler(app):
    """Arranca APScheduler si esta habilitado.

    Devuelve el scheduler o None. Protegido contra doble arranque:
    si ya hay un planificador vivo se reutiliza y no se crea otro.
    """
    global _scheduler

    if RECORDATORIOS_ENABLED != "1":
        app.logger.info(
            "[recordatorios] deshabilitados (RECORDATORIOS_ENABLED=%r)",
            RECORDATORIOS_ENABLED,
        )
        return None

    if _scheduler is not None and _scheduler.running:
        return _scheduler

    intervalo = max(1, int(RECORDATORIO_INTERVALO_MIN))
    scheduler = BackgroundScheduler(timezone=ZONA)
    scheduler.add_job(
        _job_recordatorios,
        trigger="interval",
        minutes=intervalo,
        args=[app],
        id="recordatorios_citas",
        replace_existing=True,
        # coalesce=True: si se perdio un tick, no lanza 20 de golpe.
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _scheduler = scheduler
    app.logger.info(
        "[recordatorios] scheduler iniciado (cada %s min, actua desde "
        "las %s, America/Lima)",
        intervalo, RECORDATORIO_HORA,
    )
    return scheduler


def detener_scheduler():
    """Para el scheduler y limpia el singleton (util en tests)."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
    _scheduler = None
