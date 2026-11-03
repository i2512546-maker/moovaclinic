-- ============================================================
-- MIGRACION: revertir altas de pacientes cuando una reserva falla
-- Ejecutar UNA SOLA VEZ en la base configurada en DB_NAME.
-- Hacer copia de seguridad antes de ejecutar.
-- ============================================================

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_eliminar_paciente_si_huerfano$$
CREATE PROCEDURE sp_eliminar_paciente_si_huerfano(IN p_paciente_id INT)
BEGIN
    DELETE FROM pacientes
    WHERE id = p_paciente_id
      AND NOT EXISTS (
          SELECT 1 FROM evaluaciones_iniciales e
          WHERE e.paciente_id = p_paciente_id
      );
    SELECT ROW_COUNT() AS eliminados;
END$$

DELIMITER ;

-- La eliminación solo afecta pacientes recién creados que todavía no
-- tienen citas ni evaluaciones. Los expedientes con historial se conservan.
