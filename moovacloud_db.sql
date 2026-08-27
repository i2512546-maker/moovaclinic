-- ============================================================
-- MOOVA Clinic - Migracion de base de datos
-- Base: moovacloud_db en Alwaysdata
-- ============================================================
-- Cambios:
--   1. ELIMINAR tabla admins (migrar a usuarios)
--   2. CREAR tabla roles
--   3. CREAR tabla usuarios GENERAL (sin terapeuta_id)
--   4. MODIFICAR terapeutas (quitar Correo/Clave, agregar campos)
--   5. MODIFICAR personas (dni como PK, quitar id)
--   6. ACTUALIZAR FKs en historial_citas, pagos, notas_clinicas
--   7. MODIFICAR pagos (agregar campos de verificacion)
-- ============================================================

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";
SET FOREIGN_KEY_CHECKS = 0;

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

-- -----------------------------------------------------------
-- PASO 0: Eliminar foreign keys que dependen de personas y terapeutas
-- -----------------------------------------------------------

ALTER TABLE `historial_citas`
  DROP FOREIGN KEY IF EXISTS `historial_citas_ibfk_1`,
  DROP FOREIGN KEY IF EXISTS `historial_citas_ibfk_2`,
  DROP FOREIGN KEY IF EXISTS `fk_hc_persona`;

ALTER TABLE `pagos`
  DROP FOREIGN KEY IF EXISTS `pagos_ibfk_1`,
  DROP FOREIGN KEY IF EXISTS `fk_pg_persona`;

ALTER TABLE `notas_clinicas`
  DROP FOREIGN KEY IF EXISTS `notas_clinicas_ibfk_1`,
  DROP FOREIGN KEY IF EXISTS `notas_clinicas_ibfk_2`,
  DROP FOREIGN KEY IF EXISTS `fk_nc_persona`,
  DROP FOREIGN KEY IF EXISTS `notas_clinicas_ibfk_3`;

ALTER TABLE `horarios_medico`
  DROP FOREIGN KEY IF EXISTS `horarios_medico_ibfk_1`;

-- -----------------------------------------------------------
-- PASO 1: ELIMINAR tabla admins
-- -----------------------------------------------------------

DROP TABLE IF EXISTS `admins`;

-- -----------------------------------------------------------
-- PASO 2: CREAR tabla roles
-- -----------------------------------------------------------

