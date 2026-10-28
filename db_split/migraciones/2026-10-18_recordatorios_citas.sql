-- ============================================================
-- MIGRACION: recordatorios automaticos por SMS (sustentacion)
-- Fecha:    2026-10-18
-- Base:     moovacloud_citas (Always Data)
--
-- IMPORTANTE: este archivo solo define procedimientos, NO toca
-- tablas ni inserta datos. Always Data ya tiene datos reales y no
-- se puede reimportar db_split/citas_db.sql completo. La columna
-- historial_citas.recordatorio_enviado ya existe (DEFAULT 0), por
-- lo que no hace falta ALTER TABLE.
--
-- La version para instalaciones nuevas esta en db_split/citas_db.sql.
-- ============================================================

DELIMITER $$

--
-- sp_citas_pendientes_recordatorio
--   Citas de un dia concreto que todavia no recibieron recordatorio.
--   Solo 'programada' y 'confirmada': 'cancelada' y 'completada'
--   no deben recibir SMS.
--
DROP PROCEDURE IF EXISTS `sp_citas_pendientes_recordatorio`$$
CREATE PROCEDURE `sp_citas_pendientes_recordatorio`(IN p_fecha DATE)
BEGIN
    SELECT id, paciente_id, terapeuta_id, fecha_cita, hora_cita
    FROM historial_citas
    WHERE fecha_cita = p_fecha
      AND estado IN ('programada', 'confirmada')
      AND COALESCE(recordatorio_enviado, 0) = 0
    ORDER BY hora_cita ASC;
END$$

--
-- sp_marcar_recordatorio_enviado
--   Reclamo atomico: solo marca si recordatorio_enviado todavia
--   es 0. ROW_COUNT()=1 significa que ESTE proceso gano el envio,
--   lo que evita el doble SMS si dos procesos corren a la vez
--   (el scheduler de APScheduler y el endpoint manual).
--
DROP PROCEDURE IF EXISTS `sp_marcar_recordatorio_enviado`$$
CREATE PROCEDURE `sp_marcar_recordatorio_enviado`(IN p_cita_id INT)
BEGIN
    UPDATE historial_citas
    SET recordatorio_enviado = 1, actualizado_en = UTC_TIMESTAMP()
    WHERE id = p_cita_id AND COALESCE(recordatorio_enviado, 0) = 0;
    SELECT ROW_COUNT() AS marcadas;
END$$

--
-- sp_desmarcar_recordatorio
--   Deshace el reclamo cuando el SMS fallo o el paciente no tiene
--   telefono, para que el siguiente ciclo reintente la misma cita.
--
DROP PROCEDURE IF EXISTS `sp_desmarcar_recordatorio`$$
CREATE PROCEDURE `sp_desmarcar_recordatorio`(IN p_cita_id INT)
BEGIN
    UPDATE historial_citas
    SET recordatorio_enviado = 0, actualizado_en = UTC_TIMESTAMP()
    WHERE id = p_cita_id;
    SELECT ROW_COUNT() AS desmarcadas;
END$$

DELIMITER ;

-- ============================================================
-- FIN 2026-10-18_recordatorios_citas.sql
-- ============================================================
