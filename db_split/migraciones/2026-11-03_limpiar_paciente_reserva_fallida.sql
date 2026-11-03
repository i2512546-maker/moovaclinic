-- ============================================================
-- MIGRACION: revertir altas de pacientes cuando una reserva falla
-- Ejecutar UNA SOLA VEZ en la base configurada en DB_NAME.
-- Hacer copia de seguridad antes de ejecutar.
-- ============================================================

DELIMITER $$

DROP PROCEDURE IF EXISTS sp_disponibilidad_citas_rango$$
CREATE PROCEDURE sp_disponibilidad_citas_rango(
    IN p_terapeuta_id INT, IN p_desde DATE, IN p_hasta DATE
)
BEGIN
    SELECT fecha_cita, hora_cita
    FROM historial_citas
    WHERE terapeuta_id = p_terapeuta_id
      AND fecha_cita BETWEEN p_desde AND p_hasta
      AND estado IN ('pendiente_pago', 'programada', 'confirmada')
    ORDER BY fecha_cita, hora_cita;
END$$

DROP PROCEDURE IF EXISTS sp_eliminar_paciente_si_huerfano$$
CREATE PROCEDURE sp_eliminar_paciente_si_huerfano(IN p_paciente_id INT)
BEGIN
    DELETE FROM pacientes
    WHERE id = p_paciente_id
      AND NOT EXISTS (
          SELECT 1 FROM historial_citas h
          WHERE h.paciente_id = p_paciente_id
      )
      AND NOT EXISTS (
          SELECT 1 FROM evaluaciones_iniciales e
          WHERE e.paciente_id = p_paciente_id
      );
    SELECT ROW_COUNT() AS eliminados;
END$$

DELIMITER ;

-- La eliminación solo afecta pacientes recién creados que todavía no
-- tienen citas ni evaluaciones. Los expedientes con historial se conservan.
