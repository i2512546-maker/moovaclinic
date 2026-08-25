-- ============================================================
-- MOOVA Clinic - Migración de base de datos
-- Base original: moovacloud_db (producción)
-- Fecha: 2026-08-25
-- Cambios:
--   1. ELIMINAR tabla admins (migrar a usuarios)
--   2. CREAR tabla roles
--   3. CREAR tabla usuarios (unifica admins + terapeutas auth)
--   4. MODIFICAR terapeutas (quitar Correo/Clave, agregar campos)
--   5. MODIFICAR personas (agregar estado, email, timestamps)
--   6. MODIFICAR pagos (agregar campos de verificación)
-- ============================================================

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

-- -----------------------------------------------------------
-- PASO 0: Eliminar foreign keys que dependen de terapeutas
-- (para poder modificar esa tabla sin errores)
-- -----------------------------------------------------------

ALTER TABLE `historial_citas`
  DROP FOREIGN KEY IF EXISTS `historial_citas_ibfk_2`;

ALTER TABLE `horarios_medico`
  DROP FOREIGN KEY IF EXISTS `horarios_medico_ibfk_1`;

ALTER TABLE `notas_clinicas`
  DROP FOREIGN KEY IF EXISTS `notas_clinicas_ibfk_3`;

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

-- Primero agregar especialidad_id como nullable
ALTER TABLE `terapeutas`
  ADD COLUMN `especialidad_id` int(11) DEFAULT NULL AFTER `Especialidad`,
  ADD COLUMN `activo` tinyint(1) NOT NULL DEFAULT 1 AFTER `precio`,
  ADD COLUMN `creado_en` datetime NOT NULL DEFAULT current_timestamp() AFTER `activo`,
  ADD COLUMN `actualizado_en` datetime DEFAULT NULL ON UPDATE current_timestamp() AFTER `creado_en`;

-- Mapear especialidad texto → especialidad_id
UPDATE `terapeutas` SET `especialidad_id` = 1 WHERE `Especialidad` = 'Muscular';
UPDATE `terapeutas` SET `especialidad_id` = 6 WHERE `Especialidad` = 'Cardiorrespiratoria';
-- Villegas no tiene especialidad conocida, queda NULL

-- Agregar FK de especialidad_id
ALTER TABLE `terapeutas`
  ADD CONSTRAINT `fk_terapeutas_especialidad`
  FOREIGN KEY (`especialidad_id`) REFERENCES `especialidades` (`id`)
  ON DELETE SET NULL ON UPDATE CASCADE;

-- Eliminar Correo y Clave (ya están en usuarios)
ALTER TABLE `terapeutas`
  DROP COLUMN `Correo`,
  DROP COLUMN `Clave`;

-- Eliminar unique key de Correo (ya no existe)
-- (Se eliminó con la columna)

-- -----------------------------------------------------------
-- PASO 4: CREAR tabla usuarios
--   - Migrar admins (rol admin)
--   - Migrar terapeutas (rol terapeuta)
-- -----------------------------------------------------------

