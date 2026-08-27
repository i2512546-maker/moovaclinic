-- ============================================================
-- MOOVA Clinic - Esquema completo de base de datos
-- Base: moovacloud_db | Motor: MariaDB 11.4 | Charset: utf8mb4
-- ============================================================
-- Ejecutar en phpMyAdmin > SQL sobre moovacloud_db
-- Crea todas las tablas desde cero con datos iniciales.
-- ============================================================

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";
SET FOREIGN_KEY_CHECKS = 0;

USE `moovacloud_db`;

-- ============================================================
-- 1. especialidades (catalogo)
-- ============================================================
CREATE TABLE IF NOT EXISTS `especialidades` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) NOT NULL,
  `descripcion` text DEFAULT NULL,
  `activa` tinyint(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (`id`),
  UNIQUE KEY `nombre` (`nombre`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT IGNORE INTO `especialidades` (`id`, `nombre`, `descripcion`) VALUES
(1, 'Fisioterapia', 'Tratamiento de lesiones y enfermedades del sistema musculoesqueletico'),
(2, 'Terapia Ocupacional', 'Rehabilitacion para actividades de la vida diaria'),
(3, 'Fonoaudiologia', 'Trastornos del lenguaje, audicion y deglucion'),
(4, 'Kinesiologia', 'Ciencia del movimiento y rehabilitacion fisica'),
(5, 'Psicologia', 'Atencion psicologica y salud mental'),
(6, 'Rehabilitacion Cardiaca', 'Programa de recuperacion post-cardiopatia');

-- ============================================================
-- 2. terapeutas
-- ============================================================
CREATE TABLE IF NOT EXISTS `terapeutas` (
  `ID` int(11) NOT NULL AUTO_INCREMENT,
  `DNI` varchar(15) NOT NULL,
  `Nombre` varchar(100) NOT NULL,
  `especialidad_id` int(11) DEFAULT NULL,
  `Telefono` varchar(20) DEFAULT NULL,
  `precio` decimal(10,2) DEFAULT NULL,
  `activo` tinyint(1) NOT NULL DEFAULT 1,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp(),
  `actualizado_en` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`ID`),
  UNIQUE KEY `DNI` (`DNI`),
  KEY `especialidad_id` (`especialidad_id`),
  CONSTRAINT `fk_terapeutas_especialidad` FOREIGN KEY (`especialidad_id`)
    REFERENCES `especialidades` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================
-- 3. personas (pacientes) - dni como PK
-- ============================================================
CREATE TABLE IF NOT EXISTS `personas` (
  `dni` varchar(15) NOT NULL,
  `nombre` varchar(100) NOT NULL,
  `apellido` varchar(100) NOT NULL,
  `telefono` varchar(20) NOT NULL,
  `estado` enum('activo','inactivo') NOT NULL DEFAULT 'activo',
  `email` varchar(100) DEFAULT NULL,
  `fecha_nacimiento` date DEFAULT NULL,
  `sexo` enum('M','F','otro') DEFAULT NULL,
  `direccion` varchar(255) DEFAULT NULL,
  `seguro` varchar(100) DEFAULT NULL,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp(),
  `actualizado_en` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`dni`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================
-- 4. roles
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
-- 5. usuarios (tabla general de auth, sin terapeuta_id)
-- ============================================================
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
  CONSTRAINT `fk_usuarios_rol` FOREIGN KEY (`rol_id`)
    REFERENCES `roles` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT IGNORE INTO `usuarios` (`id`, `nombre`, `correo`, `clave`, `rol_id`, `activo`) VALUES
(1, 'Administrador', 'admin@moova.com', '$2b$12$76VElioTEpM77sjDETiOBugLR2/wgDEmx4qEHFteiJEYMro7NLMji', 1, 1),
(2, 'Administrador 2', 'admin2@moova.com', '$2b$12$7Niuc7pdsDgH4qN0zCkSaeswC1GHFZBiQLcziHTyjEprDD38f5Y7q', 1, 1),
(3, 'Administrador 3', 'admin3@moova.com', '$2b$12$HOa38jTCoZFY1rfpnseWa.WGznEhncrn6DYQBCfwES7z2IWrpqXYm', 1, 1),
(4, 'Dra.Becky', 'ander@gmail.com', '$2b$12$KNwxZqdQ8uOLXsNRsETZqe0XUfaw/inUTM2OrFnTlTWdix0yGBf4q', 2, 1),
(5, 'JORDY', 'villegasc@moova.com', '$2b$12$oK2pcSRBbQKk/RMudHXQe.t/a6f3gDq4Z1Ez6txrIaR9DL60qBm6u', 2, 1),
(6, 'Jeon', 'jeon@moova.com', '$2b$12$Ep1Zx9VGyUnJQFoPyzQQVO1Cz4HEI7EWVIrHNkJckYX8dOqvPISmW', 2, 1);

-- ============================================================
-- 6. historial_citas
-- ============================================================
CREATE TABLE IF NOT EXISTS `historial_citas` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `persona_id` varchar(15) NOT NULL,
  `terapeuta_id` int(11) NOT NULL,
  `fecha_cita` date NOT NULL,
  `hora_cita` time DEFAULT NULL,
  `descripcion` text DEFAULT NULL,
  `estado` enum('programada','confirmada','cancelada','completada','no_asistio')
    NOT NULL DEFAULT 'programada',
  `recordatorio_enviado` tinyint(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `idx_fecha_cita` (`fecha_cita`),
  UNIQUE KEY `uq_reserva` (`terapeuta_id`, `fecha_cita`, `hora_cita`),
  CONSTRAINT `fk_hc_persona` FOREIGN KEY (`persona_id`)
    REFERENCES `personas` (`dni`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_hc_terapeuta` FOREIGN KEY (`terapeuta_id`)
    REFERENCES `terapeutas` (`ID`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================
-- 7. pagos
-- ============================================================
CREATE TABLE IF NOT EXISTS `pagos` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `cita_id` int(11) NOT NULL,
  `persona_id` varchar(15) NOT NULL,
  `monto` decimal(10,2) NOT NULL,
  `metodo_pago` varchar(30) NOT NULL DEFAULT 'efectivo',
  `estado_pago` varchar(20) NOT NULL DEFAULT 'pendiente',
  `fecha_pago` datetime DEFAULT NULL,
  `referencia` varchar(100) DEFAULT NULL,
  `transaccion_id` varchar(100) DEFAULT NULL,
  `comprobante_url` varchar(255) DEFAULT NULL,
  `datos_respuesta` text DEFAULT NULL,
  `intentos_verificacion` int(11) NOT NULL DEFAULT 0,
  `verificado_en` datetime DEFAULT NULL,
  `notas` text DEFAULT NULL,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `cita_id` (`cita_id`),
  KEY `persona_id` (`persona_id`),
  CONSTRAINT `fk_pg_cita` FOREIGN KEY (`cita_id`)
    REFERENCES `historial_citas` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_pg_persona` FOREIGN KEY (`persona_id`)
    REFERENCES `personas` (`dni`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================
-- 8. notas_clinicas
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
  CONSTRAINT `fk_nc_cita` FOREIGN KEY (`cita_id`)
    REFERENCES `historial_citas` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_nc_persona` FOREIGN KEY (`paciente_id`)
    REFERENCES `personas` (`dni`) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT `fk_nc_terapeuta` FOREIGN KEY (`terapeuta_id`)
    REFERENCES `terapeutas` (`ID`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================
-- 9. horarios_medico
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
  CONSTRAINT `fk_hm_terapeuta` FOREIGN KEY (`terapeuta_id`)
    REFERENCES `terapeutas` (`ID`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================
-- 10. otp_verificaciones (SMS para modificar/cancelar citas)
-- ============================================================
CREATE TABLE IF NOT EXISTS `otp_verificaciones` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `dni` varchar(15) NOT NULL,
  `codigo` varchar(6) NOT NULL,
  `accion` varchar(20) NOT NULL COMMENT 'modificar | cancelar',
  `intentos` int(11) NOT NULL DEFAULT 0,
  `expira_en` datetime NOT NULL,
  `usado` tinyint(1) NOT NULL DEFAULT 0,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_dni_accion` (`dni`, `accion`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================
-- 11. servicios (catalogo)
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
-- 12. paquetes_sesiones
-- ============================================================
CREATE TABLE IF NOT EXISTS `paquetes_sesiones` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `paciente_id` varchar(15) NOT NULL,
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
    REFERENCES `personas` (`dni`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_ps_servicio` FOREIGN KEY (`servicio_id`)
    REFERENCES `servicios` (`id`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================
-- 13. evaluaciones_iniciales
-- ============================================================
CREATE TABLE IF NOT EXISTS `evaluaciones_iniciales` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `paciente_id` varchar(15) NOT NULL,
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
    REFERENCES `personas` (`dni`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_ei_terapeuta` FOREIGN KEY (`terapeuta_id`)
    REFERENCES `terapeutas` (`ID`) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================
-- 14. consentimientos
-- ============================================================
CREATE TABLE IF NOT EXISTS `consentimientos` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `paciente_id` varchar(15) NOT NULL,
  `tipo` varchar(50) NOT NULL COMMENT 'general, tratamiento, cirugia',
  `texto_version` varchar(50) NOT NULL COMMENT 'v1.0, v2.1',
  `aceptado_en` datetime NOT NULL DEFAULT current_timestamp(),
  `ip_origen` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_consent_paciente` (`paciente_id`),
  KEY `idx_consent_tipo` (`tipo`),
  CONSTRAINT `fk_consent_paciente` FOREIGN KEY (`paciente_id`)
    REFERENCES `personas` (`dni`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================
-- 15. configuracion
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
-- 16. opiniones
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
SET FOREIGN_KEY_CHECKS = 1;

SELECT 'SCHEMA COMPLETO CREADO' AS resultado;
SHOW TABLES;
