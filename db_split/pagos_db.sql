-- ============================================================
-- pagos_db.sql
-- Base de datos de PAGOS
-- Servicio que la consume: pagos_service
-- FASE 1 - Separacion de bases (solo archivos SQL)
--
-- Tablas propias:
--   pagos                  (INSERTs con IDs actuales: 2,5,6,9)
--   paquetes_sesiones
--   paquete_sesiones_uso
--   configuracion          (INSERT con ID actual: 1 -> anio_inicio)
--
-- FK internas (FK real):
--   paquete_sesiones_uso.paquete_id -> paquetes_sesiones.id
--
-- Referencias externas (SIN FK, comentadas):
--   pagos.cita_id                -> historial_citas.id (moovacloud_citas). Sin FK.
--   pagos.paciente_id            -> pacientes.id (moovacloud_pacientes). Sin FK.
--   pagos.verificado_por         -> usuarios.id (moovacloud_auth). Sin FK.
--   paquetes_sesiones.paciente_id -> pacientes.id (moovacloud_pacientes). Sin FK.
--   paquetes_sesiones.servicio_id -> servicios.id (moovacloud_pacientes). Sin FK.
--   paquete_sesiones_uso.cita_id  -> historial_citas.id (moovacloud_citas). Sin FK.
--
-- Notas de FASE 1:
--   - Este archivo conserva las columnas de pasarela (datos_respuesta,
--     intentos_verificacion, comprobante_url) tal como estan en
--     moovacloud_db.sql (fuente de verdad). Cualquier decision de
--     limpieza de columnas es de otra fase.
--   - Los procedimientos que tocan tablas de otras bases se
--     conservan comentados y documentados como CROSS-DB
--     (pendientes de convertir en Fase 2).
--   - configuracion se ubica aqui por convencion (config de la
--     clinica asociada a pagos/estadisticas); revisable en revision.
-- ============================================================

CREATE DATABASE IF NOT EXISTS `moovacloud_pagos` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE `moovacloud_pagos`;

-- --------------------------------------------------------
--
-- Table structure for table `configuracion`
--

