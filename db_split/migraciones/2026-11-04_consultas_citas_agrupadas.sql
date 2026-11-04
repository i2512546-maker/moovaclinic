-- Agrupa dos recorridos de citas que antes ejecutaban varias consultas.
-- Ejecutar una sola vez en la base configurada por DB_NAME.
DELIMITER $$

DROP PROCEDURE IF EXISTS `sp_listar_citas_seguimiento`$$
CREATE PROCEDURE `sp_listar_citas_seguimiento`(
    IN p_desde DATE,
    IN p_hasta DATE
)
BEGIN
    SELECT h.id, h.id AS historial_id, h.paciente_id, h.terapeuta_id,
           h.servicio_id, h.fecha_cita, h.hora_cita, h.estado, h.descripcion
    FROM historial_citas h
    WHERE h.fecha_cita BETWEEN p_desde AND p_hasta
      AND h.estado IN ('cancelada', 'no_asistio')
    ORDER BY h.fecha_cita, h.hora_cita, h.id;
END$$

DROP PROCEDURE IF EXISTS `sp_pacientes_ids_por_terapeuta`$$
CREATE PROCEDURE `sp_pacientes_ids_por_terapeuta`(IN p_terapeuta_id INT)
BEGIN
    SELECT DISTINCT paciente_id
    FROM historial_citas
    WHERE terapeuta_id = p_terapeuta_id
      AND estado IN ('programada', 'confirmada', 'completada', 'cancelada', 'no_asistio')
    ORDER BY paciente_id;
END$$

DELIMITER ;
