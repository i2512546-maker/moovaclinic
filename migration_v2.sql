-- ============================================================
-- MOOVA Clinic - Migracion v3 (funcional)
-- Base: moovacloud_db en Alwaysdata (MariaDB 11.4)
-- ============================================================
-- ESTE SCRIPT ES ADITIVO Y RETROCOMPATIBLE. No borra ni recrea
-- tablas con datos. Agrega columnas, tablas nuevas y un TRIGGER.
--
-- CAMBIOS NUEVOS (v3 funcional):
--   1. historial_citas.servicio_id  -> FK a servicios.id (para
--      descontar el paquete correcto al completar la cita).
--   2. TRIGGER (descuento automatico de sesiones) que al pasar
--      historial_citas.estado a 'completada' incrementa
--      sesiones_usadas del paquete activo del paciente y lo
--      marca 'agotado' si llega al total.
--   3. pagos.verificado_por (FK -> usuarios.id) para auditoria
--      de pago.
--   4. Tabla notificaciones (reemplaza flag recordatorio_enviado).
--   5. Tabla excepciones_horario (feriados/vacaciones de terapeutas).
--   6. Tabla paquete_sesiones_uso (registro de cada consumo).
--   7. Tabla logs_auditoria + FK a usuarios.id.
-- ============================================================
-- EJECUTAR: Copiar todo este archivo y pegarlo en phpMyAdmin > SQL
-- sobre moovacloud_db. Hacer backup con mysqldump ANTES.
-- ============================================================

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";
SET FOREIGN_KEY_CHECKS = 0;

USE `moovacloud_db`;

-- ============================================================
-- PARTE 1: historial_citas.servicio_id
--   Necesario para vincular cada cita al servicio, y asi
--   descontar del paquete de sesiones correcto.
--   Aditivo: la columna es nullable, no rompe inserciones
--   existentes que no la provean.
-- ============================================================

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'historial_citas'
    AND COLUMN_NAME = 'servicio_id');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `historial_citas` ADD COLUMN `servicio_id` int(11) DEFAULT NULL AFTER `terapeuta_id`',
  'SELECT "servicio_id ya existe en historial_citas"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- FK hacia servicios (solo si la columna se acaba de crear o ya existe y no tiene FK)
SET @fk_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'historial_citas'
    AND CONSTRAINT_NAME = 'fk_hc_servicio');
