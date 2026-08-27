-- ============================================================
-- MOOVA Clinic - Migracion v2 (ACTUALIZADA post migration_v3)
-- Base: moovacloud_db en Alwaysdata (MariaDB 11.4)
-- ============================================================
-- CAMBIOS ya aplicados en v3:
--   - personas -> pacientes (mismo nombre, tabla renombrada)
--   - persona_id -> paciente_id en historial_citas, pagos
--   - terapeutas.ID -> terapeutas.id (minuscula)
--   - terapeutas: eliminadas columnas Nombre y Telefono
--   - terapeutas: agregada columna usuario_id (FK -> usuarios.id)
-- ============================================================
-- ESTE SCRIPT asume que v3 ya fue ejecutado.
-- Solo aplica cambios pendientes: columnas nuevas en pacientes,
-- tablas nuevas, y columna telefono en usuarios.
-- ============================================================
-- EJECUTAR: Copiar todo este archivo y pegarlo en phpMyAdmin > SQL
-- sobre moovacloud_db. Hacer backup con mysqldump ANTES.
-- ============================================================

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";
SET FOREIGN_KEY_CHECKS = 0;

USE `moovacloud_db`;

-- ============================================================
-- PARTE 1: Agregar columna telefono a usuarios
--   Necesaria para que terapeutas muestren telefono via JOIN
-- ============================================================

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'usuarios' AND COLUMN_NAME = 'telefono');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `usuarios` ADD COLUMN `telefono` varchar(20) DEFAULT NULL AFTER `correo`',
  'SELECT "telefono ya existe en usuarios"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;


-- ============================================================
-- PARTE 2: Agregar columnas a pacientes (antes personas)
--   fecha_nacimiento, sexo, direccion, seguro
-- ============================================================

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'pacientes' AND COLUMN_NAME = 'fecha_nacimiento');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `pacientes` ADD COLUMN `fecha_nacimiento` date DEFAULT NULL AFTER `email`',
  'SELECT "fecha_nacimiento ya existe en pacientes"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'pacientes' AND COLUMN_NAME = 'sexo');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `pacientes` ADD COLUMN `sexo` enum(''M'',''F'',''otro'') DEFAULT NULL AFTER `fecha_nacimiento`',
  'SELECT "sexo ya existe en pacientes"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'pacientes' AND COLUMN_NAME = 'direccion');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `pacientes` ADD COLUMN `direccion` varchar(255) DEFAULT NULL AFTER `sexo`',
  'SELECT "direccion ya existe en pacientes"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'pacientes' AND COLUMN_NAME = 'seguro');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `pacientes` ADD COLUMN `seguro` varchar(100) DEFAULT NULL AFTER `direccion`',
  'SELECT "seguro ya existe en pacientes"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;


-- ============================================================
-- PARTE 3: Indices y UNIQUE en historial_citas
-- ============================================================

SET @idx_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'historial_citas'
    AND INDEX_NAME = 'idx_fecha_cita');
SET @sql = IF(@idx_exists = 0,
  'ALTER TABLE `historial_citas` ADD INDEX `idx_fecha_cita` (`fecha_cita`)',
  'SELECT "idx_fecha_cita ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @uniq_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'historial_citas'
    AND INDEX_NAME = 'uq_reserva');
SET @sql = IF(@uniq_exists = 0,
  'ALTER TABLE `historial_citas` ADD UNIQUE KEY `uq_reserva` (`terapeuta_id`, `fecha_cita`, `hora_cita`)',
  'SELECT "uq_reserva ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;


-- ============================================================
-- PARTE 4: Tabla servicios (catalogo)
-- ============================================================

CREATE TABLE IF NOT EXISTS `servicios` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) NOT NULL,
  `descripcion` text DEFAULT NULL,
  `duracion_min` int(11) NOT NULL DEFAULT 60,
  `precio` decimal(10,2) NOT NULL DEFAULT 0.00,
  `activo` tinyint(1) NOT NULL DEFAULT 1,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_servicio_activo` (`activo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT IGNORE INTO `servicios` (`id`, `nombre`, `descripcion`, `duracion_min`, `precio`) VALUES