CREATE TABLE IF NOT EXISTS `roles` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `nombre` varchar(50) NOT NULL,
  `descripcion` varchar(255) DEFAULT NULL,
  `permisos` text DEFAULT NULL COMMENT 'JSON con permisos del rol',
  `activo` tinyint(1) NOT NULL DEFAULT 1,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `nombre` (`nombre`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `roles` (`id`, `nombre`, `descripcion`, `permisos`) VALUES
(1, 'admin', 'Administrador del sistema', '{"citas":"all","terapeutas":"all","pagos":"all","config":"all","reportes":"all"}'),
(2, 'terapeuta', 'Terapeuta / medico', '{"citas":"own","notas":"own","horarios":"own"}'),
(3, 'recepcionista', 'Personal de recepcion', '{"citas":"all","pacientes":"all","pagos":"view"}');

-- -----------------------------------------------------------
-- PASO 3: MODIFICAR terapeutas
--   - Eliminar Correo y Clave (se migran a usuarios)
--   - Agregar especialidad_id FK, activo, timestamps
-- -----------------------------------------------------------

ALTER TABLE `terapeutas`
  ADD COLUMN `especialidad_id` int(11) DEFAULT NULL AFTER `Especialidad`,
  ADD COLUMN `activo` tinyint(1) NOT NULL DEFAULT 1 AFTER `precio`,
  ADD COLUMN `creado_en` datetime NOT NULL DEFAULT current_timestamp() AFTER `activo`,
  ADD COLUMN `actualizado_en` datetime DEFAULT NULL ON UPDATE current_timestamp() AFTER `creado_en`;

UPDATE `terapeutas` SET `especialidad_id` = 1 WHERE `Especialidad` = 'Muscular';
UPDATE `terapeutas` SET `especialidad_id` = 6 WHERE `Especialidad` = 'Cardiorrespiratoria';

ALTER TABLE `terapeutas`
  ADD CONSTRAINT `fk_terapeutas_especialidad`
  FOREIGN KEY (`especialidad_id`) REFERENCES `especialidades` (`id`)
  ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE `terapeutas`
  DROP COLUMN `Correo`,
  DROP COLUMN `Clave`;

-- -----------------------------------------------------------
-- PASO 4: CREAR tabla usuarios SIN terapeuta_id
--   Tabla general: solo auth + rol
-- -----------------------------------------------------------

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
  KEY `rol_id` (`rol_id`),
  CONSTRAINT `fk_usuarios_rol` FOREIGN KEY (`rol_id`) REFERENCES `roles` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO `usuarios` (`nombre`, `correo`, `clave`, `rol_id`, `activo`) VALUES
('Administrador', 'admin@moova.com', '$2b$12$76VElioTEpM77sjDETiOBugLR2/wgDEmx4qEHFteiJEYMro7NLMji', 1, 1),
('Administrador 2', 'admin2@moova.com', '$2b$12$7Niuc7pdsDgH4qN0zCkSaeswC1GHFZBiQLcziHTyjEprDD38f5Y7q', 1, 1),
('Administrador 3', 'admin3@moova.com', '$2b$12$HOa38jTCoZFY1rfpnseWa.WGznEhncrn6DYQBCfwES7z2IWrpqXYm', 1, 1),
('Dra.Becky', 'ander@gmail.com', '$2b$12$KNwxZqdQ8uOLXsNRsETZqe0XUfaw/inUTM2OrFnTlTWdix0yGBf4q', 2, 1),
('JORDY', 'villegasc@moova.com', '$2b$12$oK2pcSRBbQKk/RMudHXQe.t/a6f3gDq4Z1Ez6txrIaR9DL60qBm6u', 2, 1),
('Jeon', 'jeon@moova.com', '$2b$12$Ep1Zx9VGyUnJQFoPyzQQVO1Cz4HEI7EWVIrHNkJckYX8dOqvPISmW', 2, 1);

-- -----------------------------------------------------------
-- PASO 5: MODIFICAR personas - dni como PK
-- -----------------------------------------------------------

-- Agregar columnas nuevas primero
ALTER TABLE `personas`
  ADD COLUMN `estado` enum('activo','inactivo') NOT NULL DEFAULT 'activo' AFTER `telefono`,
  ADD COLUMN `email` varchar(100) DEFAULT NULL AFTER `estado`,
  ADD COLUMN `creado_en` datetime NOT NULL DEFAULT current_timestamp() AFTER `email`,
  ADD COLUMN `actualizado_en` datetime DEFAULT NULL ON UPDATE current_timestamp() AFTER `creado_en`;

-- Migrar datos persona_id a dni en tablas hijas
UPDATE `historial_citas` h
  INNER JOIN `personas` p ON h.persona_id = p.id
  SET h.persona_id = p.dni;

UPDATE `pagos` pg
  INNER JOIN `personas` p ON pg.persona_id = p.id
  SET pg.persona_id = p.dni;

UPDATE `notas_clinicas` nc
  INNER JOIN `personas` p ON nc.paciente_id = p.id
  SET nc.paciente_id = p.dni;

-- Cambiar tipo de columna persona_id a VARCHAR
ALTER TABLE `historial_citas` MODIFY COLUMN `persona_id` varchar(15) NOT NULL;
ALTER TABLE `pagos` MODIFY COLUMN `persona_id` varchar(15) NOT NULL;
ALTER TABLE `notas_clinicas` MODIFY COLUMN `paciente_id` varchar(15) DEFAULT NULL;

-- Eliminar PK vieja (id) y hacer dni la PK
ALTER TABLE `personas` DROP PRIMARY KEY, DROP INDEX `dni`;
ALTER TABLE `personas` DROP COLUMN `id`;
ALTER TABLE `personas` ADD PRIMARY KEY (`dni`);

-- -----------------------------------------------------------
-- PASO 6: MODIFICAR pagos
-- -----------------------------------------------------------

ALTER TABLE `pagos`
  ADD COLUMN `transaccion_id` varchar(100) DEFAULT NULL AFTER `referencia`,
  ADD COLUMN `comprobante_url` varchar(255) DEFAULT NULL AFTER `transaccion_id`,
  ADD COLUMN `datos_respuesta` text DEFAULT NULL COMMENT 'JSON con respuesta completa del proveedor' AFTER `comprobante_url`,
  ADD COLUMN `intentos_verificacion` int(11) NOT NULL DEFAULT 0 AFTER `datos_respuesta`,
  ADD COLUMN `verificado_en` datetime DEFAULT NULL AFTER `intentos_verificacion`;

-- -----------------------------------------------------------
-- PASO 7: Restaurar foreign keys actualizadas
-- -----------------------------------------------------------

-- historial_citas: persona_id ahora es dni
ALTER TABLE `historial_citas`
  ADD CONSTRAINT `fk_hc_persona` FOREIGN KEY (`persona_id`) REFERENCES `personas` (`dni`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_hc_terapeuta` FOREIGN KEY (`terapeuta_id`) REFERENCES `terapeutas` (`ID`);

-- pagos: persona_id ahora es dni
ALTER TABLE `pagos`
  ADD CONSTRAINT `fk_pg_persona` FOREIGN KEY (`persona_id`) REFERENCES `personas` (`dni`) ON DELETE CASCADE ON UPDATE CASCADE;

-- notas_clinicas: paciente_id ahora es dni
ALTER TABLE `notas_clinicas`
  ADD CONSTRAINT `notas_clinicas_ibfk_1` FOREIGN KEY (`cita_id`) REFERENCES `historial_citas` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `fk_nc_persona` FOREIGN KEY (`paciente_id`) REFERENCES `personas` (`dni`) ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT `notas_clinicas_ibfk_3` FOREIGN KEY (`terapeuta_id`) REFERENCES `terapeutas` (`ID`) ON DELETE SET NULL;

-- horarios_medico
ALTER TABLE `horarios_medico`
  ADD CONSTRAINT `horarios_medico_ibfk_1` FOREIGN KEY (`terapeuta_id`) REFERENCES `terapeutas` (`ID`) ON DELETE CASCADE;

-- -----------------------------------------------------------
-- ACTUALIZAR AUTO_INCREMENTs
-- -----------------------------------------------------------

ALTER TABLE `roles` AUTO_INCREMENT = 4;
ALTER TABLE `usuarios` AUTO_INCREMENT = 7;
ALTER TABLE `terapeutas` AUTO_INCREMENT = 4;

SET FOREIGN_KEY_CHECKS = 1;

COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
