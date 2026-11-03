-- ============================================================
-- MIGRACION: actualizar especialidad de terapeuta
-- Fecha: 2026-11-02
-- Idempotente. Ejecutar en moovacloud_pacientes.
-- ============================================================

USE moovacloud_pacientes$$

DROP PROCEDURE IF EXISTS `sp_actualizar_especialidad`$$
CREATE PROCEDURE `sp_actualizar_especialidad`(IN p_medico_id INT, IN p_especialidad_id INT)
BEGIN
    UPDATE terapeutas SET especialidad_id = p_especialidad_id WHERE id = p_medico_id;
END$$

-- ============================================================
-- FIN 2026-11-02_actualizar_especialidad.sql
-- ============================================================
