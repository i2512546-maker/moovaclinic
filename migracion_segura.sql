-- ============================================================
-- MOOVA Clinic - Migracion segura de base de datos
-- Base: moovacloud_db en Alwaysdata
-- Ejecutar en phpMyAdmin > SQL
-- Seguro: verifica antes de crear/modificar
-- ============================================================

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

-- ============================================================
-- PASO 1: Crear tabla roles (si no existe)
-- ============================================================
CREATE TABLE IF NOT EXISTS `roles` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `nombre` varchar(50) NOT NULL,
  `descripcion` varchar(255) DEFAULT NULL,
  `permisos` text DEFAULT NULL,
  `activo` tinyint(1) NOT NULL DEFAULT 1,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `nombre` (`nombre`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Insertar roles solo si la tabla esta vacia
INSERT IGNORE INTO `roles` (`id`, `nombre`, `descripcion`, `permisos`) VALUES
(1, 'admin', 'Administrador del sistema', '{"citas":"all","terapeutas":"all","pagos":"all","config":"all","reportes":"all"}'),
(2, 'terapeuta', 'Terapeuta / medico', '{"citas":"own","notas":"own","horarios":"own"}'),
(3, 'recepcionista', 'Personal de recepcion', '{"citas":"all","pacientes":"all","pagos":"view"}');

-- ============================================================
-- PASO 2: Crear tabla usuarios (si no existe)
-- ============================================================
CREATE TABLE IF NOT EXISTS `usuarios` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) NOT NULL,
  `correo` varchar(100) NOT NULL,
  `clave` varchar(255) NOT NULL,
  `rol_id` int(11) NOT NULL,
  `terapeuta_id` int(11) DEFAULT NULL,
  `activo` tinyint(1) NOT NULL DEFAULT 1,
  `ultimo_acceso` datetime DEFAULT NULL,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp(),
  `actualizado_en` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `correo` (`correo`),
  KEY `rol_id` (`rol_id`),
  KEY `terapeuta_id` (`terapeuta_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================
-- PASO 3: Modificar terapeutas
--   Agregar columnas que falten (activo, timestamps)
--   Eliminar Correo y Clave si aun existen
-- ============================================================

SET FOREIGN_KEY_CHECKS = 0;

-- Agregar especialidad_id si no existe
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'terapeutas' AND COLUMN_NAME = 'especialidad_id');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `terapeutas` ADD COLUMN `especialidad_id` int(11) DEFAULT NULL AFTER `Especialidad`',
  'SELECT "especialidad_id ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Agregar activo si no existe
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'terapeutas' AND COLUMN_NAME = 'activo');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `terapeutas` ADD COLUMN `activo` tinyint(1) NOT NULL DEFAULT 1 AFTER `precio`',
  'SELECT "activo ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Agregar creado_en si no existe
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'terapeutas' AND COLUMN_NAME = 'creado_en');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `terapeutas` ADD COLUMN `creado_en` datetime NOT NULL DEFAULT current_timestamp() AFTER `activo`',
  'SELECT "creado_en ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Agregar actualizado_en si no existe
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'terapeutas' AND COLUMN_NAME = 'actualizado_en');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `terapeutas` ADD COLUMN `actualizado_en` datetime DEFAULT NULL ON UPDATE current_timestamp() AFTER `creado_en`',
  'SELECT "actualizado_en ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Eliminar Correo si existe
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'terapeutas' AND COLUMN_NAME = 'Correo');
SET @sql = IF(@col_exists > 0,
  'ALTER TABLE `terapeutas` DROP COLUMN `Correo`',
  'SELECT "Correo ya no existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Eliminar Clave si existe
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'terapeutas' AND COLUMN_NAME = 'Clave');
SET @sql = IF(@col_exists > 0,
  'ALTER TABLE `terapeutas` DROP COLUMN `Clave`',
  'SELECT "Clave ya no existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Agregar FK de especialidad_id si no existe
SET @fk_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'terapeutas' AND CONSTRAINT_NAME = 'fk_terapeutas_especialidad');
SET @sql = IF(@fk_exists = 0,
  'ALTER TABLE `terapeutas` ADD CONSTRAINT `fk_terapeutas_especialidad` FOREIGN KEY (`especialidad_id`) REFERENCES `especialidades` (`id`) ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT "FK especialidad ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- PASO 4: Eliminar tabla admins (ya no se usa, auth va por usuarios)
-- ============================================================
SET FOREIGN_KEY_CHECKS = 0;

-- Migrar admins a usuarios (si la tabla existe)
SET @admins_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'admins');
SELECT @admins_exists AS admins_tabla_existe;

-- Si hay admins, copiarlos a usuarios
INSERT IGNORE INTO `usuarios` (`nombre`, `correo`, `clave`, `rol_id`, `activo`)
SELECT `nombre`, `correo`, `clave`, 1, 1 FROM `admins`
WHERE @admins_exists > 0;

-- Eliminar la tabla admins
DROP TABLE IF EXISTS `admins`;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- PASO 5: Migrar datos de terapeutas a usuarios
-- ============================================================

-- Mapear especialidad texto a especialidad_id
UPDATE `terapeutas` SET `especialidad_id` = 1 WHERE `Especialidad` = 'Muscular' AND (`especialidad_id` IS NULL OR `especialidad_id` = 0);
UPDATE `terapeutas` SET `especialidad_id` = 6 WHERE `Especialidad` = 'Cardiorrespiratoria' AND (`especialidad_id` IS NULL OR `especialidad_id` = 0);

-- Insertar terapeutas en usuarios (solo si no existen ya por correo)
-- Dra.Becky
INSERT IGNORE INTO `usuarios` (`nombre`, `correo`, `clave`, `rol_id`, `terapeuta_id`, `activo`)
SELECT `Nombre`, IFNULL((SELECT CONCAT(`Nombre`, '@moova.com') FROM DUAL), 'ander@gmail.com'),
       '$2b$12$KNwxZqdQ8uOLXsNRsETZqe0XUfaw/inUTM2OrFnTlTWdix0yGBf4q',
       2, `ID`, 1
FROM `terapeutas` WHERE `ID` = 1 AND NOT EXISTS (SELECT 1 FROM `usuarios` WHERE `correo` = 'ander@gmail.com');

-- JORDY
INSERT IGNORE INTO `usuarios` (`nombre`, `correo`, `clave`, `rol_id`, `terapeuta_id`, `activo`)
SELECT `Nombre`, 'villegasc@moova.com',
       '$2b$12$oK2pcSRBbQKk/RMudHXQe.t/a6f3gDq4Z1Ez6txrIaR9DL60qBm6u',
       2, `ID`, 1
FROM `terapeutas` WHERE `ID` = 2 AND NOT EXISTS (SELECT 1 FROM `usuarios` WHERE `correo` = 'villegasc@moova.com');

-- Jeon
INSERT IGNORE INTO `usuarios` (`nombre`, `correo`, `clave`, `rol_id`, `terapeuta_id`, `activo`)
SELECT `Nombre`, 'jeon@moova.com',
       '$2b$12$Ep1Zx9VGyUnJQFoPyzQQVO1Cz4HEI7EWVIrHNkJckYX8dOqvPISmW',
       2, `ID`, 1
FROM `terapeutas` WHERE `ID` = 3 AND NOT EXISTS (SELECT 1 FROM `usuarios` WHERE `correo` = 'jeon@moova.com');

-- Insertar admins
INSERT IGNORE INTO `usuarios` (`id`, `nombre`, `correo`, `clave`, `rol_id`, `activo`) VALUES
(1, 'Administrador', 'admin@moova.com', '$2b$12$76VElioTEpM77sjDETiOBugLR2/wgDEmx4qEHFteiJEYMro7NLMji', 1, 1),
(2, 'Administrador 2', 'admin2@moova.com', '$2b$12$7Niuc7pdsDgH4qN0zCkSaeswC1GHFZBiQLcziHTyjEprDD38f5Y7q', 1, 1),
(3, 'Administrador 3', 'admin3@moova.com', '$2b$12$HOa38jTCoZFY1rfpnseWa.WGznEhncrn6DYQBCfwES7z2IWrpqXYm', 1, 1);

-- ============================================================
-- PASO 6: Modificar personas
--   Agregar estado, email, timestamps si faltan
-- ============================================================

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'personas' AND COLUMN_NAME = 'estado');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `personas` ADD COLUMN `estado` enum(''activo'',''inactivo'') NOT NULL DEFAULT ''activo'' AFTER `telefono`',
  'SELECT "personas.estado ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'personas' AND COLUMN_NAME = 'email');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `personas` ADD COLUMN `email` varchar(100) DEFAULT NULL AFTER `estado`',
  'SELECT "personas.email ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'personas' AND COLUMN_NAME = 'creado_en');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `personas` ADD COLUMN `creado_en` datetime NOT NULL DEFAULT current_timestamp() AFTER `email`',
  'SELECT "personas.creado_en ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'personas' AND COLUMN_NAME = 'actualizado_en');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `personas` ADD COLUMN `actualizado_en` datetime DEFAULT NULL ON UPDATE current_timestamp() AFTER `creado_en`',
  'SELECT "personas.actualizado_en ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ============================================================
-- PASO 7: Modificar historial_citas
--   Agregar hora_cita si falta
-- ============================================================

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'historial_citas' AND COLUMN_NAME = 'hora_cita');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `historial_citas` ADD COLUMN `hora_cita` time DEFAULT NULL AFTER `fecha_cita`',
  'SELECT "hora_cita ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ============================================================
-- PASO 8: Modificar pagos
--   Agregar columnas de verificacion si faltan
-- ============================================================

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'pagos' AND COLUMN_NAME = 'transaccion_id');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `pagos` ADD COLUMN `transaccion_id` varchar(100) DEFAULT NULL AFTER `referencia`',
  'SELECT "transaccion_id ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'pagos' AND COLUMN_NAME = 'comprobante_url');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `pagos` ADD COLUMN `comprobante_url` varchar(255) DEFAULT NULL AFTER `transaccion_id`',
  'SELECT "comprobante_url ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'pagos' AND COLUMN_NAME = 'datos_respuesta');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `pagos` ADD COLUMN `datos_respuesta` text DEFAULT NULL AFTER `comprobante_url`',
  'SELECT "datos_respuesta ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'pagos' AND COLUMN_NAME = 'intentos_verificacion');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `pagos` ADD COLUMN `intentos_verificacion` int(11) NOT NULL DEFAULT 0 AFTER `datos_respuesta`',
  'SELECT "intentos_verificacion ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'pagos' AND COLUMN_NAME = 'verificado_en');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `pagos` ADD COLUMN `verificado_en` datetime DEFAULT NULL AFTER `intentos_verificacion`',
  'SELECT "verificado_en ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ============================================================
-- PASO 9: Crear tabla notas_clinicas (si no existe)
-- ============================================================
CREATE TABLE IF NOT EXISTS `notas_clinicas` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `cita_id` int(11) NOT NULL,
  `paciente_id` int(11) DEFAULT NULL,
  `terapeuta_id` int(11) DEFAULT NULL,
  `nota` text NOT NULL,
  `diagnostico` varchar(255) DEFAULT NULL,
  `fecha_creacion` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `cita_id` (`cita_id`),
  KEY `paciente_id` (`paciente_id`),
  KEY `terapeuta_id` (`terapeuta_id`),
  CONSTRAINT `notas_clinicas_ibfk_1` FOREIGN KEY (`cita_id`) REFERENCES `historial_citas` (`id`) ON DELETE CASCADE,
  CONSTRAINT `notas_clinicas_ibfk_2` FOREIGN KEY (`paciente_id`) REFERENCES `personas` (`id`) ON DELETE SET NULL,
  CONSTRAINT `notas_clinicas_ibfk_3` FOREIGN KEY (`terapeuta_id`) REFERENCES `terapeutas` (`ID`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================
-- PASO 10: Crear tabla horarios_medico (si no existe)
-- ============================================================
CREATE TABLE IF NOT EXISTS `horarios_medico` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `terapeuta_id` int(11) NOT NULL,
  `dia_semana` tinyint(1) NOT NULL COMMENT '0=Dom, 1=Lun, ..., 6=Sat',
  `hora_inicio` time NOT NULL,
  `hora_fin` time NOT NULL,
  `activo` tinyint(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  KEY `terapeuta_id` (`terapeuta_id`),
  CONSTRAINT `horarios_medico_ibfk_1` FOREIGN KEY (`terapeuta_id`) REFERENCES `terapeutas` (`ID`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================
-- PASO 11: Crear tabla configuracion (si no existe)
-- ============================================================
CREATE TABLE IF NOT EXISTS `configuracion` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `clave` varchar(50) NOT NULL,
  `valor` varchar(255) NOT NULL,
  `descripcion` text DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `clave` (`clave`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT IGNORE INTO `configuracion` (`clave`, `valor`, `descripcion`) VALUES
('anio_inicio', '2023', 'Anio de inicio de actividades de la clinica');

-- ============================================================
-- PASO 12: Crear tabla opiniones (si no existe)
-- ============================================================
CREATE TABLE IF NOT EXISTS `opiniones` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `persona_id` int(11) DEFAULT NULL,
  `nombre_paciente` varchar(100) NOT NULL,
  `calificacion` tinyint(1) NOT NULL,
  `comentario` text DEFAULT NULL,
  `visible` tinyint(1) NOT NULL DEFAULT 1,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_calificacion` (`calificacion`),
  KEY `idx_visible` (`visible`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================
-- PASO 13: Ajustar AUTO_INCREMENTs
-- ============================================================
SET @max_id = (SELECT IFNULL(MAX(id), 0) FROM `usuarios`);
SET @sql = CONCAT('ALTER TABLE `usuarios` AUTO_INCREMENT = ', @max_id + 1);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @max_id = (SELECT IFNULL(MAX(id), 0) FROM `roles`);
SET @sql = CONCAT('ALTER TABLE `roles` AUTO_INCREMENT = ', @max_id + 1);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

COMMIT;

-- ============================================================
-- VERIFICACION: mostrar resultado
-- ============================================================
SELECT 'MIGRACION COMPLETADA' AS resultado;
SHOW TABLES;
