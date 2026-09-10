-- ============================================================
-- auth_db.sql
-- Base de datos de AUTENTICACION / AUTORIZACION
-- Servicio que la consume: auth_service
-- FASE 1 - Separacion de bases (solo archivos SQL)
--
-- Tablas propias:
--   roles      (INSERTs con IDs actuales: 1, 2, 3)
--   usuarios   (INSERTs con IDs actuales: 1..6)
--
-- FK internas:
--   usuarios.rol_id -> roles.id  (fk_usuarios_rol, FK real)
--
-- Referencias externas (SIN FK, comentadas):
--   terapeutas.usuario_id -> usuarios.id (moovacloud_pacientes). Sin FK.
--
-- Notas de FASE 1:
--   - El almacen de auditoria y su procedimiento de insercion
--     (estructura + logica) quedaron fuera de este archivo:
--     ahora viven en audit_db.sql.
--   - Los procedimientos que tocan tablas de otras bases se
--     conservan comentados y documentados como CROSS-DB
--     (pendientes de convertir en Fase 2).
-- ============================================================

CREATE DATABASE IF NOT EXISTS `moovacloud_auth` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE `moovacloud_auth`;

-- --------------------------------------------------------
--
-- Table structure for table `roles`
--

CREATE TABLE `roles` (
  `id` int(11) NOT NULL,
  `nombre` varchar(50) NOT NULL,
  `descripcion` varchar(255) DEFAULT NULL,
  `permisos` text DEFAULT NULL,
  `activo` tinyint(1) NOT NULL DEFAULT 1,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `roles`
--

INSERT INTO `roles` (`id`, `nombre`, `descripcion`, `permisos`, `activo`, `creado_en`) VALUES
(1, 'admin', 'Administrador del sistema', '{\"citas\":\"all\",\"terapeutas\":\"all\",\"pagos\":\"all\",\"config\":\"all\",\"reportes\":\"all\"}', 1, '2026-08-25 08:34:08'),
(2, 'terapeuta', 'Terapeuta / medico', '{\"citas\":\"own\",\"notas\":\"own\",\"horarios\":\"own\"}', 1, '2026-08-25 08:34:08'),
(3, 'recepcionista', 'Personal de recepcion', '{\"citas\":\"all\",\"pacientes\":\"all\",\"pagos\":\"view\"}', 1, '2026-08-25 08:34:08');

-- --------------------------------------------------------
--
-- Table structure for table `usuarios`
--

CREATE TABLE `usuarios` (
  `id` int(11) NOT NULL,
  `nombre` varchar(100) NOT NULL,
  `correo` varchar(100) NOT NULL,
  `telefono` varchar(20) DEFAULT NULL,
  `clave` varchar(255) NOT NULL,
  `rol_id` int(11) NOT NULL,
  `activo` tinyint(1) NOT NULL DEFAULT 1,
  `ultimo_acceso` datetime DEFAULT NULL,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp(),
  `actualizado_en` datetime DEFAULT NULL ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `usuarios`
--

INSERT INTO `usuarios` (`id`, `nombre`, `correo`, `telefono`, `clave`, `rol_id`, `activo`, `ultimo_acceso`, `creado_en`, `actualizado_en`) VALUES
(1, 'Dra.Becky', 'Dra.Becky@moova.com', NULL, '$2b$12$KNwxZqdQ8uOLXsNRsETZqe0XUfaw/inUTM2OrFnTlTWdix0yGBf4q', 2, 1, NULL, '2026-08-25 08:34:09', NULL),
(2, 'JORDY', 'villegasc@moova.com', NULL, '$2b$12$oK2pcSRBbQKk/RMudHXQe.t/a6f3gDq4Z1Ez6txrIaR9DL60qBm6u', 2, 1, NULL, '2026-08-25 08:34:09', NULL),
(3, 'Jeon', 'jeon@moova.com', NULL, '$2b$12$Ep1Zx9VGyUnJQFoPyzQQVO1Cz4HEI7EWVIrHNkJckYX8dOqvPISmW', 2, 1, NULL, '2026-08-25 08:34:09', NULL),
(4, '', 'admin@moova.com', NULL, '$2b$12$vE9D1TPN.Srns8GyK47/UOO3rHzKmFUSkqPAro8NZtvkm17Vm7TKK', 1, 1, '2026-09-09 03:30:17', '2026-08-25 08:47:48', '2026-09-09 03:30:17'),
(5, '', 'admin2@moova.com', NULL, '$2b$12$vow9xYULbf6gzev6IAEdV.OecRqzGIA8c4bojCP.mnrm8lSCcYefa', 1, 1, '2026-09-08 22:57:31', '2026-08-25 08:47:48', '2026-09-08 22:57:31'),
(6, '', 'admin3@moova.com', NULL, '$2b$12$ZmaTaKrph1OjLP/yNo.6Bu5p1FHIE2nvfXE6Tj8DVifYXB65Kgq5K', 1, 1, NULL, '2026-08-25 08:47:48', '2026-09-08 06:39:13');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `roles`
--
ALTER TABLE `roles`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `nombre` (`nombre`);

--
-- Indexes for table `usuarios`
--
ALTER TABLE `usuarios`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `correo` (`correo`),
  ADD KEY `rol_id` (`rol_id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `roles`
--
ALTER TABLE `roles`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- AUTO_INCREMENT for table `usuarios`
--
ALTER TABLE `usuarios`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=8;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `usuarios`
--
ALTER TABLE `usuarios`
  ADD CONSTRAINT `fk_usuarios_rol` FOREIGN KEY (`rol_id`) REFERENCES `roles` (`id`) ON UPDATE CASCADE;

-- --------------------------------------------------------
--
-- Procedimientos de autenticacion / autorizacion (internos de moovacloud_auth)
--

DELIMITER $$

DROP PROCEDURE IF EXISTS `sp_login`$$
CREATE PROCEDURE `sp_login`(IN p_correo VARCHAR(120))
BEGIN
    SELECT u.*, r.nombre AS rol_nombre
    FROM usuarios u
    JOIN roles r ON u.rol_id = r.id
    WHERE u.correo = p_correo AND u.activo = 1;
END$$

DROP PROCEDURE IF EXISTS `sp_actualizar_ultimo_acceso`$$
CREATE PROCEDURE `sp_actualizar_ultimo_acceso`(IN p_id INT)
BEGIN
    UPDATE usuarios SET ultimo_acceso = NOW() WHERE id = p_id;
END$$

DROP PROCEDURE IF EXISTS `sp_listar_usuarios`$$
CREATE PROCEDURE `sp_listar_usuarios`()
BEGIN
    SELECT u.id, u.nombre, u.correo, r.nombre AS rol, u.activo, u.ultimo_acceso
    FROM usuarios u
    JOIN roles r ON u.rol_id = r.id
    ORDER BY r.nombre, u.nombre;
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_rol_id`$$
CREATE PROCEDURE `sp_obtener_rol_id`(IN p_nombre VARCHAR(50))
BEGIN
    SELECT id FROM roles WHERE nombre = p_nombre;
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_rol_id_terapeuta`$$
CREATE PROCEDURE `sp_obtener_rol_id_terapeuta`()
BEGIN
    SELECT id FROM roles WHERE nombre = 'terapeuta';
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_usuario_por_correo`$$
CREATE PROCEDURE `sp_obtener_usuario_por_correo`(IN p_correo VARCHAR(120))
BEGIN
    SELECT id FROM usuarios WHERE correo = p_correo;
END$$

DROP PROCEDURE IF EXISTS `sp_crear_usuario`$$
CREATE PROCEDURE `sp_crear_usuario`(
    IN p_nombre VARCHAR(100), IN p_correo VARCHAR(120),
    IN p_clave VARCHAR(255), IN p_rol_id INT
)
BEGIN
    INSERT INTO usuarios (nombre, correo, clave, rol_id) VALUES (p_nombre, p_correo, p_clave, p_rol_id);
    SELECT LAST_INSERT_ID() AS id;
END$$

DROP PROCEDURE IF EXISTS `sp_actualizar_usuario`$$
CREATE PROCEDURE `sp_actualizar_usuario`(
    IN p_usuario_id INT, IN p_nombre VARCHAR(100), IN p_correo VARCHAR(120),
    IN p_activo TINYINT, IN p_clave VARCHAR(255), IN p_rol_id INT
)
BEGIN
    UPDATE usuarios
    SET nombre = IF(p_nombre IS NOT NULL, p_nombre, nombre),
        correo = IF(p_correo IS NOT NULL, p_correo, correo),
        activo = IF(p_activo IS NOT NULL, p_activo, activo),
        clave = IF(p_clave IS NOT NULL, p_clave, clave),
        rol_id = IF(p_rol_id IS NOT NULL, p_rol_id, rol_id)
    WHERE id = p_usuario_id;
    SELECT ROW_COUNT() AS actualizados;
END$$

DROP PROCEDURE IF EXISTS `sp_listar_roles`$$
CREATE PROCEDURE `sp_listar_roles`()
BEGIN
    SELECT * FROM roles WHERE activo = 1 ORDER BY nombre;
END$$

DROP PROCEDURE IF EXISTS `sp_verificar_usuario`$$
CREATE PROCEDURE `sp_verificar_usuario`(IN p_usuario_id INT)
BEGIN
    SELECT u.id, u.nombre, u.rol_id, r.nombre AS rol
    FROM usuarios u
    JOIN roles r ON u.rol_id = r.id
    WHERE u.id = p_usuario_id AND u.activo = 1;
END$$

-- --------------------------------------------------------
-- Procedimientos de gestion de usuarios usados por el gateway/admin
-- (solo tocan usuarios / roles: internos de moovacloud_auth)
-- --------------------------------------------------------

DROP PROCEDURE IF EXISTS `sp_obtener_usuario_por_nombre`$$
CREATE PROCEDURE `sp_obtener_usuario_por_nombre`(IN p_nombre VARCHAR(100))
BEGIN
    SELECT u.id FROM usuarios u WHERE u.nombre = p_nombre;
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_usuario_por_id`$$
CREATE PROCEDURE `sp_obtener_usuario_por_id`(IN p_usuario_id INT)
BEGIN
    SELECT u.id, u.nombre, u.correo, u.telefono, u.rol_id, u.activo,
           r.nombre AS rol
    FROM usuarios u
    JOIN roles r ON u.rol_id = r.id
    WHERE u.id = p_usuario_id;
END$$

DROP PROCEDURE IF EXISTS `sp_crear_usuario_admin`$$
CREATE PROCEDURE `sp_crear_usuario_admin`(
    IN p_nombre VARCHAR(100), IN p_correo VARCHAR(120),
    IN p_telefono VARCHAR(20), IN p_clave VARCHAR(255), IN p_rol_id INT
)
BEGIN
    INSERT INTO usuarios (nombre, correo, telefono, clave, rol_id)
    VALUES (p_nombre, p_correo, p_telefono, p_clave, p_rol_id);
    SELECT LAST_INSERT_ID() AS id;
END$$

DROP PROCEDURE IF EXISTS `sp_set_usuario_activo`$$
CREATE PROCEDURE `sp_set_usuario_activo`(IN p_usuario_id INT, IN p_activo TINYINT)
BEGIN
    UPDATE usuarios SET activo = p_activo WHERE id = p_usuario_id;
END$$

DROP PROCEDURE IF EXISTS `sp_cambiar_clave_usuario`$$
CREATE PROCEDURE `sp_cambiar_clave_usuario`(IN p_usuario_id INT, IN p_clave VARCHAR(255))
BEGIN
    UPDATE usuarios SET clave = p_clave WHERE id = p_usuario_id;
END$$

DELIMITER ;

-- ============================================================
-- FIN auth_db.sql
-- ============================================================