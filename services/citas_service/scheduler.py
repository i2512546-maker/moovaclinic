# ============================================================
# Planificador de recordatorios (modulo de citas)
#
# Arranca APScheduler desde create_app() si hay recordatorios habilitados
# o si está activa la liberación horaria de pagos vencidos.
# Los recordatorios respetan la hora de Lima; la liberación de pagos
# se ejecuta cada hora en el dominio de pagos.
#
# El job NUNCA debe tumbar el proceso: cualquier excepcion se atrapa
# y se loguea.
# ============================================================

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from shared.config import (
    LIBERAR_VENCIDOS_ENABLED,
    RECORDATORIO_HORA,
    RECORDATORIO_INTERVALO_MIN,
    RECORDATORIOS_ENABLED,
)
from shared.db import dominio

ZONA = ZoneInfo("America/Lima")

# Singleton: create_app puede llamarse mas de una vez y no queremos
# jobs duplicados al crear varias instancias de la app en el mismo proceso.
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
            with dominio("citas"):
                resumen = enviar_recordatorios()
        app.logger.info("[recordatorios] %s", resumen)
    except Exception as exc:
        app.logger.error(
            "[recordatorios] fallo el job: %s: %s", type(exc).__name__, exc
        )


def _job_liberar_pagos_vencidos(app):
    from services.pagos_service.routes import procesar_pagos_vencidos

    try:
        with app.app_context(), dominio("pagos"):
            resultado = procesar_pagos_vencidos()
        app.logger.info("[pagos vencidos] %s", resultado)
    except Exception as exc:
        app.logger.error(
            "[pagos vencidos] fallo el job: %s: %s", type(exc).__name__, exc
        )


def iniciar_scheduler(app):
    """Arranca APScheduler si esta habilitado.

    Devuelve el scheduler o None. Protegido contra doble arranque:
    si ya hay un planificador vivo se reutiliza y no se crea otro.
    """
    global _scheduler

    if RECORDATORIOS_ENABLED != "1" and not LIBERAR_VENCIDOS_ENABLED:
        app.logger.info(
            "[scheduler] recordatorios y liberacion de vencidos deshabilitados"
        )
        return None

    if _scheduler is not None and _scheduler.running:
        return _scheduler

    scheduler = BackgroundScheduler(timezone=ZONA)
    if RECORDATORIOS_ENABLED == "1":
        intervalo = max(1, int(RECORDATORIO_INTERVALO_MIN))
        scheduler.add_job(
            _job_recordatorios,
            trigger="interval",
            minutes=intervalo,
            args=[app],
            id="recordatorios_citas",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    if LIBERAR_VENCIDOS_ENABLED:
        scheduler.add_job(
            _job_liberar_pagos_vencidos,
            trigger="interval",
            hours=1,
            args=[app],
            id="liberar_pagos_vencidos",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    scheduler.start()
    _scheduler = scheduler
    app.logger.info(
        "[scheduler] iniciado (recordatorios=%s, liberar_vencidos=%s)",
        RECORDATORIOS_ENABLED == "1", LIBERAR_VENCIDOS_ENABLED,
    )
    return scheduler


def detener_scheduler():
    """Para el scheduler y limpia el singleton (util en tests).

    No recibe la app, asi que aqui no hay app.logger: se usa el logger
    del modulo, que solo se vera si alguien configura el logging raiz
    (ningun servicio lo hace hoy; en los tests se recoge con caplog).
    """
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        try:
            _scheduler.shutdown(wait=False)
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "[recordatorios] no se pudo parar el scheduler: %s: %s",
                type(exc).__name__, exc,
            )
    _scheduler = None