CREATE TABLE `configuracion` (
  `id` int(11) NOT NULL,
  `clave` varchar(50) NOT NULL,
  `valor` varchar(255) NOT NULL,
  `descripcion` text DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `configuracion`
--

INSERT INTO `configuracion` (`id`, `clave`, `valor`, `descripcion`) VALUES
(1, 'anio_inicio', '2023', 'Anio de inicio de actividades de la clinica');

-- --------------------------------------------------------
--
-- Table structure for table `pagos`
--

CREATE TABLE `pagos` (
  `id` int(11) NOT NULL,
  `cita_id` int(11) NOT NULL,
  `paciente_id` int(11) NOT NULL,
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
  `verificado_por` int(11) DEFAULT NULL,
  `notas` text DEFAULT NULL,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Ref. historial_citas (moovacloud_citas). Sin FK.
--   pagos.cita_id -> historial_citas.id
-- Ref. pacientes (moovacloud_pacientes). Sin FK.
--   pagos.paciente_id -> pacientes.id
-- Ref. usuarios (moovacloud_auth). Sin FK.
--   pagos.verificado_por -> usuarios.id

--
-- Dumping data for table `pagos`
--

INSERT INTO `pagos` (`id`, `cita_id`, `paciente_id`, `monto`, `metodo_pago`, `estado_pago`, `fecha_pago`, `referencia`, `transaccion_id`, `comprobante_url`, `datos_respuesta`, `intentos_verificacion`, `verificado_en`, `verificado_por`, `notas`, `creado_en`) VALUES
(2, 11, 6, 50.00, 'yape', 'pagado', '2026-08-20 23:47:45', NULL, NULL, NULL, NULL, 0, NULL, NULL, 'Anticipo 50% de la atencion', '2026-08-20 23:47:45'),
(5, 14, 6, 40.00, 'yape', 'pagado', '2026-08-21 00:06:17', '942154', NULL, NULL, NULL, 0, NULL, NULL, 'Anticipo 50% de la atencion', '2026-08-21 00:05:16'),
(6, 15, 6, 60.00, 'tarjeta', 'pendiente', NULL, NULL, NULL, NULL, NULL, 0, NULL, NULL, 'Anticipo 50% de la atencion', '2026-08-21 00:12:18'),
(9, 18, 11, 40.00, 'yape', 'pendiente', NULL, NULL, NULL, NULL, NULL, 0, NULL, NULL, 'Anticipo 50% de la atencion', '2026-08-25 23:21:37');

-- --------------------------------------------------------
--
-- Table structure for table `paquetes_sesiones`
--

CREATE TABLE `paquetes_sesiones` (
  `id` int(11) NOT NULL,
  `paciente_id` int(11) NOT NULL,
  `servicio_id` int(11) NOT NULL,
  `total_sesiones` int(11) NOT NULL,
  `sesiones_usadas` int(11) NOT NULL DEFAULT 0,
  `fecha_compra` date NOT NULL,
  `fecha_vencimiento` date DEFAULT NULL,
  `estado` enum('activo','agotado','vencido','cancelado') NOT NULL DEFAULT 'activo',
  `creado_en` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Ref. pacientes (moovacloud_pacientes). Sin FK.
--   paquetes_sesiones.paciente_id -> pacientes.id
-- Ref. servicios (moovacloud_pacientes). Sin FK.
--   paquetes_sesiones.servicio_id -> servicios.id

-- --------------------------------------------------------
--
-- Table structure for table `paquete_sesiones_uso`
--

CREATE TABLE `paquete_sesiones_uso` (
  `id` int(11) NOT NULL,
  `paquete_id` int(11) NOT NULL,
  `cita_id` int(11) NOT NULL,
  `fecha_uso` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Ref. historial_citas (moovacloud_citas). Sin FK.
--   paquete_sesiones_uso.cita_id -> historial_citas.id

--
-- Indexes for dumped tables
--

--
-- Indexes for table `configuracion`
--
ALTER TABLE `configuracion`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `clave` (`clave`);

--
-- Indexes for table `pagos`
--
ALTER TABLE `pagos`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_cita` (`cita_id`),
  ADD KEY `idx_estado` (`estado_pago`),
  ADD KEY `idx_fecha` (`fecha_pago`),
  ADD KEY `pagos_ibfk_2` (`paciente_id`),
  ADD KEY `fk_pg_verificado_por` (`verificado_por`);

--
-- Indexes for table `paquetes_sesiones`
--
ALTER TABLE `paquetes_sesiones`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_ps_paciente` (`paciente_id`),
  ADD KEY `idx_ps_servicio` (`servicio_id`),
  ADD KEY `idx_ps_estado` (`estado`);

--
-- Indexes for table `paquete_sesiones_uso`
--
ALTER TABLE `paquete_sesiones_uso`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_uso_cita` (`cita_id`),
  ADD KEY `idx_uso_paquete` (`paquete_id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `configuracion`
--
ALTER TABLE `configuracion`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- AUTO_INCREMENT for table `pagos`
--
ALTER TABLE `pagos`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=10;

--
-- AUTO_INCREMENT for table `paquetes_sesiones`
--
ALTER TABLE `paquetes_sesiones`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `paquete_sesiones_uso`
--
ALTER TABLE `paquete_sesiones_uso`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- Constraints for dumped tables (Solo FK internas; las referencias a
-- otras bases van como comentario)
--

--
-- Constraints for table `paquete_sesiones_uso`
--
ALTER TABLE `paquete_sesiones_uso`
  ADD CONSTRAINT `fk_uso_paquete` FOREIGN KEY (`paquete_id`) REFERENCES `paquetes_sesiones` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

-- --------------------------------------------------------
--
-- Procedimientos del dominio de pagos
--

DELIMITER $$

DROP PROCEDURE IF EXISTS `sp_guardar_referencia`$$
CREATE PROCEDURE `sp_guardar_referencia`(IN p_cita_id INT, IN p_cobro_id VARCHAR(100))
BEGIN
    UPDATE pagos SET referencia = p_cobro_id WHERE cita_id = p_cita_id;
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_pago`$$
CREATE PROCEDURE `sp_obtener_pago`(IN p_cita_id INT)
BEGIN
    SELECT * FROM pagos WHERE cita_id = p_cita_id;
END$$

DROP PROCEDURE IF EXISTS `sp_confirmar_pago`$$
CREATE PROCEDURE `sp_confirmar_pago`(
    IN p_cita_id INT, IN p_referencia VARCHAR(100),
    IN p_datos_respuesta TEXT, IN p_verificado_por INT
)
BEGIN
    IF p_verificado_por IS NOT NULL THEN
        UPDATE pagos
        SET estado_pago = 'pagado', fecha_pago = NOW(),
            referencia = COALESCE(p_referencia, referencia),
            transaccion_id = COALESCE(p_referencia, transaccion_id),
            datos_respuesta = COALESCE(p_datos_respuesta, datos_respuesta),
            verificado_en = NOW(), verificado_por = p_verificado_por
        WHERE cita_id = p_cita_id AND estado_pago = 'pendiente';
    ELSE
        UPDATE pagos
        SET estado_pago = 'pagado', fecha_pago = NOW(),
            referencia = COALESCE(p_referencia, referencia),
            transaccion_id = COALESCE(p_referencia, transaccion_id),
            datos_respuesta = COALESCE(p_datos_respuesta, datos_respuesta),
            verificado_en = NOW()
        WHERE cita_id = p_cita_id AND estado_pago = 'pendiente';
    END IF;
    SELECT ROW_COUNT() AS pagado;
END$$

DROP PROCEDURE IF EXISTS `sp_crear_pago_anticipo`$$
CREATE PROCEDURE `sp_crear_pago_anticipo`(
    IN p_cita_id INT, IN p_paciente_id INT, IN p_monto DECIMAL(10,2), IN p_metodo_pago VARCHAR(20)
)
BEGIN
    DECLARE v_id INT;
    SELECT id INTO v_id FROM pagos
    WHERE cita_id = p_cita_id AND estado_pago = 'pendiente'
    LIMIT 1;
    IF v_id IS NULL THEN
        INSERT INTO pagos (cita_id, paciente_id, monto, metodo_pago, estado_pago, notas)
        VALUES (p_cita_id, p_paciente_id, p_monto, p_metodo_pago, 'pendiente', 'Anticipo 50%');
        SET v_id = LAST_INSERT_ID();
    END IF;
    SELECT v_id AS id;
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_configuracion_anio`$$
CREATE PROCEDURE `sp_obtener_configuracion_anio`()
BEGIN
    SELECT valor FROM configuracion WHERE clave = 'anio_inicio';
END$$

-- --------------------------------------------------------
-- Procedimientos CROSS-DB de FASE 1 ELIMINADOS en FASE 2:
--   sp_obtener_pago_pendiente, sp_obtener_cita_para_confirmar
--   (hacian JOIN a historial_citas/pacientes/usuarios). Los datos de
--   la cita/paciente/terapeuta los resuelve ahora pagos_service via
--   citas_client/pacientes_client y se combinan en el servicio.
-- --------------------------------------------------------

--
-- sp_cancelar_pago_cita  |  LOCAL (FASE 2)
--   Marca cancelado el pago pendiente de una cita. Lo invoca
--   pagos_service (POST /api/pagos/<cita_id>/cancelar) cuando
--   citas_service cancela una cita.
--
DROP PROCEDURE IF EXISTS `sp_cancelar_pago_cita`$$
CREATE PROCEDURE `sp_cancelar_pago_cita`(IN p_cita_id INT)
BEGIN
    UPDATE pagos SET estado_pago = 'cancelado'
    WHERE cita_id = p_cita_id AND estado_pago = 'pendiente';
    SELECT ROW_COUNT() AS cancelados;
END$$

--
-- sp_listar_paquetes_paciente  |  LOCAL (FASE 2)
--   Paquetes de sesiones de un paciente. El nombre del servicio
--   (servicios vive en moovacloud_pacientes) se agrega en pagos_service
--   via pacientes_client (GET /api/servicios).
--
DROP PROCEDURE IF EXISTS `sp_listar_paquetes_paciente`$$
CREATE PROCEDURE `sp_listar_paquetes_paciente`(IN p_paciente_id INT)
BEGIN
    SELECT ps.*
    FROM paquetes_sesiones ps
    WHERE ps.paciente_id = p_paciente_id
    ORDER BY ps.fecha_compra DESC;
END$$

--
-- sp_crear_paquete  |  LOCAL (FASE 2)
--
DROP PROCEDURE IF EXISTS `sp_crear_paquete`$$
CREATE PROCEDURE `sp_crear_paquete`(
    IN p_paciente_id INT, IN p_servicio_id INT,
    IN p_total_sesiones INT, IN p_fecha_compra DATE, IN p_fecha_vencimiento DATE
)
BEGIN
    INSERT INTO paquetes_sesiones (paciente_id, servicio_id, total_sesiones, fecha_compra, fecha_vencimiento)
    VALUES (p_paciente_id, p_servicio_id, p_total_sesiones, p_fecha_compra, p_fecha_vencimiento);
    SELECT LAST_INSERT_ID() AS id;
END$$

--
-- sp_obtener_pagos_paciente  |  LOCAL (FASE 2)
--   Pagos de un paciente (para el historial mostrado en el detalle de
--   paciente servido por pacientes_service, que lo pide via HTTP).
--
DROP PROCEDURE IF EXISTS `sp_obtener_pagos_paciente`$$
CREATE PROCEDURE `sp_obtener_pagos_paciente`(IN p_paciente_id INT)
BEGIN
    SELECT * FROM pagos
    WHERE paciente_id = p_paciente_id
    ORDER BY creado_en DESC;
END$$

DELIMITER ;

-- ============================================================
-- FIN pagos_db.sql
-- ============================================================