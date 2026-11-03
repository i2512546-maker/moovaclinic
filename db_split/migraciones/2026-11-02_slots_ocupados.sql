-- ============================================================
-- MIGRACION: slots ocupados por terapeuta y fecha
-- Fecha: 2026-11-02
-- Idempotente. Ejecutar en moovacloud_citas.
-- ============================================================

USE moovacloud_citas$$

DROP PROCEDURE IF EXISTS `sp_slots_ocupados`$$
CREATE PROCEDURE `sp_slots_ocupados`(IN p_medico_id INT, IN p_fecha DATE)
BEGIN
    SELECT hora_cita, COUNT(*) AS n
    FROM historial_citas
    WHERE terapeuta_id = p_medico_id
      AND fecha_cita = p_fecha
      AND estado IN ('pendiente_pago', 'programada', 'confirmada')
    GROUP BY hora_cita;
END$$

-- ============================================================
-- FIN 2026-11-02_slots_ocupados.sql
-- ============================================================
