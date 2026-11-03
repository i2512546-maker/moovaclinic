-- ============================================================
-- MIGRACION: marcar cita como no asistida
-- Fecha: 2026-11-02
-- Idempotente. Ejecutar en moovacloud_citas.
-- ============================================================

USE moovacloud_citas$$

DROP PROCEDURE IF EXISTS `sp_marcar_no_asistio`$$
CREATE PROCEDURE `sp_marcar_no_asistio`(IN p_cita_id INT)
BEGIN
    DECLARE v_afectadas INT DEFAULT 0;
    UPDATE historial_citas SET estado = 'no_asistio', actualizado_en = NOW()
    WHERE id = p_cita_id AND estado IN ('programada', 'confirmada');
    SET v_afectadas = ROW_COUNT();
    SELECT v_afectadas AS actualizadas;
END$$

-- ============================================================
-- FIN 2026-11-02_marcar_no_asistio.sql
-- ============================================================
