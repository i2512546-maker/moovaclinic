-- ============================================================
-- audit_db.sql
-- Base de datos de AUDITORIA
-- Servicio que la consumira: audit_service (fase posterior)
-- FASE 1 - Separacion de bases (solo archivos SQL)
--
-- Tablas propias:
--   logs_auditoria   (tabla ligera tomada de moovacloud_db.sql)
--                    -> sin filas actuales en el dump; se conserva
--                       estructura, indices y AUTO_INCREMENT
--
-- FK internas:
--   (ninguna)
--
-- Referencias externas (SIN FK, comentadas):
--   logs_auditoria.usuario_id -> usuarios.id (moovacloud_auth). Sin FK.
--   logs_auditoria.usuario_tipo -> dominio: admin|terapeuta|paciente|sistema
--
-- NOTA: Este archivo es SOLO la base de datos. No se crea ni modifica
--       codigo de audit-service (eso corresponde a otra fase).
--
-- NOTA IMPORTANTE: la version anterior del procedimiento
--       sp_insertar_log_auditoria usaba columnas que NO existen
--       (tabla_afectada, registro_id, detalle). Aqui se corrige para
--       usar las columnas reales de la tabla.
-- ============================================================

CREATE DATABASE IF NOT EXISTS `moovacloud_auditoria` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE `moovacloud_auditoria`;

-- --------------------------------------------------------
--
-- Table structure for table `logs_auditoria`
--

CREATE TABLE `logs_auditoria` (
  `id` int(11) NOT NULL,
  `usuario_tipo` varchar(20) NOT NULL,
  `usuario_id` int(11) DEFAULT NULL,
  `usuario_nombre` varchar(100) DEFAULT NULL,
  `accion` varchar(255) NOT NULL,
  `detalles` text DEFAULT NULL,
  `ip_origen` varchar(45) DEFAULT NULL,
  `fecha_creacion` timestamp NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- (La tabla no tiene filas actuales en el dump de origen:
--  no hay INSERTs que conservar.)

--
-- Indexes for table `logs_auditoria`
--
ALTER TABLE `logs_auditoria`
  ADD PRIMARY KEY (`id`);

--
-- AUTO_INCREMENT for table `logs_auditoria`
--
ALTER TABLE `logs_auditoria`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

-- --------------------------------------------------------
--
-- Procedimiento de insercion de logs
--

DELIMITER $$

DROP PROCEDURE IF EXISTS `sp_insertar_log_auditoria`$$
CREATE PROCEDURE `sp_insertar_log_auditoria`(
    IN p_usuario_id INT,
    IN p_usuario_tipo VARCHAR(20),
    IN p_usuario_nombre VARCHAR(100),
    IN p_accion VARCHAR(255),
    IN p_detalles TEXT,
    IN p_ip_origen VARCHAR(45)
)
BEGIN
    INSERT INTO logs_auditoria (usuario_id, usuario_tipo, usuario_nombre, accion, detalles, ip_origen)
    VALUES (p_usuario_id, p_usuario_tipo, p_usuario_nombre, p_accion, p_detalles, p_ip_origen);
END$$

-- --------------------------------------------------------
--
-- Consulta/lista de logs de auditoria (solo lectura)
-- Filtros opcionales por tipo de usuario, accion (parcial)
-- y rango de fechas. Ordena por fecha descendente y limita
-- a los ultimos 200 registros.
--

DROP PROCEDURE IF EXISTS `sp_listar_auditoria`$$
CREATE PROCEDURE `sp_listar_auditoria`(
    IN p_usuario_tipo VARCHAR(20),
    IN p_accion VARCHAR(255),
    IN p_fecha_desde DATETIME,
    IN p_fecha_hasta DATETIME
)
BEGIN
    SELECT id, usuario_tipo, usuario_id, usuario_nombre,
           accion, detalles, ip_origen, fecha_creacion
    FROM logs_auditoria
    WHERE (p_usuario_tipo IS NULL OR usuario_tipo = p_usuario_tipo)
      AND (p_accion IS NULL OR accion LIKE CONCAT('%', p_accion, '%'))
      AND (p_fecha_desde IS NULL OR fecha_creacion >= p_fecha_desde)
      AND (p_fecha_hasta IS NULL OR fecha_creacion <= p_fecha_hasta)
    ORDER BY fecha_creacion DESC
    LIMIT 200;
END$$

DELIMITER ;