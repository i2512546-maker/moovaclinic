-- ============================================================
-- MOOVA Clinic - Migracion v4 (Pacientes + Rehabilitaciones)
-- ============================================================
-- ADITIVO: no toca tablas ni procedures existentes.
-- Ejecutar: mysql -u root moovacloud_db < migration_v4.sql
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;
SET time_zone = '+00:00';

DELIMITER $$

-- ============================================================
-- PARTE A: Obtener terapeutas activos (catalogo para form rehab)
-- ============================================================

DROP PROCEDURE IF EXISTS `sp_listar_terapeutas_activos`$$
CREATE PROCEDURE `sp_listar_terapeutas_activos`()
BEGIN
    SELECT t.id AS terapeuta_id, u.nombre AS terapeuta_nombre,
           e.nombre AS especialidad
    FROM terapeutas t
    JOIN usuarios u ON t.usuario_id = u.id
    LEFT JOIN especialidades e ON t.especialidad_id = e.id
    WHERE t.activo = 1
    ORDER BY u.nombre;
END$$

-- ============================================================
-- PARTE B: Obtener areas/tipos de rehabilitacion (catalogo)
-- ============================================================

DROP PROCEDURE IF EXISTS `sp_listar_areas_rehabilitacion`$$
CREATE PROCEDURE `sp_listar_areas_rehabilitacion`()
BEGIN
    SELECT id, nombre FROM servicios WHERE activo = 1 ORDER BY nombre;
END$$

-- ============================================================
-- PARTE C: Validar si una cita ya esta registrada (backend check)
-- ============================================================

DROP PROCEDURE IF EXISTS `sp_existe_rehabilitacion_cita`$$
CREATE PROCEDURE `sp_existe_rehabilitacion_cita`(
    IN p_paciente_id INT, IN p_numero_cita INT
)
BEGIN
    SELECT id, numero_cita, estado
    FROM rehabilitaciones
    WHERE paciente_id = p_paciente_id AND numero_cita = p_numero_cita;
END$$

-- ============================================================
-- PARTE D: Resumen de rehabilitaciones (para badges/contadores)
-- ============================================================

DROP PROCEDURE IF EXISTS `sp_resumen_rehabilitaciones`$$
CREATE PROCEDURE `sp_resumen_rehabilitaciones`(IN p_paciente_id INT)
BEGIN
    SELECT COUNT(*) AS total_registradas,
           COALESCE(MAX(numero_cita), 0) AS ultima_cita,
           COALESCE(MAX(numero_cita), 0) + 1 AS proxima_cita_disponible
    FROM rehabilitaciones
    WHERE paciente_id = p_paciente_id;
END$$

DELIMITER ;

SET FOREIGN_KEY_CHECKS = 1;

SELECT 'MIGRACION v4 (PACIENTES + REHABILITACIONES) COMPLETADA' AS resultado;
