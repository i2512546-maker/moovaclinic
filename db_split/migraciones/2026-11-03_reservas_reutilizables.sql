-- ============================================================
-- MIGRACION: liberar el horario cuando una cita deja de estar activa
-- Fecha: 2026-11-03
-- Ejecutar UNA SOLA VEZ en la base de datos MySQL de Alwaysdata.
-- Primero selecciona en phpMyAdmin el esquema que usa la aplicacion.
-- Haz una copia de seguridad antes de ejecutar.
-- ============================================================

ALTER TABLE historial_citas
    DROP INDEX uq_reserva,
    ADD COLUMN reserva_activa TINYINT
        GENERATED ALWAYS AS (
            CASE
                WHEN estado IN ('pendiente_pago', 'programada', 'confirmada') THEN 1
                ELSE NULL
            END
        ) STORED,
    ADD UNIQUE KEY uq_reserva_activa (
        terapeuta_id, fecha_cita, hora_cita, reserva_activa
    );

-- Las citas pendientes de pago, programadas o confirmadas reservan el slot.
-- Las canceladas, completadas y no asistidas conservan su historial,
-- pero ya no bloquean una nueva reserva para esa fecha y hora.
