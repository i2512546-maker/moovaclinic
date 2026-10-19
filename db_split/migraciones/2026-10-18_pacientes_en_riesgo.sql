-- ============================================================
-- MIGRACION: reporte de pacientes en riesgo de fuga (sustentacion)
-- Fecha:    2026-10-18
-- Base:     moovacloud_citas (Always Data)
--
-- IMPORTANTE: este archivo solo define procedimientos, NO toca
-- tablas ni inserta datos. Always Data ya tiene datos reales y no
-- se puede reimportar db_split/citas_db.sql completo. No hace
-- falta ningun ALTER TABLE: el reporte se calcula con las columnas
-- que historial_citas ya tiene.
--
-- La version para instalaciones nuevas esta en db_split/citas_db.sql.
-- ============================================================

DELIMITER $$

--
-- sp_pacientes_en_riesgo
--   Devuelve SOLO los pacientes en riesgo de fuga, con las metricas
--   crudas de citas. El nombre, el telefono y el nivel los agrega
--   citas_service (los datos del paciente viven en
--   moovacloud_pacientes y no se pueden consultar desde aqui).
--
--   Dos senales de abandono:
--     1. Sin cita futura programada/confirmada y ya paso el umbral
--        de dias desde la ultima cita.
--     2. Falto (estado 'no_asistio') tres o mas veces.
--
--   p_fecha: dia de referencia (hoy en America/Lima).
--   p_dias_umbral: dias desde la ultima cita para la senal 1.
--
DROP PROCEDURE IF EXISTS `sp_pacientes_en_riesgo`$$
CREATE PROCEDURE `sp_pacientes_en_riesgo`(IN p_fecha DATE, IN p_dias_umbral INT)
BEGIN
    SELECT
        h.paciente_id AS paciente_id,
        -- Ultima cita de cualquier tipo ya pasada: incluye las que
        -- quedaron 'programadas' y nunca se cerraron.
        MAX(CASE WHEN h.fecha_cita < p_fecha THEN h.fecha_cita END) AS ultima_cita,
        DATEDIFF(p_fecha, MAX(CASE WHEN h.fecha_cita < p_fecha THEN h.fecha_cita END))
            AS dias_desde_ultima,
        SUM(CASE WHEN h.fecha_cita >= p_fecha
                  AND h.estado IN ('programada', 'confirmada')
                 THEN 1 ELSE 0 END) AS citas_programadas,
        SUM(CASE WHEN h.estado = 'completada' THEN 1 ELSE 0 END) AS completadas,
        SUM(CASE WHEN h.estado = 'cancelada'  THEN 1 ELSE 0 END) AS canceladas,
        SUM(CASE WHEN h.estado = 'no_asistio' THEN 1 ELSE 0 END) AS faltas
    FROM historial_citas h
    GROUP BY h.paciente_id
    HAVING (
        -- 1) Sin cita futura y ya hace rato que no viene.
        (citas_programadas = 0 AND dias_desde_ultima >= p_dias_umbral)
        -- 2) Falto tres o mas veces.
        OR (faltas >= 3)
    )
    ORDER BY dias_desde_ultima DESC, faltas DESC;
END$$

DELIMITER ;

-- ============================================================
-- FIN 2026-10-18_pacientes_en_riesgo.sql
-- ============================================================
