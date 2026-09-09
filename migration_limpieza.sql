-- ============================================================
-- MOOVA Clinic - Script de Limpieza y Optimización Final
-- Elimina tablas y columnas innecesarias (paquetes, excepciones,
-- base de auditoría secundaria pesada, metadatos y pasarelas complejas)
-- y consolida una tabla limpia de auditoría ligera.
-- ============================================================

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";
SET FOREIGN_KEY_CHECKS = 0;

-- 1. Eliminar tablas empresariales/complejas innecesarias para la clínica inicial
DROP TABLE IF EXISTS `paquete_sesiones_uso`;
DROP TABLE IF EXISTS `paquetes_sesiones`;
DROP TABLE IF EXISTS `excepciones_horario`;
DROP TABLE IF EXISTS `log_metadata`;
DROP TABLE IF EXISTS `audit_queues`;
DROP TABLE IF EXISTS `alertas_sistema`;
DROP TABLE IF EXISTS `audit_admins`;

-- Opcional: Si deseas eliminar por completo la BD de auditoría secundaria pesada:
-- DROP DATABASE IF EXISTS `moovacloud_auditoria`;

-- 2. Limpiar columnas innecesarias en la tabla PACIENTES (ej: seguro)
ALTER TABLE `pacientes` DROP COLUMN IF EXISTS `seguro`;

-- 3. Limpiar columnas innecesarias en la tabla PAGOS (pasarelas complejas)
ALTER TABLE `pagos` DROP COLUMN IF EXISTS `datos_respuesta`;
ALTER TABLE `pagos` DROP COLUMN IF EXISTS `intentos_verificacion`;
ALTER TABLE `pagos` DROP COLUMN IF EXISTS `comprobante_url`;

-- 4. Crear una tabla de auditoría ligera y funcional en la misma base de datos
DROP TABLE IF EXISTS `logs_auditoria`;
CREATE TABLE `logs_auditoria` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `usuario_id` int(11) DEFAULT NULL,
  `usuario_nombre` varchar(100) DEFAULT NULL,
  `accion` varchar(100) NOT NULL COMMENT 'LOGIN, CREAR_CITA, CAMBIAR_CLAVE, PAGAR_CITA',
  `detalles` text DEFAULT NULL,
  `ip_origen` varchar(45) DEFAULT NULL,
  `fecha_creacion` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_logs_usuario` (`usuario_id`),
  KEY `idx_logs_fecha` (`fecha_creacion`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='Auditoría ligera de eventos clave';

SET FOREIGN_KEY_CHECKS = 1;
COMMIT;
