-- ============================================================
-- MOOVA Clinic - Migracion segura de base de datos
-- Base: moovacloud_db en Alwaysdata
-- Ejecutar en phpMyAdmin > SQL
-- ============================================================
-- Cambios:
--   1. Tabla usuarios: general, sin terapeuta_id
--   2. Tabla personas: dni como PK (sin id auto_increment)
--   3. FKs actualizadas en historial_citas, pagos, notas_clinicas
--   4. Tabla admins eliminada
-- ============================================================

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";
SET FOREIGN_KEY_CHECKS = 0;

USE `moovacloud_db`;

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

INSERT IGNORE INTO `roles` (`id`, `nombre`, `descripcion`, `permisos`) VALUES
(1, 'admin', 'Administrador del sistema', '{"citas":"all","terapeutas":"all","pagos":"all","config":"all","reportes":"all"}'),
(2, 'terapeuta', 'Terapeuta / medico', '{"citas":"own","notas":"own","horarios":"own"}'),
(3, 'recepcionista', 'Personal de recepcion', '{"citas":"all","pacientes":"all","pagos":"view"}');

-- ============================================================
-- PASO 2: Crear/recrear tabla usuarios SIN terapeuta_id
--   Tabla general: id, nombre, correo, clave, rol_id, activo
-- ============================================================

-- Si la tabla usuarios existe con terapeuta_id, la recreamos
SET @table_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'usuarios');

