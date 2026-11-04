-- MOOVA Clinic: guardado automatico de notas y cierre diario.
-- Ejecutar en DB_NAME despues de las migraciones anteriores.
DELIMITER $$

DROP PROCEDURE IF EXISTS `sp_actualizar_descripcion_cita`$$
CREATE PROCEDURE `sp_actualizar_descripcion_cita`(IN p_historial_id INT, IN p_descripcion TEXT)
BEGIN
    UPDATE historial_citas
    SET descripcion = p_descripcion, actualizado_en = NOW()
    WHERE id = p_historial_id
      AND estado IN ('programada', 'confirmada');
END$$

DROP PROCEDURE IF EXISTS `sp_completar_citas_con_notas_del_dia`$$
CREATE PROCEDURE `sp_completar_citas_con_notas_del_dia`(IN p_fecha DATE)
BEGIN
    UPDATE historial_citas
    SET estado = 'completada', actualizado_en = NOW()
    WHERE DATE(fecha_cita) = p_fecha
      AND estado IN ('programada', 'confirmada')
      AND descripcion IS NOT NULL
      AND TRIM(descripcion) <> '';
    SELECT ROW_COUNT() AS actualizadas;
END$$

DELIMITER ;