SET @sql = IF(@fk_exists = 0,
  'ALTER TABLE `historial_citas` ADD CONSTRAINT `fk_hc_servicio`
     FOREIGN KEY (`servicio_id`) REFERENCES `servicios` (`id`)
     ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT "fk_hc_servicio ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;


-- ============================================================
-- PARTE 2: TRIGGER de descuento automatico de sesiones
--   Cuando historial_citas.estado pasa a 'completada', busca el
--   paquete activo del paciente para ese servicio y:
--     - incrementa sesiones_usadas (sin superar total_sesiones)
--     - lo marca 'agotado' si sesiones_usadas == total_sesiones
--     - registra el consumo en paquete_sesiones_uso
--   NOTA: se dispara en la tabla historial_citas (nivel base de
--   datos), por lo que cubre cualquier servicio que la escriba.
-- ============================================================

-- Tabla de registro de consumos (debe existir antes del trigger)
CREATE TABLE IF NOT EXISTS `paquete_sesiones_uso` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `paquete_id` int(11) NOT NULL,
  `cita_id` int(11) NOT NULL,
  `fecha_uso` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_uso_cita` (`cita_id`),
  KEY `idx_uso_paquete` (`paquete_id`),
  CONSTRAINT `fk_uso_paquete` FOREIGN KEY (`paquete_id`)
    REFERENCES `paquetes_sesiones` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_uso_cita` FOREIGN KEY (`cita_id`)
    REFERENCES `historial_citas` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

DELIMITER $$

-- DROP TRIGGER IF EXISTS `trg_historial_completada`;
CREATE TRIGGER `trg_historial_completada`
AFTER UPDATE ON `historial_citas`
FOR EACH ROW
BEGIN
  -- Solo actua cuando la cita pasa a 'completada'
  IF NEW.estado = 'completada' AND OLD.estado <> 'completada' THEN

    -- Buscar un paquete activo del paciente para el servicio de esta cita.
    -- Si hay varios activos del mismo servicio, descuenta del mas antiguo
    -- (fecha_compra ASC) para agotarlos en orden.
    UPDATE `paquetes_sesiones` ps
    SET ps.`sesiones_usadas` = ps.`sesiones_usadas` + 1,
        ps.`estado` = IF(ps.`sesiones_usadas` + 1 >= ps.`total_sesiones`, 'agotado', ps.`estado`)
    WHERE ps.`id` = (
          SELECT p2.`id` FROM (
            SELECT pp.`id`
            FROM `paquetes_sesiones` pp
            WHERE pp.`paciente_id` = NEW.`paciente_id`
              AND pp.`servicio_id` = NEW.`servicio_id`
              AND pp.`estado` = 'activo'
              AND pp.`sesiones_usadas` < pp.`total_sesiones`
            ORDER BY pp.`fecha_compra` ASC
            LIMIT 1
          ) p2
    );

    -- Registrar el consumo (solo si efectivamente se encontro un paquete)
    INSERT INTO `paquete_sesiones_uso` (paquete_id, cita_id)
    SELECT pp.`id`, NEW.`id`
    FROM `paquetes_sesiones` pp
    WHERE pp.`paciente_id` = NEW.`paciente_id`
      AND pp.`servicio_id` = NEW.`servicio_id`
      AND pp.`estado` = 'activo'
    LIMIT 1
    ON DUPLICATE KEY UPDATE `paquete_id` = `paquete_id`;

  END IF;
END$$

DELIMITER ;


-- ============================================================
-- PARTE 3: pagos.verificado_por (auditoria de pago)
--   FK -> usuarios.id. Nullable (los pagos automaticos via
--   Yape/Plin/Niubiz no tienen un usuario que verifica).
--   pagos_service comparte la misma BD (moovacloud_db), por lo
--   que leer usuarios no es problema entre servicios.
-- ============================================================

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'pagos' AND COLUMN_NAME = 'verificado_por');
SET @sql = IF(@col_exists = 0,
  'ALTER TABLE `pagos` ADD COLUMN `verificado_por` int(11) DEFAULT NULL AFTER `verificado_en`',
  'SELECT "verificado_por ya existe en pagos"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @fk_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
  WHERE TABLE_SCHEMA = 'moovacloud_db' AND TABLE_NAME = 'pagos'
    AND CONSTRAINT_NAME = 'fk_pg_verificado_por');
