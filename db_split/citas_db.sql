-- ============================================================
-- citas_db.sql
-- Base de datos de CITAS
-- Servicio que la consume: citas_service
-- FASE 1 - Separacion de bases (solo archivos SQL)
--
-- Tablas propias (dominio de citas, activas):
--   historial_citas    (INSERTs con IDs actuales: 1,2,3,4,5,7,8,9,11,14,15,18)
--   otp_verificaciones (INSERTs con IDs actuales: 1..6)
--
-- FK internas:
--   (ninguna: todas las referencias de historial_citas apuntan a
--    tablas de otras bases, por eso van como comentario)
--
-- Referencias externas (SIN FK, comentadas):
--   historial_citas.paciente_id   -> pacientes.id (moovacloud_pacientes). Sin FK.
--   historial_citas.terapeuta_id  -> terapeutas.id (moovacloud_pacientes). Sin FK.
--   historial_citas.servicio_id   -> servicios.id (moovacloud_pacientes). Sin FK.
--
-- Notas de FASE 1:
--   - Se ELIMINARON de este archivo las tablas que no pertenecen al
--     dominio de citas, junto con su estructura, indices, FKs y
--     procedimientos asociados (listadas en el resumen de la fase).
--   - Trigger ELIMINADO de esta fase (CROSS-DB):
--       * trg_historial_completada (AFTER UPDATE sobre historial_citas):
--         escribia sobre paquetes_sesiones y paquete_sesiones_uso,
--         que ahora viven en moovacloud_pagos. Pendiente de recrear como
--         logica de Fase 2.
--   - Los procedimientos que tocan tablas de otras bases se
--     conservan comentados y documentados como CROSS-DB
--     (pendientes de convertir en Fase 2).
-- ============================================================

CREATE DATABASE IF NOT EXISTS `moovacloud_citas` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE `moovacloud_citas`;

-- --------------------------------------------------------
--
-- Table structure for table `historial_citas`
--