(1, 'Sesion de Fisioterapia', 'Sesion individual de rehabilitacion fisica', 60, 80.00),
(2, 'Sesion de Terapia Cardiorrespiratoria', 'Rehabilitacion cardiorrespiratoria', 60, 100.00),
(3, 'Sesion de Terapia Muscular', 'Fortalecimiento y recuperacion muscular', 45, 70.00),
(4, 'Evaluacion Inicial', 'Evaluacion completa del paciente nuevo', 30, 50.00);


-- ============================================================
-- PARTE 5: Tabla evaluaciones_iniciales
--   FK paciente_id -> pacientes.id (int)
--   FK terapeuta_id -> terapeutas.id (int)
-- ============================================================

CREATE TABLE IF NOT EXISTS `evaluaciones_iniciales` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `paciente_id` int(11) NOT NULL,
  `terapeuta_id` int(11) NOT NULL,
  `motivo_consulta` text NOT NULL,
  `escala_dolor_eva` tinyint(1) DEFAULT NULL COMMENT 'EVA 0-10',
  `rango_movimiento` text DEFAULT NULL,
  `objetivos_terapeuticos` text DEFAULT NULL,
  `fecha_creacion` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_ei_paciente` (`paciente_id`),
  KEY `idx_ei_terapeuta` (`terapeuta_id`),
  CONSTRAINT `fk_ei_paciente` FOREIGN KEY (`paciente_id`)
    REFERENCES `pacientes` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_ei_terapeuta` FOREIGN KEY (`terapeuta_id`)
    REFERENCES `terapeutas` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


-- ============================================================
-- PARTE 6: Tabla paquetes_sesiones
--   FK paciente_id -> pacientes.id (int)
-- ============================================================

CREATE TABLE IF NOT EXISTS `paquetes_sesiones` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `paciente_id` int(11) NOT NULL,
  `servicio_id` int(11) NOT NULL,
  `total_sesiones` int(11) NOT NULL,
  `sesiones_usadas` int(11) NOT NULL DEFAULT 0,
  `fecha_compra` date NOT NULL,
  `fecha_vencimiento` date DEFAULT NULL,
  `estado` enum('activo','agotado','vencido','cancelado') NOT NULL DEFAULT 'activo',
  `creado_en` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_ps_paciente` (`paciente_id`),
  KEY `idx_ps_servicio` (`servicio_id`),
  KEY `idx_ps_estado` (`estado`),
  CONSTRAINT `fk_ps_paciente` FOREIGN KEY (`paciente_id`)
    REFERENCES `pacientes` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_ps_servicio` FOREIGN KEY (`servicio_id`)
    REFERENCES `servicios` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


-- ============================================================
-- PARTE 7: Tabla consentimientos
--   FK paciente_id -> pacientes.id (int)
-- ============================================================

CREATE TABLE IF NOT EXISTS `consentimientos` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `paciente_id` int(11) NOT NULL,
  `tipo` varchar(50) NOT NULL COMMENT 'general, tratamiento, cirugia',
  `texto_version` varchar(50) NOT NULL COMMENT 'v1.0, v2.1',
  `aceptado_en` datetime NOT NULL DEFAULT current_timestamp(),
  `ip_origen` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_consent_paciente` (`paciente_id`),
  KEY `idx_consent_tipo` (`tipo`),
  CONSTRAINT `fk_consent_paciente` FOREIGN KEY (`paciente_id`)
    REFERENCES `pacientes` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


-- ============================================================
-- VERIFICACION FINAL
-- ============================================================

SET FOREIGN_KEY_CHECKS = 1;

SELECT 'MIGRACION V2 COMPLETADA' AS resultado;

DESCRIBE `pacientes`;
DESCRIBE `terapeutas`;
DESCRIBE `usuarios`;
DESCRIBE `historial_citas`;
SHOW TABLES;