SET @sql = IF(@fk_exists = 0,
  'ALTER TABLE `pagos` ADD CONSTRAINT `fk_pg_verificado_por`
     FOREIGN KEY (`verificado_por`) REFERENCES `usuarios` (`id`)
     ON DELETE SET NULL ON UPDATE CASCADE',
  'SELECT "fk_pg_verificado_por ya existe"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;


-- ============================================================
-- PARTE 4: Tabla notificaciones
--   Reemplaza el flag booleano recordatorio_enviado en
--   historial_citas; registra cada intento de notificacion.
-- ============================================================

CREATE TABLE IF NOT EXISTS `notificaciones` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `paciente_id` int(11) NOT NULL,
  `cita_id` int(11) DEFAULT NULL,
  `canal` enum('sms','whatsapp','email') NOT NULL,
  `tipo` varchar(50) NOT NULL COMMENT 'recordatorio, confirmacion, modificacion, cancelacion',
  `enviado_en` datetime NOT NULL DEFAULT current_timestamp(),
  `estado` enum('enviado','fallido','pendiente') NOT NULL DEFAULT 'pendiente',
  PRIMARY KEY (`id`),
  KEY `idx_not_paciente` (`paciente_id`),
  KEY `idx_not_cita` (`cita_id`),
  KEY `idx_not_estado` (`estado`),
  CONSTRAINT `fk_not_paciente` FOREIGN KEY (`paciente_id`)
    REFERENCES `pacientes` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_not_cita` FOREIGN KEY (`cita_id`)
    REFERENCES `historial_citas` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


-- ============================================================
-- PARTE 5: Tabla excepciones_horario
--   Feriados/vacaciones/indisponibilidad puntual sobre
--   horarios_medico. La disponibilidad debe excluir estas fechas.
-- ============================================================

CREATE TABLE IF NOT EXISTS `excepciones_horario` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `terapeuta_id` int(11) NOT NULL,
  `fecha` date NOT NULL,
  `motivo` varchar(255) DEFAULT NULL,
  `disponible` tinyint(1) NOT NULL DEFAULT 0 COMMENT '0=no disponible, 1=disponible',
  PRIMARY KEY (`id`),
  KEY `idx_exc_terapeuta` (`terapeuta_id`),
  KEY `idx_exc_fecha` (`fecha`),
  CONSTRAINT `fk_exc_terapeuta` FOREIGN KEY (`terapeuta_id`)
    REFERENCES `terapeutas` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;


-- ============================================================
-- PARTE 6: logs_auditoria + FK a usuarios.id
-- ============================================================

CREATE TABLE IF NOT EXISTS `logs_auditoria` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `usuario_id` int(11) DEFAULT NULL,
  `accion` varchar(100) NOT NULL COMMENT 'crear_cita, cancelar_cita, reprogramar_cita, marcar_pago, crear_usuario, desactivar_usuario',
  `tabla_afectada` varchar(50) DEFAULT NULL,
  `registro_id` int(11) DEFAULT NULL,
  `detalle` text DEFAULT NULL,
  `ip_origen` varchar(45) DEFAULT NULL,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_log_usuario` (`usuario_id`),
  KEY `idx_log_accion` (`accion`),
  KEY `idx_log_fecha` (`creado_en`),
  CONSTRAINT `fk_log_usuario` FOREIGN KEY (`usuario_id`)
    REFERENCES `usuarios` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Backfill: una fila de ejemplo si la tabla estaba vacia (opcional)
-- INSERT IGNORE INTO `logs_auditoria` (usuario_id, accion, tabla_afectada, detalle)
-- VALUES (NULL, 'migracion_v3', 'sistema', 'Tabla logs_auditoria creada');


-- ============================================================
-- PARTE 7: DIAGNOSTICO horarios (Punto 3 - solo lectura)
--   NOTA IMPORTANTE: el sistema de reservas actual NO usa
--   horarios_medico. La disponibilidad se calcula contando citas
--   programadas por terapeuta/fecha (diseño COUNT, intencional).
--   Por eso estas queries son SOLO diagnostico, NO bloquean nada.
-- ============================================================

-- 7.1 Terapeutas activos SIN ningun horario cargado en horarios_medico
--     (Diagnostico de lo incompleto; no afecta reservas hoy)
SELECT t.id, u.nombre, t.activo
FROM terapeutas t
JOIN usuarios u ON t.usuario_id = u.id
WHERE t.activo = 1
  AND NOT EXISTS (
      SELECT 1 FROM horarios_medico hm WHERE hm.terapeuta_id = t.id
  );

-- 7.2 Terapeutas activos y cuantos dias de la semana tienen horario
SELECT t.id, u.nombre, COUNT(hm.id) AS dias_con_horario
FROM terapeutas t
JOIN usuarios u ON t.usuario_id = u.id
LEFT JOIN horarios_medico hm ON hm.terapeuta_id = t.id AND hm.activo = 1
WHERE t.activo = 1
GROUP BY t.id, u.nombre
ORDER BY dias_con_horario ASC;

-- 7.3 INSERT template para completar horarios faltantes
--     (solo si decides mantener la tabla sincronizada; recorda que
--      el codigo no la lee hoy)
INSERT INTO horarios_medico (terapeuta_id, dia_semana, hora_inicio, hora_fin, duracion_min, activo) VALUES
(2, 0, '08:00:00', '13:00:00', 30, 1),   -- terapeuta 2, lunes
(2, 1, '08:00:00', '13:00:00', 30, 1),   -- terapeuta 2, martes
(2, 2, '08:00:00', '13:00:00', 30, 1),   -- terapeuta 2, miercoles
(3, 0, '14:00:00', '18:00:00', 30, 1),   -- terapeuta 3, lunes
(3, 3, '14:00:00', '18:00:00', 30, 1);   -- terapeuta 3, jueves


-- ============================================================
-- VERIFICACION FINAL
-- ============================================================

SET FOREIGN_KEY_CHECKS = 1;

SELECT 'MIGRACION V3 (funcional) COMPLETADA' AS resultado;

DESCRIBE `historial_citas`;
DESCRIBE `pagos`;
SHOW TABLES;
