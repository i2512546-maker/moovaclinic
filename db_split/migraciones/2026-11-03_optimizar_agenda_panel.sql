-- ============================================================
-- Optimizacion de agenda y resumen del panel administrador.
-- No elimina ni modifica datos existentes.
-- Ejecutar una sola vez en la base configurada en DB_NAME.
-- ============================================================

-- Indice compuesto para filtrar por estado y fecha sin recorrer
-- historiales completos al contar cancelaciones/inasistencias.
SET @existe_idx_estado_fecha = (
    SELECT COUNT(*) FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'historial_citas'
      AND index_name = 'idx_estado_fecha_cita'
);
SET @sql_idx_estado_fecha = IF(
    @existe_idx_estado_fecha = 0,
    'ALTER TABLE historial_citas ADD INDEX idx_estado_fecha_cita (estado, fecha_cita)',
    'SELECT 1'
);
PREPARE stmt_idx_estado_fecha FROM @sql_idx_estado_fecha;
EXECUTE stmt_idx_estado_fecha;
DEALLOCATE PREPARE stmt_idx_estado_fecha;

DROP PROCEDURE IF EXISTS sp_listar_citas_dia;
DROP PROCEDURE IF EXISTS sp_resumen_citas_estados;
DROP PROCEDURE IF EXISTS sp_resumen_pacientes_agenda;

DELIMITER $$
CREATE PROCEDURE sp_listar_citas_dia(IN p_fecha DATE)
BEGIN
    SELECT h.id, h.id AS historial_id, h.fecha_cita, h.hora_cita, h.estado,
           h.descripcion, h.paciente_id, h.terapeuta_id, h.servicio_id
    FROM historial_citas h
    WHERE h.fecha_cita = p_fecha
      AND h.estado IN ('programada', 'confirmada', 'cancelada', 'completada', 'no_asistio')
    ORDER BY h.hora_cita ASC, h.id ASC;
END$$

CREATE PROCEDURE sp_resumen_citas_estados(IN p_desde DATE)
BEGIN
    SELECT h.estado, COUNT(*) AS total
    FROM historial_citas h
    WHERE h.estado IN ('cancelada', 'no_asistio')
      AND h.fecha_cita >= p_desde
    GROUP BY h.estado;
END$$

CREATE PROCEDURE sp_resumen_pacientes_agenda(IN p_fecha DATE)
BEGIN
    SELECT h.paciente_id, COUNT(*) AS total, MAX(h.fecha_cita) AS ultima
    FROM historial_citas h
    WHERE h.estado <> 'pendiente_pago'
      AND h.paciente_id IN (
          SELECT DISTINCT dia.paciente_id
          FROM historial_citas dia
          WHERE dia.fecha_cita = p_fecha
            AND dia.estado IN ('programada', 'confirmada', 'cancelada', 'completada', 'no_asistio')
      )
    GROUP BY h.paciente_id;
END$$
DELIMITER ;

-- Fin de migracion.