CREATE TABLE IF NOT EXISTS `usuarios` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) NOT NULL,
  `correo` varchar(100) NOT NULL,
  `clave` varchar(255) NOT NULL,
  `rol_id` int(11) NOT NULL,
  `terapeuta_id` int(11) DEFAULT NULL COMMENT 'FK a terapeutas, solo si rol=terapeuta',
  `activo` tinyint(1) NOT NULL DEFAULT 1,
  `ultimo_acceso` datetime DEFAULT NULL,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp(),
  `actualizado_en` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `correo` (`correo`),
  KEY `rol_id` (`rol_id`),
  KEY `terapeuta_id` (`terapeuta_id`),
  CONSTRAINT `fk_usuarios_rol` FOREIGN KEY (`rol_id`) REFERENCES `roles` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `fk_usuarios_terapeuta` FOREIGN KEY (`terapeuta_id`) REFERENCES `terapeutas` (`ID`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Migrar los 3 admins que existían (rol_id=1)
INSERT INTO `usuarios` (`nombre`, `correo`, `clave`, `rol_id`, `activo`) VALUES
('Administrador', 'admin@moova.com', '$2b$12$76VElioTEpM77sjDETiOBugLR2/wgDEmx4qEHFteiJEYMro7NLMji', 1, 1),
('Administrador 2', 'admin2@moova.com', '$2b$12$7Niuc7pdsDgH4qN0zCkSaeswC1GHFZBiQLcziHTyjEprDD38f5Y7q', 1, 1),
('Administrador 3', 'admin3@moova.com', '$2b$12$HOa38jTCoZFY1rfpnseWa.WGznEhncrn6DYQBCfwES7z2IWrpqXYm', 1, 1);

-- Migrar terapeutas existentes (rol_id=2)
-- Dra.Becky → ID=1, JORDY → ID=2, Jeon → ID=3
INSERT INTO `usuarios` (`nombre`, `correo`, `clave`, `rol_id`, `terapeuta_id`, `activo`) VALUES
('Dra.Becky', 'ander@gmail.com', '$2b$12$KNwxZqdQ8uOLXsNRsETZqe0XUfaw/inUTM2OrFnTlTWdix0yGBf4q', 2, 1, 1),
('JORDY', 'villegasc@moova.com', '$2b$12$oK2pcSRBbQKk/RMudHXQe.t/a6f3gDq4Z1Ez6txrIaR9DL60qBm6u', 2, 2, 1),
('Jeon', 'jeon@moova.com', '$2b$12$Ep1Zx9VGyUnJQFoPyzQQVO1Cz4HEI7EWVIrHNkJckYX8dOqvPISmW', 2, 3, 1);

-- -----------------------------------------------------------
-- PASO 5: MODIFICAR personas
--   - Agregar estado (activo/inactivo)
--   - Agregar email
--   - Agregar timestamps
-- -----------------------------------------------------------

ALTER TABLE `personas`
  ADD COLUMN `estado` enum('activo','inactivo') NOT NULL DEFAULT 'activo' AFTER `telefono`,
  ADD COLUMN `email` varchar(100) DEFAULT NULL AFTER `estado`,
  ADD COLUMN `creado_en` datetime NOT NULL DEFAULT current_timestamp() AFTER `email`,
  ADD COLUMN `actualizado_en` datetime DEFAULT NULL ON UPDATE current_timestamp() AFTER `creado_en`;

-- -----------------------------------------------------------
-- PASO 6: MODIFICAR pagos
--   - Agregar transaccion_id
--   - Agregar comprobante_url
--   - Agregar datos_respuesta (JSON del proveedor)
--   - Agregar intentos_verificacion
--   - Agregar verificado_en
--   - Mejorar metodo_pago con ENUM
-- -----------------------------------------------------------

ALTER TABLE `pagos`
  ADD COLUMN `transaccion_id` varchar(100) DEFAULT NULL AFTER `referencia`,
  ADD COLUMN `comprobante_url` varchar(255) DEFAULT NULL AFTER `transaccion_id`,
  ADD COLUMN `datos_respuesta` text DEFAULT NULL COMMENT 'JSON con respuesta completa del proveedor' AFTER `comprobante_url`,
  ADD COLUMN `intentos_verificacion` int(11) NOT NULL DEFAULT 0 AFTER `datos_respuesta`,
  ADD COLUMN `verificado_en` datetime DEFAULT NULL AFTER `intentos_verificacion`;

-- Agregar constraint FK de personas en pagos (si no existe)
-- Ya existe pagos_ibfk_2

-- -----------------------------------------------------------
-- PASO 7: Restaurar foreign keys de historial_citas
-- -----------------------------------------------------------

ALTER TABLE `historial_citas`
  ADD CONSTRAINT `historial_citas_ibfk_2` FOREIGN KEY (`terapeuta_id`) REFERENCES `terapeutas` (`ID`);

ALTER TABLE `horarios_medico`
  ADD CONSTRAINT `horarios_medico_ibfk_1` FOREIGN KEY (`terapeuta_id`) REFERENCES `terapeutas` (`ID`) ON DELETE CASCADE;

ALTER TABLE `notas_clinicas`
  ADD CONSTRAINT `notas_clinicas_ibfk_3` FOREIGN KEY (`terapeuta_id`) REFERENCES `terapeutas` (`ID`) ON DELETE CASCADE;

-- -----------------------------------------------------------
-- ACTUALIZAR AUTO_INCREMENTs
-- -----------------------------------------------------------

ALTER TABLE `roles` AUTO_INCREMENT = 4;
ALTER TABLE `usuarios` AUTO_INCREMENT = 7;
ALTER TABLE `terapeutas` AUTO_INCREMENT = 4;
ALTER TABLE `personas` AUTO_INCREMENT = 11;
ALTER TABLE `pagos` AUTO_INCREMENT = 9;
ALTER TABLE `historial_citas` AUTO_INCREMENT = 18;
ALTER TABLE `horarios_medico` AUTO_INCREMENT = 19;
ALTER TABLE `otp_verificaciones` AUTO_INCREMENT = 7;

COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
