-- ============================================================
-- MOOVA Clinic - Migracion v3 (Registro de Rehabilitaciones)
-- ============================================================
-- MODULO: Admin -> Pacientes -> Registro de rehabilitacion.
--
-- PARTE A: Tabla `rehabilitaciones` (aditiva, no toca tablas
--          existentes). Cada fila = una cita/sesion de
--          rehabilitacion numerada (Cita 1, Cita 2, ...).
--          La clave UNIQUE (paciente_id, numero_cita) garantiza
--          a nivel de base de datos que un paciente NO pueda
--          tener dos registros para la misma cita.
--
-- PARTE B: Procedimientos almacenados de lectura/escritura.
--          El numero de cita lo calcula el PROCEDURE (nunca el
--          cliente), de modo que solo se puede registrar la
--          siguiente cita disponible (secuencia estricta).
--
-- EJECUCION:
--   Local (XAMPP):  mysql -u root moovaclinic_db < migration_v3.sql
--   phpMyAdmin:     seleccionar la base correcta (moovacloud_db en
--                   produccion) y ejecutar todo el archivo.
--   Es retrocompatible: solo CREA tabla y PROCEDUREs nuevos.
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;
SET time_zone = '+00:00';

-- ============================================================
-- PARTE A: Tabla rehabilitaciones
-- ============================================================

CREATE TABLE IF NOT EXISTS `rehabilitaciones` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `paciente_id` int(11) NOT NULL,
  `numero_cita` int(11) NOT NULL COMMENT 'Cita 1, Cita 2, ... por paciente (secuencia estricta)',
  `dni` varchar(20) NOT NULL COMMENT 'DNI del paciente (denormalizado para busquedas)',
  `nombres` varchar(200) DEFAULT NULL,
  `apellidos` varchar(200) DEFAULT NULL,
  `fecha_cita` date NOT NULL,
  `hora_ingreso` time DEFAULT NULL,
  `hora_salida` time DEFAULT NULL,
  `motivo_diagnostico` text DEFAULT NULL,
  `area_tipo` varchar(150) DEFAULT NULL,
  `profesional` varchar(200) DEFAULT NULL,
  `observaciones` text DEFAULT NULL,
  `tratamiento` text DEFAULT NULL,
  `evolucion` text DEFAULT NULL,
  `estado` varchar(50) NOT NULL DEFAULT 'registrada',
  `proxima_cita` date DEFAULT NULL,
  `fecha_registro` datetime NOT NULL DEFAULT current_timestamp(),
  `registrado_por` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_rehab_paciente_cita` (`paciente_id`,`numero_cita`),
  KEY `idx_rehab_dni` (`dni`),
  KEY `idx_rehab_paciente` (`paciente_id`),
  CONSTRAINT `fk_rehab_paciente` FOREIGN KEY (`paciente_id`)
    REFERENCES `pacientes` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_rehab_registrado_por` FOREIGN KEY (`registrado_por`)
    REFERENCES `usuarios` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================
-- PARTE B: Procedimientos almacenados
-- ============================================================

DELIMITER $$

-- Lista todas las rehabilitaciones de un paciente (0..n, ordenadas)
DROP PROCEDURE IF EXISTS `sp_listar_rehabilitaciones`$$
CREATE PROCEDURE `sp_listar_rehabilitaciones`(IN p_paciente_id INT)
BEGIN
    SELECT * FROM rehabilitaciones
    WHERE paciente_id = p_paciente_id
    ORDER BY numero_cita ASC;
END$$

-- Proxima cita disponible + total de citas registradas del paciente
DROP PROCEDURE IF EXISTS `sp_proxima_cita_rehab`$$
CREATE PROCEDURE `sp_proxima_cita_rehab`(IN p_paciente_id INT)
BEGIN
    SELECT COALESCE(MAX(numero_cita), 0) + 1 AS proxima_cita,
           COUNT(*) AS total_citas
    FROM rehabilitaciones
    WHERE paciente_id = p_paciente_id;
END$$

-- Registra la SIGUIENTE cita de rehabilitacion del paciente.
-- El numero de cita lo calcula el procedimiento internamente
-- (MAX+1), por lo que el cliente no puede registrar fuera de
-- secuencia ni reutilizar una cita ya registrada.
DROP PROCEDURE IF EXISTS `sp_crear_rehabilitacion`$$
CREATE PROCEDURE `sp_crear_rehabilitacion`(
    IN p_paciente_id INT,
    IN p_dni VARCHAR(20),
    IN p_nombres VARCHAR(200),
    IN p_apellidos VARCHAR(200),
    IN p_fecha_cita DATE,
    IN p_hora_ingreso TIME,
    IN p_hora_salida TIME,
    IN p_motivo_diagnostico TEXT,
    IN p_area_tipo VARCHAR(150),
    IN p_profesional VARCHAR(200),
    IN p_observaciones TEXT,
    IN p_tratamiento TEXT,
    IN p_evolucion TEXT,
    IN p_estado VARCHAR(50),
    IN p_proxima_cita DATE,
    IN p_registrado_por INT
)
BEGIN
    DECLARE v_proximo INT DEFAULT 1;

    SELECT COALESCE(MAX(numero_cita), 0) + 1 INTO v_proximo
    FROM rehabilitaciones
    WHERE paciente_id = p_paciente_id;

    INSERT INTO rehabilitaciones (
        paciente_id, numero_cita, dni, nombres, apellidos,
        fecha_cita, hora_ingreso, hora_salida,
        motivo_diagnostico, area_tipo, profesional,
        observaciones, tratamiento, evolucion,
        estado, proxima_cita, registrado_por
    ) VALUES (
        p_paciente_id, v_proximo, p_dni, p_nombres, p_apellidos,
        p_fecha_cita, p_hora_ingreso, p_hora_salida,
        p_motivo_diagnostico, p_area_tipo, p_profesional,
        p_observaciones, p_tratamiento, p_evolucion,
        COALESCE(NULLIF(p_estado, ''), 'registrada'), p_proxima_cita, p_registrado_por
    );

    SELECT v_proximo AS numero_cita, ROW_COUNT() AS insertadas;
END$$

DELIMITER ;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- VERIFICACION
-- ============================================================
SELECT 'MIGRACION V3 (REHABILITACIONES) COMPLETADA' AS resultado;
DESCRIBE `rehabilitaciones`;
SHOW PROCEDURE STATUS WHERE Db = DATABASE() AND Name LIKE '%rehab';