-- Guardar datos existentes en una tabla temporal
SET @sql = IF(@table_exists > 0,
  'CREATE TABLE IF NOT EXISTS `usuarios_backup` AS SELECT id, nombre, correo, clave, rol_id, activo, ultimo_acceso, creado_en, actualizado_en FROM `usuarios`',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Eliminar tabla vieja si tiene terapeuta_id
SET @has_terapeuta_id = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'usuarios' AND COLUMN_NAME = 'terapeuta_id');
SET @sql = IF(@has_terapeuta_id > 0,
  'DROP TABLE IF EXISTS `usuarios`',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Crear tabla usuarios limpia (sin terapeuta_id)
CREATE TABLE IF NOT EXISTS `usuarios` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) NOT NULL,
  `correo` varchar(100) NOT NULL,
  `clave` varchar(255) NOT NULL,
  `rol_id` int(11) NOT NULL,
  `activo` tinyint(1) NOT NULL DEFAULT 1,
  `ultimo_acceso` datetime DEFAULT NULL,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp(),
  `actualizado_en` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `correo` (`correo`),
  KEY `rol_id` (`rol_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Restaurar datos desde backup
SET @backup_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'usuarios_backup');
SET @sql = IF(@backup_exists > 0,
  'INSERT IGNORE INTO `usuarios` (`id`, `nombre`, `correo`, `clave`, `rol_id`, `activo`, `ultimo_acceso`, `creado_en`, `actualizado_en`) SELECT `id`, `nombre`, `correo`, `clave`, `rol_id`, `activo`, `ultimo_acceso`, `creado_en`, `actualizado_en` FROM `usuarios_backup`',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Eliminar tabla backup
DROP TABLE IF EXISTS `usuarios_backup`;

-- ============================================================
-- PASO 3: Modificar terapeutas (sin tocar la tabla en si)
--   Solo agregar columnas que falten y quitar Correo/Clave
-- ============================================================

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

-- ============================================================
-- PASO 4: Eliminar tabla admins
-- ============================================================

SET @admins_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'admins');
SELECT @admins_exists AS admins_tabla_existe;

INSERT IGNORE INTO `usuarios` (`nombre`, `correo`, `clave`, `rol_id`, `activo`)
SELECT `nombre`, `correo`, `clave`, 1, 1 FROM `admins`
WHERE @admins_exists > 0;

DROP TABLE IF EXISTS `admins`;

-- ============================================================
-- PASO 5: Insertar terapeutas en usuarios (sin terapeuta_id)
-- ============================================================

-- Mapear especialidad texto a especialidad_id
UPDATE `terapeutas` SET `especialidad_id` = 1 WHERE `Especialidad` = 'Muscular' AND (`especialidad_id` IS NULL OR `especialidad_id` = 0);
UPDATE `terapeutas` SET `especialidad_id` = 6 WHERE `Especialidad` = 'Cardiorrespiratoria' AND (`especialidad_id` IS NULL OR `especialidad_id` = 0);

-- Dra.Becky
INSERT IGNORE INTO `usuarios` (`nombre`, `correo`, `clave`, `rol_id`, `activo`)
SELECT `Nombre`, IFNULL((SELECT CONCAT(`Nombre`, '@moova.com') FROM DUAL), 'ander@gmail.com'),
       '$2b$12$KNwxZqdQ8uOLXsNRsETZqe0XUfaw/inUTM2OrFnTlTWdix0yGBf4q',
       2, 1
FROM `terapeutas` WHERE `ID` = 1 AND NOT EXISTS (SELECT 1 FROM `usuarios` WHERE `correo` = 'ander@gmail.com');

-- JORDY
INSERT IGNORE INTO `usuarios` (`nombre`, `correo`, `clave`, `rol_id`, `activo`)
SELECT `Nombre`, 'villegasc@moova.com',
       '$2b$12$oK2pcSRBbQKk/RMudHXQe.t/a6f3gDq4Z1Ez6txrIaR9DL60qBm6u',
       2, 1
FROM `terapeutas` WHERE `ID` = 2 AND NOT EXISTS (SELECT 1 FROM `usuarios` WHERE `correo` = 'villegasc@moova.com');

-- Jeon
INSERT IGNORE INTO `usuarios` (`nombre`, `correo`, `clave`, `rol_id`, `activo`)
SELECT `Nombre`, 'jeon@moova.com',
       '$2b$12$Ep1Zx9VGyUnJQFoPyzQQVO1Cz4HEI7EWVIrHNkJckYX8dOqvPISmW',
       2, 1
FROM `terapeutas` WHERE `ID` = 3 AND NOT EXISTS (SELECT 1 FROM `usuarios` WHERE `correo` = 'jeon@moova.com');

-- Insertar admins
INSERT IGNORE INTO `usuarios` (`id`, `nombre`, `correo`, `clave`, `rol_id`, `activo`) VALUES
(1, 'Administrador', 'admin@moova.com', '$2b$12$76VElioTEpM77sjDETiOBugLR2/wgDEmx4qEHFteiJEYMro7NLMji', 1, 1),
(2, 'Administrador 2', 'admin2@moova.com', '$2b$12$7Niuc7pdsDgH4qN0zCkSaeswC1GHFZBiQLcziHTyjEprDD38f5Y7q', 1, 1),
(3, 'Administrador 3', 'admin3@moova.com', '$2b$12$HOa38jTCoZFY1rfpnseWa.WGznEhncrn6DYQBCfwES7z2IWrpqXYm', 1, 1);

-- ============================================================
-- PASO 6: Modificar personas
--   Agregar columnas nuevas
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
-- PASO 7: Migrar datos persona_id de INT a VARCHAR(dni)
--   Antes de cambiar PK, copiar el dni a las tablas hijas
-- ============================================================

-- historial_citas: convertir persona_id de INT a VARCHAR
SET @col_type = (SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'historial_citas' AND COLUMN_NAME = 'persona_id');
SET @sql = IF(@col_type = 'int',
  'ALTER TABLE `historial_citas` MODIFY COLUMN `persona_id` varchar(15) NOT NULL',
  'SELECT "historial_citas.persona_id ya es varchar"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Rellenar persona_id con dni usando el id viejo
UPDATE `historial_citas` h
  INNER JOIN `personas` p ON h.persona_id = p.id
  SET h.persona_id = p.dni
  WHERE h.persona_id REGEXP '^[0-9]+$';

-- pagos: convertir persona_id de INT a VARCHAR
SET @col_type = (SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'pagos' AND COLUMN_NAME = 'persona_id');
SET @sql = IF(@col_type = 'int',
  'ALTER TABLE `pagos` MODIFY COLUMN `persona_id` varchar(15) NOT NULL',
  'SELECT "pagos.persona_id ya es varchar"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

UPDATE `pagos` pg
  INNER JOIN `personas` p ON pg.persona_id = p.id
  SET pg.persona_id = p.dni
  WHERE pg.persona_id REGEXP '^[0-9]+$';

-- notas_clinicas: convertir paciente_id de INT a VARCHAR
SET @col_type = (SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'notas_clinicas' AND COLUMN_NAME = 'paciente_id');
SET @sql = IF(@col_type = 'int',
  'ALTER TABLE `notas_clinicas` MODIFY COLUMN `paciente_id` varchar(15) DEFAULT NULL',
  'SELECT "notas_clinicas.paciente_id ya es varchar"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

UPDATE `notas_clinicas` nc
  INNER JOIN `personas` p ON nc.paciente_id = p.id
  SET nc.paciente_id = p.dni
  WHERE nc.paciente_id REGEXP '^[0-9]+$';

-- opiniones: convertir persona_id de INT a VARCHAR
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'opiniones' AND COLUMN_NAME = 'persona_id');
SET @sql = IF(@col_exists > 0,
  'ALTER TABLE `opiniones` MODIFY COLUMN `persona_id` varchar(15) DEFAULT NULL',
  'SELECT "opiniones no tiene persona_id"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ============================================================
-- PASO 8: Eliminar FKs que referencian personas(id)
-- ============================================================

-- historial_citas FK
SET @fk_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'historial_citas' AND CONSTRAINT_TYPE = 'FOREIGN KEY');
SET @sql = IF(@fk_exists > 0,
  'ALTER TABLE `historial_citas` DROP FOREIGN KEY `historial_citas_ibfk_2`',
  'SELECT "no FK en historial_citas"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- pagos FK
SET @fk_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'pagos' AND CONSTRAINT_TYPE = 'FOREIGN KEY');
SET @sql = IF(@fk_exists > 0,
  'ALTER TABLE `pagos` DROP FOREIGN KEY `pagos_ibfk_1`',
  'SELECT "no FK en pagos"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- notas_clinicas FK a personas
SET @fk_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'notas_clinicas' AND CONSTRAINT_NAME = 'notas_clinicas_ibfk_2');
SET @sql = IF(@fk_exists > 0,
  'ALTER TABLE `notas_clinicas` DROP FOREIGN KEY `notas_clinicas_ibfk_2`',
  'SELECT "no FK notas->personas"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ============================================================
-- PASO 9: Cambiar PK de personas: de id a dni
-- ============================================================

-- Eliminar PK actual (id)
SET @pk_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'personas' AND CONSTRAINT_TYPE = 'PRIMARY KEY');
SET @sql = IF(@pk_exists > 0,
  'ALTER TABLE `personas` DROP PRIMARY KEY',
  'SELECT "no PK en personas"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Eliminar UNIQUE KEY en dni (ya va a ser PK)
SET @uniq_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'personas' AND NON_UNIQUE = 0 AND COLUMN_NAME = 'dni' AND SEQ_IN_INDEX > 0);
SET @sql = IF(@uniq_exists > 0,
  'ALTER TABLE `personas` DROP INDEX `dni`',
  'SELECT "no UNIQUE dni"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Eliminar columna id si aun existe
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'personas' AND COLUMN_NAME = 'id');
SET @sql = IF(@col_exists > 0,
  'ALTER TABLE `personas` DROP COLUMN `id`',
  'SELECT "columna id ya eliminada"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Hacer dni la PRIMARY KEY
ALTER TABLE `personas` ADD PRIMARY KEY (`dni`);

-- ============================================================
-- PASO 10: Recrear FKs apuntando a personas(dni)
-- ============================================================

-- historial_citas: FK persona_id -> personas(dni)
SET @fk_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'historial_citas' AND CONSTRAINT_NAME = 'fk_hc_persona');
SET @sql = IF(@fk_exists = 0,
  'ALTER TABLE `historial_citas` ADD CONSTRAINT `fk_hc_persona` FOREIGN KEY (`persona_id`) REFERENCES `personas` (`dni`) ON DELETE CASCADE ON UPDATE CASCADE',
  'SELECT "FK hc->personas ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- pagos: FK persona_id -> personas(dni)
SET @fk_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'pagos' AND CONSTRAINT_NAME = 'fk_pg_persona');
SET @sql = IF(@fk_exists = 0,
  'ALTER TABLE `pagos` ADD CONSTRAINT `fk_pg_persona` FOREIGN KEY (`persona_id`) REFERENCES `personas` (`dni`) ON DELETE CASCADE ON UPDATE CASCADE',
  'SELECT "FK pg->personas ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- notas_clinicas: FK paciente_id -> personas(dni)
SET @fk_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'notas_clinicas' AND CONSTRAINT_NAME = 'fk_nc_persona');
SET @sql = IF(@fk_exists = 0,
  'ALTER TABLE `notas_clinicas` ADD CONSTRAINT `fk_nc_persona` FOREIGN KEY (`paciente_id`) REFERENCES `personas` (`dni`) ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT "FK nc->personas ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ============================================================
-- PASO 11: Modificar historial_citas - agregar hora_cita
-- ============================================================

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'historial_citas' AND COLUMN_NAME = 'hora_cita');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `historial_citas` ADD COLUMN `hora_cita` time DEFAULT NULL AFTER `fecha_cita`',
  'SELECT "hora_cita ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ============================================================
-- PASO 12: Modificar pagos - agregar columnas de verificacion
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
-- PASO 13: Crear tabla notas_clinicas (si no existe)
--   paciente_id ya es VARCHAR(15) = dni
-- ============================================================
CREATE TABLE IF NOT EXISTS `notas_clinicas` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `cita_id` int(11) NOT NULL,
  `paciente_id` varchar(15) DEFAULT NULL,
  `terapeuta_id` int(11) DEFAULT NULL,
  `nota` text NOT NULL,
  `diagnostico` varchar(255) DEFAULT NULL,
  `fecha_creacion` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `cita_id` (`cita_id`),
  KEY `paciente_id` (`paciente_id`),
  KEY `terapeuta_id` (`terapeuta_id`),
  CONSTRAINT `notas_clinicas_ibfk_1` FOREIGN KEY (`cita_id`) REFERENCES `historial_citas` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_nc_persona` FOREIGN KEY (`paciente_id`) REFERENCES `personas` (`dni`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `notas_clinicas_ibfk_3` FOREIGN KEY (`terapeuta_id`) REFERENCES `terapeutas` (`ID`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================
-- PASO 14: Crear tabla horarios_medico (si no existe)
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
-- PASO 15: Crear tabla configuracion (si no existe)
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
-- PASO 16: Crear tabla opiniones (si no existe)
-- ============================================================
CREATE TABLE IF NOT EXISTS `opiniones` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `persona_id` varchar(15) DEFAULT NULL,
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
-- PASO 17: Ajustar AUTO_INCREMENTs
-- ============================================================
SET @max_id = (SELECT IFNULL(MAX(id), 0) FROM `usuarios`);
SET @sql = CONCAT('ALTER TABLE `usuarios` AUTO_INCREMENT = ', @max_id + 1);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @max_id = (SELECT IFNULL(MAX(id), 0) FROM `roles`);
SET @sql = CONCAT('ALTER TABLE `roles` AUTO_INCREMENT = ', @max_id + 1);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET FOREIGN_KEY_CHECKS = 1;

COMMIT;

-- ============================================================
-- VERIFICACION
-- ============================================================
SELECT 'MIGRACION COMPLETADA' AS resultado;
SHOW TABLES;
DESCRIBE `personas`;
DESCRIBE `usuarios`;
