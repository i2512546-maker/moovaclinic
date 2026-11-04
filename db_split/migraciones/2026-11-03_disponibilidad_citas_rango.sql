-- Optimiza la consulta de disponibilidad de un terapeuta por rango de fechas.
-- Ejecutar una sola vez en la base configurada en DB_NAME.
DROP PROCEDURE IF EXISTS `sp_disponibilidad_citas_rango`;
DELIMITER $$
CREATE PROCEDURE `sp_disponibilidad_citas_rango`(
    IN p_terapeuta_id INT,
    IN p_desde DATE,
    IN p_hasta DATE
)
BEGIN
    SELECT fecha_cita, hora_cita
    FROM historial_citas
    WHERE terapeuta_id = p_terapeuta_id
      AND fecha_cita BETWEEN p_desde AND p_hasta
      AND estado IN ('pendiente_pago', 'programada', 'confirmada')
    ORDER BY fecha_cita, hora_cita;
END$$
DELIMITER ;