CREATE TABLE `historial_citas` (
  `id` int(11) NOT NULL,
  `paciente_id` int(11) NOT NULL,
  `terapeuta_id` int(11) NOT NULL,
  `servicio_id` int(11) DEFAULT NULL,
  `fecha_cita` date NOT NULL,
  `hora_cita` time DEFAULT NULL,
  `descripcion` text DEFAULT NULL,
  `estado` enum('programada','confirmada','cancelada','completada','no_asistio') NOT NULL DEFAULT 'programada',
  `recordatorio_enviado` tinyint(1) DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `historial_citas`
--

INSERT INTO `historial_citas` (`id`, `paciente_id`, `terapeuta_id`, `servicio_id`, `fecha_cita`, `hora_cita`, `descripcion`, `estado`, `recordatorio_enviado`) VALUES
(1, 1, 1, NULL, '2026-05-14', NULL, NULL, 'cancelada', 0),
(2, 1, 1, NULL, '2026-05-29', NULL, NULL, 'cancelada', 0),
(3, 1, 2, NULL, '2026-05-31', NULL, NULL, 'programada', 0),
(4, 1, 1, NULL, '2026-05-20', NULL, NULL, 'programada', 0),
(5, 2, 1, NULL, '2026-05-14', NULL, NULL, 'programada', 0),
(7, 1, 1, NULL, '2026-05-25', NULL, NULL, 'programada', 0),
(8, 3, 1, NULL, '2026-05-28', NULL, NULL, 'cancelada', 0),
(9, 4, 1, NULL, '2026-08-21', NULL, NULL, 'programada', 0),
(11, 6, 1, NULL, '2026-08-20', NULL, NULL, 'programada', 0),
(14, 6, 2, NULL, '2026-08-28', NULL, NULL, 'programada', 0),
(15, 6, 3, NULL, '2026-09-01', NULL, NULL, 'programada', 0),
(18, 11, 2, NULL, '2026-08-26', NULL, NULL, 'programada', 0);

-- --------------------------------------------------------
--
-- Table structure for table `otp_verificaciones`
--

CREATE TABLE `otp_verificaciones` (
  `id` int(11) NOT NULL,
  `dni` varchar(15) NOT NULL,
  `codigo` varchar(6) NOT NULL,
  `accion` varchar(20) NOT NULL,
  `intentos` int(11) NOT NULL DEFAULT 0,
  `expira_en` datetime NOT NULL,
  `usado` tinyint(1) NOT NULL DEFAULT 0,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `otp_verificaciones`
--

INSERT INTO `otp_verificaciones` (`id`, `dni`, `codigo`, `accion`, `intentos`, `expira_en`, `usado`, `creado_en`) VALUES
(1, '47896066', '786834', 'modificar', 0, '2026-05-11 23:05:27', 1, '2026-05-12 05:55:29'),
(2, '47896066', '950702', 'modificar', 0, '2026-05-11 23:05:28', 1, '2026-05-12 05:55:30'),
(3, '47896066', '219481', 'modificar', 0, '2026-05-11 23:12:33', 1, '2026-05-12 06:02:35'),
(4, '47896066', '501485', 'cancelar', 0, '2026-05-11 23:12:46', 1, '2026-05-12 06:02:48'),
(5, '47896066', '634665', 'modificar', 0, '2026-05-27 19:51:14', 1, '2026-05-27 21:41:16'),
(6, '47896066', '833874', 'cancelar', 0, '2026-05-27 19:52:34', 1, '2026-05-27 21:42:35');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `historial_citas`
--
ALTER TABLE `historial_citas`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_reserva` (`terapeuta_id`,`fecha_cita`,`hora_cita`),
  ADD KEY `persona_id` (`paciente_id`),
  ADD KEY `terapeuta_id` (`terapeuta_id`),
  ADD KEY `idx_fecha_cita` (`fecha_cita`),
  ADD KEY `fk_hc_servicio` (`servicio_id`);

--
-- Indexes for table `otp_verificaciones`
--
ALTER TABLE `otp_verificaciones`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_dni_accion` (`dni`,`accion`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `historial_citas`
--
ALTER TABLE `historial_citas`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=19;

--
-- AUTO_INCREMENT for table `otp_verificaciones`
--
ALTER TABLE `otp_verificaciones`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=7;

-- --------------------------------------------------------
-- Constraints (SIN FK real hacia otras bases, solo comentario)
--
-- Ref. pacientes (moovacloud_pacientes). Sin FK.
--   historial_citas.paciente_id  -> pacientes.id
-- Ref. terapeutas (moovacloud_pacientes). Sin FK.
--   historial_citas.terapeuta_id -> terapeutas.id
-- Ref. servicios (moovacloud_pacientes). Sin FK.
--   historial_citas.servicio_id  -> servicios.id
-- --------------------------------------------------------

-- NOTA FASE 1: el trigger `trg_historial_completada` (AFTER UPDATE
-- sobre historial_citas) fue ELIMINADO de este archivo porque es
-- CROSS-DB: escribia sobre paquetes_sesiones y paquete_sesiones_uso
-- (moovacloud_pagos). Se re-creara como logica interna en Fase 2.

-- --------------------------------------------------------
--
-- Procedimientos del dominio de citas
--

DELIMITER $$

DROP PROCEDURE IF EXISTS `sp_medico_disponible`$$
CREATE PROCEDURE `sp_medico_disponible`(IN p_medico_id INT, IN p_fecha DATETIME, IN p_excluir_cita_id INT)
BEGIN
    SELECT COUNT(*) AS n
    FROM historial_citas
    WHERE terapeuta_id = p_medico_id
      AND fecha_cita = p_fecha
      AND estado = 'programada'
      AND (p_excluir_cita_id IS NULL OR id <> p_excluir_cita_id);
END$$

DROP PROCEDURE IF EXISTS `sp_crear_cita`$$
CREATE PROCEDURE `sp_crear_cita`(
    IN p_paciente_id INT, IN p_terapeuta_id INT, IN p_servicio_id INT, IN p_fecha DATETIME
)
BEGIN
    INSERT INTO historial_citas (paciente_id, terapeuta_id, servicio_id, fecha_cita, estado)
    VALUES (p_paciente_id, p_terapeuta_id, p_servicio_id, p_fecha, 'programada');
    SELECT LAST_INSERT_ID() AS id;
END$$

DROP PROCEDURE IF EXISTS `sp_modificar_cita`$$
CREATE PROCEDURE `sp_modificar_cita`(IN p_cita_id INT, IN p_fecha DATETIME, IN p_medico_id INT)
BEGIN
    UPDATE historial_citas SET fecha_cita = p_fecha, terapeuta_id = p_medico_id
    WHERE id = p_cita_id AND estado = 'programada';
    SELECT ROW_COUNT() AS actualizadas;
END$$

DROP PROCEDURE IF EXISTS `sp_completar_cita`$$
CREATE PROCEDURE `sp_completar_cita`(IN p_historial_id INT, IN p_descripcion TEXT)
BEGIN
    UPDATE historial_citas SET descripcion = p_descripcion, estado = 'completada'
    WHERE id = p_historial_id;
END$$

DROP PROCEDURE IF EXISTS `sp_estadisticas_recuperados`$$
CREATE PROCEDURE `sp_estadisticas_recuperados`()
BEGIN
    SELECT COUNT(DISTINCT paciente_id) AS total FROM historial_citas WHERE estado = 'completada';
END$$

-- --------------------------------------------------------
-- Procedimientos OTP (dominio de citas: modificar/cancelar con OTP)
-- --------------------------------------------------------

DROP PROCEDURE IF EXISTS `sp_invalidar_otps_previos`$$
CREATE PROCEDURE `sp_invalidar_otps_previos`(IN p_dni VARCHAR(20), IN p_accion VARCHAR(20))
BEGIN
    UPDATE otp_verificaciones SET usado = 1 WHERE dni = p_dni AND accion = p_accion AND usado = 0;
END$$

DROP PROCEDURE IF EXISTS `sp_insertar_otp`$$
CREATE PROCEDURE `sp_insertar_otp`(
    IN p_dni VARCHAR(20), IN p_codigo VARCHAR(10), IN p_accion VARCHAR(20), IN p_expira_en DATETIME
)
BEGIN
    INSERT INTO otp_verificaciones (dni, codigo, accion, expira_en)
    VALUES (p_dni, p_codigo, p_accion, p_expira_en);
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_otp`$$
CREATE PROCEDURE `sp_obtener_otp`(IN p_dni VARCHAR(20), IN p_accion VARCHAR(20))
BEGIN
    SELECT * FROM otp_verificaciones
    WHERE dni = p_dni AND accion = p_accion AND usado = 0
    ORDER BY creado_en DESC LIMIT 1;
END$$

DROP PROCEDURE IF EXISTS `sp_incrementar_intentos_otp`$$
CREATE PROCEDURE `sp_incrementar_intentos_otp`(IN p_id INT)
BEGIN
    UPDATE otp_verificaciones SET intentos = intentos + 1 WHERE id = p_id;
END$$

DROP PROCEDURE IF EXISTS `sp_marcar_otp_usado`$$
CREATE PROCEDURE `sp_marcar_otp_usado`(IN p_id INT)
BEGIN
    UPDATE otp_verificaciones SET usado = 1 WHERE id = p_id;
END$$

-- --------------------------------------------------------
-- Procedimientos de consulta de citas (FASE 2: ahora locales;
-- los datos de pacientes/terapeutas se enriquecen vía HTTP en
-- citas_service -> pacientes_service/auth_service)
-- --------------------------------------------------------

--
-- sp_listar_citas  |  LOCAL (FASE 2)
--   El filtro por p_dni ya NO se puede resolver aqui (pacientes
--   vive en moovacloud_pacientes). Se conserva el parametro por compatibilidad
--   de firma; citas_service aplica el filtro por dni despues de
--   resolver el paciente via HTTP.
--   historial_id = alias del id para compatibilidad con el contrato
--   de interfaz.html (form guardar_descripcion).
--
DROP PROCEDURE IF EXISTS `sp_listar_citas`$$
CREATE PROCEDURE `sp_listar_citas`(
    IN p_estado VARCHAR(20), IN p_dni VARCHAR(20), IN p_fecha DATETIME, IN p_medico_id INT
)
BEGIN
    SELECT h.id, h.id AS historial_id, h.fecha_cita, h.hora_cita, h.estado,
           h.descripcion, h.paciente_id, h.terapeuta_id, h.servicio_id
    FROM historial_citas h
    WHERE h.estado = p_estado
      AND (p_fecha IS NULL OR h.fecha_cita >= p_fecha)
      AND (p_medico_id IS NULL OR h.terapeuta_id = p_medico_id)
    ORDER BY h.fecha_cita ASC;
END$$

--
-- sp_detalle_cita  |  LOCAL (FASE 2)
--   Nombre/telefono del paciente y terapeuta se agregan en
--   citas_service via pacientes_service.
--
DROP PROCEDURE IF EXISTS `sp_detalle_cita`$$
CREATE PROCEDURE `sp_detalle_cita`(IN p_cita_id INT)
BEGIN
    SELECT h.*, h.id AS historial_id
    FROM historial_citas h
    WHERE h.id = p_cita_id;
END$$

--
-- sp_cancelar_cita  |  LOCAL (FASE 2)
--   Solo actualiza historial_citas. El cambio de estado del pago
--   ('cancelado') se delega via HTTP a pagos_service
--   (POST /api/pagos/<cita_id>/cancelar).
--
DROP PROCEDURE IF EXISTS `sp_cancelar_cita`$$
CREATE PROCEDURE `sp_cancelar_cita`(IN p_cita_id INT)
BEGIN
    DECLARE v_afectadas INT DEFAULT 0;
    UPDATE historial_citas SET estado = 'cancelada'
    WHERE id = p_cita_id AND estado = 'programada';
    SET v_afectadas = ROW_COUNT();
    SELECT v_afectadas AS actualizadas;
END$$

--
-- sp_existe_cita_programada_paciente  |  LOCAL (FASE 2)
--   Verifica que un paciente (id resuelto via pacientes_service)
--   tenga al menos una cita programada. Reemplaza la logica que
--   hacia sp_obtener_telefono_otp (CROSS-DB).
--
DROP PROCEDURE IF EXISTS `sp_existe_cita_programada_paciente`$$
CREATE PROCEDURE `sp_existe_cita_programada_paciente`(IN p_paciente_id INT)
BEGIN
    SELECT 1 AS existe
    FROM historial_citas
    WHERE paciente_id = p_paciente_id AND estado = 'programada'
    LIMIT 1;
END$$

--
-- sp_listar_citas_paciente  |  LOCAL (FASE 2)
--   Historial de citas de un paciente (para el detalle de paciente
--   servido por pacientes_service, que enriquece terapeuta y pago).
--
DROP PROCEDURE IF EXISTS `sp_listar_citas_paciente`$$
CREATE PROCEDURE `sp_listar_citas_paciente`(IN p_paciente_id INT)
BEGIN
    SELECT id, id AS historial_id, fecha_cita, hora_cita, estado,
           descripcion, terapeuta_id, servicio_id
    FROM historial_citas
    WHERE paciente_id = p_paciente_id
    ORDER BY fecha_cita DESC;
END$$

--
-- sp_resumen_pacientes  |  LOCAL (FASE 2)
--   Conteo de citas y ultima cita por paciente (para que
--   pacientes_service enriquezca sp_listar_pacientes vía HTTP).
--
DROP PROCEDURE IF EXISTS `sp_resumen_pacientes`$$
CREATE PROCEDURE `sp_resumen_pacientes`()
BEGIN
    SELECT paciente_id, COUNT(*) AS total, MAX(fecha_cita) AS ultima
    FROM historial_citas
    GROUP BY paciente_id;
END$$

DELIMITER ;

-- ============================================================
-- FIN citas_db.sql
-- ============================================================