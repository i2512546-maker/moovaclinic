-- =============================================================
-- MOOVA CLINIC - BASE DE DATOS UNIFICADA
-- Archivo maestro generado desde los SQL de db_split/ en main.
-- Ejecutar una sola vez en MySQL/MariaDB.
--
-- Crea: moovaclinic
-- Incluye tablas, datos iniciales, indices, claves y procedimientos
-- almacenados que estan definidos en los siete SQL originales.
--
-- IMPORTANTE:
-- 1) Hacer backup de las siete bases antiguas antes de migrar datos.
-- 2) Este archivo incluye los INSERT presentes en el repositorio;
--    no puede incluir registros nuevos que solo existan en hosting.
-- 3) Los SQL originales omitian algunas FK entre dominios. Se
--    conservan esas decisiones para evitar fallos por datos historicos.
--    Las consultas/procedimientos KPI se adaptan a tablas locales.
-- 4) Configurar DB_NAME=moovaclinic en el entorno de la aplicacion.
-- =============================================================

CREATE DATABASE IF NOT EXISTS `moovaclinic`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;
USE `moovaclinic`;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;



-- =============================================================
-- ORIGEN: db_split/auth_db.sql
-- =============================================================

-- ============================================================
-- sql
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
--     ahora viven en moovacloud_auditoria.sql.
--   - Los procedimientos que tocan tablas de otras bases se
--     conservan comentados y documentados como CROSS-DB
--     (pendientes de convertir en Fase 2).
-- ============================================================
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
    SELECT u.id, u.nombre, u.correo, u.telefono, r.nombre AS rol, u.activo, u.ultimo_acceso
    FROM usuarios u
    JOIN roles r ON u.rol_id = r.id
    ORDER BY r.nombre, u.nombre;
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_rol_id`$$
CREATE PROCEDURE `sp_obtener_rol_id`(IN p_nombre VARCHAR(50))
BEGIN
    SELECT id FROM roles WHERE nombre = p_nombre;
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

--
-- sp_actualizar_telefono_usuario  (FASE 3: aviso al terapeuta)
--   Solo toca la columna telefono. Va aparte de
--   sp_actualizar_usuario a proposito: cambiar la firma de un
--   procedimiento ya existente haria fallar por numero de
--   parametros si el codigo y la migracion llegan a produccion en
--   momentos distintos, y eso romperia editar usuarios.
--
--   NULLIF(p_telefono, ''): "" o NULL limpia el telefono (borrar),
--   cualquier otro valor lo sobrescribe. El formato lo valida el
--   codigo antes de llegar aqui (^9\d{8}$).
--
DROP PROCEDURE IF EXISTS `sp_actualizar_telefono_usuario`$$
CREATE PROCEDURE `sp_actualizar_telefono_usuario`(
    IN p_usuario_id INT, IN p_telefono VARCHAR(20)
)
BEGIN
    UPDATE usuarios
    SET telefono = NULLIF(p_telefono, '')
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

-- NOTA: cambiar clave y activar/desactivar usuario se hacen con
-- sp_actualizar_usuario (arriba), que ya cubre nombre, correo, activo,
-- clave y rol. Por eso no existen sp_set_usuario_activo ni
-- sp_cambiar_clave_usuario.

DELIMITER ;

-- ============================================================
-- FIN sql
-- ============================================================


-- =============================================================
-- ORIGEN: db_split/pacientes_db.sql
-- =============================================================

-- ============================================================
-- pacientes_db.sql
-- Base de datos de PACIENTES
-- Servicio que la consume: pacientes_service
-- FASE 1 - Separacion de bases (solo archivos SQL)
--
-- Tablas propias:
--   pacientes             (INSERTs con IDs actuales: 1,2,3,4,6,11)
--   consentimientos
--   evaluaciones_iniciales
--   opiniones
--   especialidades        (INSERTs con IDs actuales: 1..6)
--   servicios             (INSERTs con IDs actuales: 1..4)
--   terapeutas            (INSERTs con IDs actuales: 1,2,3)
--
-- FK internas (FK real):
--   consentimientos.paciente_id      -> pacientes.id
--   evaluaciones_iniciales.paciente_id  -> pacientes.id
--   evaluaciones_iniciales.terapeuta_id -> terapeutas.id
--   opiniones.paciente_id            -> pacientes.id
--   terapeutas.especialidad_id       -> especialidades.id
--
-- Referencias externas (SIN FK, comentadas):
--   terapeutas.usuario_id  -> usuarios.id (moovacloud_auth). Sin FK.
--   (el resto de tablas de otras bases listadas en los
--    procedimientos CROSS-DB van documentadas alli)
--
-- Notas de FASE 1:
--   - Este archivo conserva la columna `seguro` de pacientes tal
--     como esta en moovacloud_db.sql (fuente de verdad). Cualquier
--     decision de limpieza de columnas es de otra fase.
--   - Los procedimientos que tocan tablas de otras bases se
--     conservan comentados y documentados como CROSS-DB
--     (pendientes de convertir en Fase 2).
-- ============================================================
-- --------------------------------------------------------
--
-- Table structure for table `pacientes`
--

CREATE TABLE `pacientes` (
  `id` int(11) NOT NULL,
  `nombre` varchar(100) NOT NULL,
  `apellido` varchar(100) NOT NULL,
  `dni` varchar(15) NOT NULL,
  `telefono` varchar(20) NOT NULL,
  `estado` enum('activo','inactivo') NOT NULL DEFAULT 'activo',
  `email` varchar(100) DEFAULT NULL,
  `fecha_nacimiento` date DEFAULT NULL,
  `sexo` enum('M','F','otro') DEFAULT NULL,
  `direccion` varchar(255) DEFAULT NULL,
  `seguro` varchar(100) DEFAULT NULL,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp(),
  `actualizado_en` datetime DEFAULT NULL ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `pacientes`
--

INSERT INTO `pacientes` (`id`, `nombre`, `apellido`, `dni`, `telefono`, `estado`, `email`, `fecha_nacimiento`, `sexo`, `direccion`, `seguro`, `creado_en`, `actualizado_en`) VALUES
(1, 'HULDA FEBE', 'VENTOSILLA GUTIERREZ', '47896066', '997010000', 'activo', NULL, NULL, NULL, NULL, NULL, '2026-08-25 08:34:09', NULL),
(2, 'LEONOR', 'CHAMBI CARI', '45154578', '997010000', 'activo', NULL, NULL, NULL, NULL, NULL, '2026-08-25 08:34:09', NULL),
(3, 'JORDY', 'JIMENEZ FLORES', '47845421', '997010000', 'activo', NULL, NULL, NULL, NULL, NULL, '2026-08-25 08:34:09', NULL),
(4, 'QUELYON AUDIET', 'SAUCEDO MORAN', '45674895', '986537295', 'activo', NULL, NULL, NULL, NULL, NULL, '2026-08-25 08:34:09', NULL),
(6, 'NOEL', 'BARRIOS ALFARO', '44587524', '947587444', 'activo', NULL, NULL, NULL, NULL, NULL, '2026-08-25 08:34:09', NULL),
(11, 'KATTIA MERLIZA', 'VILLANO ALIAGA', '48565955', '945785454', 'activo', NULL, NULL, NULL, NULL, NULL, '2026-08-25 23:21:36', NULL);

-- --------------------------------------------------------
--
-- Table structure for table `consentimientos`
--

CREATE TABLE `consentimientos` (
  `id` int(11) NOT NULL,
  `paciente_id` int(11) NOT NULL,
  `tipo` varchar(50) NOT NULL COMMENT 'general, tratamiento, cirugia',
  `texto_version` varchar(50) NOT NULL COMMENT 'v1.0, v2.1',
  `aceptado_en` datetime NOT NULL DEFAULT current_timestamp(),
  `ip_origen` varchar(45) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------
--
-- Table structure for table `evaluaciones_iniciales`
--

CREATE TABLE `evaluaciones_iniciales` (
  `id` int(11) NOT NULL,
  `paciente_id` int(11) NOT NULL,
  `terapeuta_id` int(11) NOT NULL,
  `motivo_consulta` text NOT NULL,
  `escala_dolor_eva` tinyint(1) DEFAULT NULL COMMENT 'EVA 0-10',
  `rango_movimiento` text DEFAULT NULL,
  `objetivos_terapeuticos` text DEFAULT NULL,
  `fecha_creacion` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------
--
-- Table structure for table `opiniones`
--

CREATE TABLE `opiniones` (
  `id` int(11) NOT NULL,
  `paciente_id` int(11) DEFAULT NULL,
  `nombre_paciente` varchar(100) NOT NULL,
  `calificacion` tinyint(1) NOT NULL,
  `comentario` text DEFAULT NULL,
  `visible` tinyint(1) NOT NULL DEFAULT 1,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------
--
-- Table structure for table `especialidades`
--

CREATE TABLE `especialidades` (
  `id` int(11) NOT NULL,
  `nombre` varchar(100) NOT NULL,
  `descripcion` text DEFAULT NULL,
  `activa` tinyint(1) NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `especialidades`
--

INSERT INTO `especialidades` (`id`, `nombre`, `descripcion`, `activa`) VALUES
(1, 'Fisioterapia', 'Tratamiento de lesiones y enfermedades del sistema musculoesqueletico', 1),
(2, 'Terapia Ocupacional', 'Rehabilitacion para realizar actividades de la vida diaria', 1),
(3, 'Fonoaudiologia', 'Trastornos del lenguaje, audicion y deglucion', 1),
(4, 'Kinesiologia', 'Ciencia del movimiento y rehabilitacion fisica', 1),
(5, 'Psicologia', 'Atencion psicologica y salud mental', 1),
(6, 'Rehabilitacion Cardiaca', 'Programa de recuperacion post-cardiopatia', 1);

-- --------------------------------------------------------
--
-- Table structure for table `servicios`
--

CREATE TABLE `servicios` (
  `id` int(11) NOT NULL,
  `nombre` varchar(100) NOT NULL,
  `descripcion` text DEFAULT NULL,
  `duracion_min` int(11) NOT NULL DEFAULT 60,
  `precio` decimal(10,2) NOT NULL DEFAULT 0.00,
  `activo` tinyint(1) NOT NULL DEFAULT 1,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `servicios`
--

INSERT INTO `servicios` (`id`, `nombre`, `descripcion`, `duracion_min`, `precio`, `activo`, `creado_en`) VALUES
(1, 'Sesion de Fisioterapia', 'Sesion individual de rehabilitacion fisica', 60, 80.00, 1, '2026-08-27 08:13:59'),
(2, 'Sesion de Terapia Cardiorrespiratoria', 'Rehabilitacion cardiorrespiratoria', 60, 100.00, 1, '2026-08-27 08:13:59'),
(3, 'Sesion de Terapia Muscular', 'Fortalecimiento y recuperacion muscular', 45, 70.00, 1, '2026-08-27 08:13:59'),
(4, 'Evaluacion Inicial', 'Evaluacion completa del paciente nuevo', 30, 50.00, 1, '2026-08-27 08:13:59');

-- --------------------------------------------------------
--
-- Table structure for table `terapeutas`
--

CREATE TABLE `terapeutas` (
  `id` int(11) NOT NULL,
  `usuario_id` int(11) NOT NULL,
  `especialidad_id` int(11) DEFAULT NULL,
  `precio` decimal(10,2) DEFAULT NULL,
  `activo` tinyint(1) NOT NULL DEFAULT 1,
  `creado_en` datetime NOT NULL DEFAULT current_timestamp(),
  `actualizado_en` datetime DEFAULT NULL ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Ref. usuarios (moovacloud_auth). Sin FK.
--   terapeutas.usuario_id -> usuarios.id

--
-- Dumping data for table `terapeutas`
--

INSERT INTO `terapeutas` (`id`, `usuario_id`, `especialidad_id`, `precio`, `activo`, `creado_en`, `actualizado_en`) VALUES
(1, 1, 1, 100.00, 1, '2026-08-25 08:34:08', '2026-08-27 11:37:47'),
(2, 2, NULL, 80.00, 1, '2026-08-25 08:34:08', '2026-08-27 11:37:47'),
(3, 3, 6, 120.00, 1, '2026-08-25 08:34:08', '2026-08-27 11:37:47');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `pacientes`
--
ALTER TABLE `pacientes`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `dni` (`dni`);

--
-- Indexes for table `consentimientos`
--
ALTER TABLE `consentimientos`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_consent_paciente` (`paciente_id`),
  ADD KEY `idx_consent_tipo` (`tipo`);

--
-- Indexes for table `evaluaciones_iniciales`
--
ALTER TABLE `evaluaciones_iniciales`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_ei_paciente` (`paciente_id`),
  ADD KEY `idx_ei_terapeuta` (`terapeuta_id`);

--
-- Indexes for table `opiniones`
--
ALTER TABLE `opiniones`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_calificacion` (`calificacion`),
  ADD KEY `idx_visible` (`visible`),
  ADD KEY `idx_opiniones_paciente` (`paciente_id`);

--
-- Indexes for table `especialidades`
--
ALTER TABLE `especialidades`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `nombre` (`nombre`);

--
-- Indexes for table `servicios`
--
ALTER TABLE `servicios`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_servicio_activo` (`activo`);

--
-- Indexes for table `terapeutas`
--
ALTER TABLE `terapeutas`
  ADD PRIMARY KEY (`id`),
  ADD KEY `fk_terapeutas_especialidad` (`especialidad_id`),
  ADD KEY `fk_terapeutas_usuario` (`usuario_id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `pacientes`
--
ALTER TABLE `pacientes`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=12;

--
-- AUTO_INCREMENT for table `consentimientos`
--
ALTER TABLE `consentimientos`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `evaluaciones_iniciales`
--
ALTER TABLE `evaluaciones_iniciales`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `opiniones`
--
ALTER TABLE `opiniones`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT for table `especialidades`
--
ALTER TABLE `especialidades`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=7;

--
-- AUTO_INCREMENT for table `servicios`
--
ALTER TABLE `servicios`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- AUTO_INCREMENT for table `terapeutas`
--
ALTER TABLE `terapeutas`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- Constraints for dumped tables (Solo FK internas; las referencias a
-- otras bases van como comentario)
--

--
-- Constraints for table `consentimientos`
--
ALTER TABLE `consentimientos`
  ADD CONSTRAINT `fk_consent_paciente` FOREIGN KEY (`paciente_id`) REFERENCES `pacientes` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `evaluaciones_iniciales`
--
ALTER TABLE `evaluaciones_iniciales`
  ADD CONSTRAINT `fk_ei_paciente` FOREIGN KEY (`paciente_id`) REFERENCES `pacientes` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_ei_terapeuta` FOREIGN KEY (`terapeuta_id`) REFERENCES `terapeutas` (`id`) ON UPDATE CASCADE;

--
-- Constraints for table `opiniones`
--
ALTER TABLE `opiniones`
  ADD CONSTRAINT `fk_opiniones_paciente` FOREIGN KEY (`paciente_id`) REFERENCES `pacientes` (`id`) ON DELETE SET NULL ON UPDATE CASCADE;

-- Ref. usuarios (moovacloud_auth). Sin FK (no se crea constraint).
--   terapeutas.usuario_id -> usuarios.id
--
-- Constraints for table `terapeutas`
--
ALTER TABLE `terapeutas`
  ADD CONSTRAINT `fk_terapeutas_especialidad` FOREIGN KEY (`especialidad_id`) REFERENCES `especialidades` (`id`) ON DELETE SET NULL ON UPDATE CASCADE;

-- --------------------------------------------------------
--
-- Procedimientos del dominio de pacientes
--

DELIMITER $$

DROP PROCEDURE IF EXISTS `sp_obtener_paciente_por_dni`$$
CREATE PROCEDURE `sp_obtener_paciente_por_dni`(IN p_dni VARCHAR(20))
BEGIN
    SELECT * FROM pacientes WHERE dni = p_dni;
END$$

DROP PROCEDURE IF EXISTS `sp_existe_paciente_por_dni`$$
CREATE PROCEDURE `sp_existe_paciente_por_dni`(IN p_dni VARCHAR(20))
BEGIN
    SELECT dni FROM pacientes WHERE dni = p_dni;
END$$

DROP PROCEDURE IF EXISTS `sp_crear_paciente`$$
CREATE PROCEDURE `sp_crear_paciente`(
    IN p_nombre VARCHAR(100), IN p_apellido VARCHAR(100),
    IN p_dni VARCHAR(20), IN p_telefono VARCHAR(20),
    IN p_email VARCHAR(120), IN p_fecha_nacimiento DATE,
    IN p_sexo VARCHAR(10), IN p_direccion VARCHAR(255), IN p_seguro VARCHAR(100)
)
BEGIN
    INSERT INTO pacientes (nombre, apellido, dni, telefono, email, fecha_nacimiento, sexo, direccion, seguro)
    VALUES (p_nombre, p_apellido, p_dni, p_telefono, p_email, p_fecha_nacimiento, p_sexo, p_direccion, p_seguro);
    SELECT LAST_INSERT_ID() AS id;
END$$

DROP PROCEDURE IF EXISTS `sp_actualizar_paciente`$$
CREATE PROCEDURE `sp_actualizar_paciente`(
    IN p_dni_actual VARCHAR(20),
    IN p_nombre VARCHAR(100), IN p_apellido VARCHAR(100),
    IN p_telefono VARCHAR(20), IN p_email VARCHAR(120),
    IN p_estado VARCHAR(20), IN p_fecha_nacimiento DATE,
    IN p_sexo VARCHAR(10), IN p_direccion VARCHAR(255),
    IN p_seguro VARCHAR(100), IN p_dni_nuevo VARCHAR(20)
)
BEGIN
    UPDATE pacientes
    SET nombre = IF(p_nombre IS NOT NULL, p_nombre, nombre),
        apellido = IF(p_apellido IS NOT NULL, p_apellido, apellido),
        telefono = IF(p_telefono IS NOT NULL, p_telefono, telefono),
        email = IF(p_email IS NOT NULL, p_email, email),
        estado = IF(p_estado IS NOT NULL, p_estado, estado),
        fecha_nacimiento = IF(p_fecha_nacimiento IS NOT NULL, p_fecha_nacimiento, fecha_nacimiento),
        sexo = IF(p_sexo IS NOT NULL, p_sexo, sexo),
        direccion = IF(p_direccion IS NOT NULL, p_direccion, direccion),
        seguro = IF(p_seguro IS NOT NULL, p_seguro, seguro),
        dni = IF(p_dni_nuevo IS NOT NULL, p_dni_nuevo, dni)
    WHERE dni = p_dni_actual;
    SELECT ROW_COUNT() AS actualizadas;
END$$

DROP PROCEDURE IF EXISTS `sp_listar_servicios`$$
CREATE PROCEDURE `sp_listar_servicios`()
BEGIN
    SELECT * FROM servicios WHERE activo = 1 ORDER BY nombre;
END$$

DROP PROCEDURE IF EXISTS `sp_listar_evaluaciones`$$
CREATE PROCEDURE `sp_listar_evaluaciones`(IN p_paciente_id INT)
BEGIN
    -- FASE 2: local. El nombre del terapeuta (usuarios vive en
    -- moovacloud_auth) se agrega en pacientes_service via auth/auth_client.
    SELECT ei.*
    FROM evaluaciones_iniciales ei
    WHERE ei.paciente_id = p_paciente_id
    ORDER BY ei.fecha_creacion DESC;
END$$

DROP PROCEDURE IF EXISTS `sp_crear_evaluacion`$$
CREATE PROCEDURE `sp_crear_evaluacion`(
    IN p_paciente_id INT, IN p_terapeuta_id INT, IN p_motivo_consulta TEXT,
    IN p_escala_dolor_eva INT, IN p_rango_movimiento TEXT, IN p_objetivos_terapeuticos TEXT
)
BEGIN
    INSERT INTO evaluaciones_iniciales
        (paciente_id, terapeuta_id, motivo_consulta, escala_dolor_eva, rango_movimiento, objetivos_terapeuticos)
    VALUES (p_paciente_id, p_terapeuta_id, p_motivo_consulta, p_escala_dolor_eva, p_rango_movimiento, p_objetivos_terapeuticos);
    SELECT LAST_INSERT_ID() AS id;
END$$

DROP PROCEDURE IF EXISTS `sp_listar_consentimientos`$$
CREATE PROCEDURE `sp_listar_consentimientos`(IN p_paciente_id INT)
BEGIN
    SELECT * FROM consentimientos WHERE paciente_id = p_paciente_id ORDER BY aceptado_en DESC;
END$$

DROP PROCEDURE IF EXISTS `sp_crear_consentimiento`$$
CREATE PROCEDURE `sp_crear_consentimiento`(
    IN p_paciente_id INT, IN p_tipo VARCHAR(50), IN p_texto_version VARCHAR(50), IN p_ip_origen VARCHAR(45)
)
BEGIN
    INSERT INTO consentimientos (paciente_id, tipo, texto_version, ip_origen)
    VALUES (p_paciente_id, p_tipo, p_texto_version, p_ip_origen);
    SELECT LAST_INSERT_ID() AS id;
END$$

-- --------------------------------------------------------
-- Procedimientos de gestion (gateway/admin) sobre tablas de moovacloud_pacientes
-- --------------------------------------------------------

DROP PROCEDURE IF EXISTS `sp_obtener_especialidad_id`$$
CREATE PROCEDURE `sp_obtener_especialidad_id`(IN p_nombre VARCHAR(100))
BEGIN
    SELECT id FROM especialidades WHERE nombre = p_nombre;
END$$

DROP PROCEDURE IF EXISTS `sp_listar_especialidades`$$
CREATE PROCEDURE `sp_listar_especialidades`()
BEGIN
    SELECT id, nombre FROM especialidades WHERE activa = 1 ORDER BY nombre;
END$$

DROP PROCEDURE IF EXISTS `sp_actualizar_precio`$$
CREATE PROCEDURE `sp_actualizar_precio`(IN p_medico_id INT, IN p_precio DECIMAL(10,2))
BEGIN
    UPDATE terapeutas SET precio = p_precio WHERE id = p_medico_id;
END$$

DROP PROCEDURE IF EXISTS `sp_set_terapeuta_activo`$$
CREATE PROCEDURE `sp_set_terapeuta_activo`(IN p_medico_id INT, IN p_activo TINYINT)
BEGIN
    UPDATE terapeutas SET activo = p_activo WHERE id = p_medico_id;
END$$

DROP PROCEDURE IF EXISTS `sp_estadisticas_especialistas`$$
CREATE PROCEDURE `sp_estadisticas_especialistas`()
BEGIN
    SELECT COUNT(*) AS total FROM terapeutas WHERE activo = 1;
END$$

DROP PROCEDURE IF EXISTS `sp_estadisticas_opiniones`$$
CREATE PROCEDURE `sp_estadisticas_opiniones`()
BEGIN
    SELECT COUNT(*) AS total, SUM(CASE WHEN calificacion >= 4 THEN 1 ELSE 0 END) AS buenas
    FROM opiniones WHERE visible = 1;
END$$

-- --------------------------------------------------------
-- Procedimientos CROSS-DB de FASE 1 COMENTADOS: migrados a funciones
-- locales + enriquecimiento via HTTP (citas/pagos/auth services).
-- Eliminados: sp_obtener_historial_paciente, sp_listar_paquetes,
-- sp_crear_paquete, sp_consultar_medicos_admin,
-- sp_obtener_ficha_clinica_completa (delegados en los servicios).
-- --------------------------------------------------------

--
-- sp_listar_pacientes  |  LOCAL (FASE 2)
--   total_visitas y ultima_cita YA NO se calculan aqui (historial_citas
--   vive en moovacloud_citas). Se calculan en pacientes_service usando
--   citas_client (GET /api/citas/resumen_pacientes).
--
DROP PROCEDURE IF EXISTS `sp_listar_pacientes`$$
CREATE PROCEDURE `sp_listar_pacientes`()
BEGIN
    SELECT p.*
    FROM pacientes p
    ORDER BY p.apellido ASC;
END$$

--
-- sp_crear_paciente_min  |  LOCAL (FASE 2)
--   Crea paciente con datos minimos (nombre, apellido, dni, telefono).
--   Usado por citas_service cuando el hub de reserva trae un dni
--   desconocido.
--
DROP PROCEDURE IF EXISTS `sp_crear_paciente_min`$$
CREATE PROCEDURE `sp_crear_paciente_min`(
    IN p_nombre VARCHAR(100), IN p_apellido VARCHAR(100),
    IN p_dni VARCHAR(20), IN p_telefono VARCHAR(20)
)
BEGIN
    INSERT INTO pacientes (nombre, apellido, dni, telefono)
    VALUES (p_nombre, p_apellido, p_dni, p_telefono);
    SELECT LAST_INSERT_ID() AS id;
END$$

--
-- sp_listar_terapeutas  |  LOCAL (FASE 2)
--   Solo columnas propias. Nombre/telefono/correo del usuario se
--   enriquecen en pacientes_service via auth_client
--   (GET /api/auth/usuarios/por-nombre o lista de usuarios).
--
DROP PROCEDURE IF EXISTS `sp_listar_terapeutas`$$
CREATE PROCEDURE `sp_listar_terapeutas`()
BEGIN
    SELECT t.id AS ID, t.usuario_id, t.especialidad_id, t.precio, t.activo
    FROM terapeutas t
    ORDER BY t.id;
END$$

--
-- sp_obtener_terapeuta  |  LOCAL (FASE 2)
--
DROP PROCEDURE IF EXISTS `sp_obtener_terapeuta`$$
CREATE PROCEDURE `sp_obtener_terapeuta`(IN p_medico_id INT)
BEGIN
    SELECT id AS ID, usuario_id, especialidad_id, precio, activo
    FROM terapeutas
    WHERE id = p_medico_id;
END$$

--
-- sp_crear_terapeuta  |  LOCAL (FASE 2)
--   El usuario se crea primero via auth_service; este SP solo inserta
--   la fila de terapeutas con el usuario_id resultante.
--
DROP PROCEDURE IF EXISTS `sp_crear_terapeuta`$$
CREATE PROCEDURE `sp_crear_terapeuta`(IN p_usuario_id INT, IN p_especialidad_id INT, IN p_precio DECIMAL(10,2))
BEGIN
    INSERT INTO terapeutas (usuario_id, especialidad_id, precio) VALUES (p_usuario_id, p_especialidad_id, p_precio);
    SELECT LAST_INSERT_ID() AS id;
END$$

DELIMITER ;

-- ============================================================
-- FIN pacientes_db.sql
-- ============================================================


-- =============================================================
-- ORIGEN: db_split/citas_db.sql
-- =============================================================

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
--         que ahora viven en  Pendiente de recrear como
--         logica de Fase 2.
--   - Los procedimientos que tocan tablas de otras bases se
--     conservan comentados y documentados como CROSS-DB
--     (pendientes de convertir en Fase 2).
-- ============================================================
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
  `estado` enum('pendiente_pago','programada','confirmada','cancelada','completada','no_asistio') NOT NULL DEFAULT 'programada',
  `recordatorio_enviado` tinyint(1) DEFAULT 0,
  `creado_en` datetime DEFAULT NULL,
  `actualizado_en` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Politica de zona horaria (historial_citas):
--   - creado_en / actualizado_en se guardan en UTC explicito con
--     UTC_TIMESTAMP(), NUNCA NOW()/CURRENT_TIMESTAMP(): el servidor MySQL
--     corre en SYSTEM/CEST (UTC+2), asi que el reloj de la maquina no debe
--     decidir los timestamps. Las columnas no usan DEFAULT with a timestamp
--     precisamente para que el valor lo fije el procedimiento.
--   - fecha_cita / hora_cita son literales (DATE/TIME sin zona): guardan
--     exactamente lo que el paciente eligio, interpretado como hora de Lima
--     (America/Lima, UTC-5). La capa de presentacion convierte a Lima.

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
      AND estado IN ('pendiente_pago', 'programada', 'confirmada')
      AND (p_excluir_cita_id IS NULL OR id <> p_excluir_cita_id);
END$$

DROP PROCEDURE IF EXISTS `sp_crear_cita`$$
CREATE PROCEDURE `sp_crear_cita`(
    IN p_paciente_id INT, IN p_terapeuta_id INT, IN p_servicio_id INT,
    IN p_fecha DATETIME, IN p_hora TIME
)
BEGIN
    INSERT INTO historial_citas (
        paciente_id, terapeuta_id, servicio_id, fecha_cita, hora_cita, estado,
        creado_en, actualizado_en
    )
    VALUES (
        p_paciente_id, p_terapeuta_id, p_servicio_id, p_fecha, p_hora, 'programada',
        UTC_TIMESTAMP(), UTC_TIMESTAMP()
    );
    SELECT LAST_INSERT_ID() AS id;
END$$

DROP PROCEDURE IF EXISTS `sp_crear_cita_pendiente_pago`$$
CREATE PROCEDURE `sp_crear_cita_pendiente_pago`(
    IN p_paciente_id INT, IN p_terapeuta_id INT, IN p_servicio_id INT,
    IN p_fecha DATETIME, IN p_hora TIME
)
BEGIN
    INSERT INTO historial_citas (
        paciente_id, terapeuta_id, servicio_id, fecha_cita, hora_cita, estado,
        creado_en, actualizado_en
    )
    VALUES (
        p_paciente_id, p_terapeuta_id, p_servicio_id, p_fecha, p_hora,
        'pendiente_pago', UTC_TIMESTAMP(), UTC_TIMESTAMP()
    );
    SELECT LAST_INSERT_ID() AS id;
END$$

DROP PROCEDURE IF EXISTS `sp_confirmar_cita_pago`$$
CREATE PROCEDURE `sp_confirmar_cita_pago`(IN p_cita_id INT)
BEGIN
    UPDATE historial_citas
    SET estado = 'programada', actualizado_en = UTC_TIMESTAMP()
    WHERE id = p_cita_id AND estado = 'pendiente_pago';
    SELECT ROW_COUNT() AS actualizadas;
END$$

DROP PROCEDURE IF EXISTS `sp_modificar_cita`$$
CREATE PROCEDURE `sp_modificar_cita`(IN p_cita_id INT, IN p_fecha DATETIME, IN p_medico_id INT, IN p_hora TIME)
BEGIN
    UPDATE historial_citas
    SET fecha_cita = p_fecha,
        hora_cita = p_hora,
        terapeuta_id = p_medico_id,
        actualizado_en = UTC_TIMESTAMP()
    WHERE id = p_cita_id AND estado = 'programada';
    SELECT ROW_COUNT() AS actualizadas;
END$$

DROP PROCEDURE IF EXISTS `sp_completar_cita`$$
CREATE PROCEDURE `sp_completar_cita`(IN p_historial_id INT, IN p_descripcion TEXT)
BEGIN
    UPDATE historial_citas SET descripcion = p_descripcion, estado = 'completada',
        actualizado_en = UTC_TIMESTAMP()
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
    UPDATE historial_citas SET estado = 'cancelada', actualizado_en = UTC_TIMESTAMP()
    WHERE id = p_cita_id AND estado = 'programada';
    SET v_afectadas = ROW_COUNT();
    SELECT v_afectadas AS actualizadas;
END$$

-- Cancela solo citas programadas cuando el pago anticipado vencio.
-- Las citas completadas o ya canceladas permanecen intactas.
DROP PROCEDURE IF EXISTS `sp_cancelar_cita_pago_vencido`$$
CREATE PROCEDURE `sp_cancelar_cita_pago_vencido`(IN p_cita_id INT)
BEGIN
    UPDATE historial_citas
    SET estado = 'cancelada',
        descripcion = CONCAT_WS(
            ' | ', NULLIF(TRIM(descripcion), ''), 'pago vencido'
        ),
        actualizado_en = UTC_TIMESTAMP()
    WHERE id = p_cita_id AND estado IN ('pendiente_pago', 'programada');
    SELECT ROW_COUNT() AS actualizadas;
END$

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
      AND estado <> 'pendiente_pago'
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
    WHERE estado <> 'pendiente_pago'
    GROUP BY paciente_id;
END$$

-- --------------------------------------------------------
-- Recordatorios automaticos por SMS (sustentacion).
-- La tarde anterior se envia un aviso al paciente de las citas
-- del dia siguiente. recordatorio_enviado era una columna que no
-- usaba nadie; ahora es el cursor del envio.
-- --------------------------------------------------------

--
-- sp_citas_pendientes_recordatorio  |  LOCAL
--   Citas de un dia concreto que todavia no recibieron recordatorio.
--   Solo 'programada' y 'confirmada': 'cancelada' y 'completada'
--   no deben recibir SMS.
--
DROP PROCEDURE IF EXISTS `sp_citas_pendientes_recordatorio`$$
CREATE PROCEDURE `sp_citas_pendientes_recordatorio`(IN p_fecha DATE)
BEGIN
    SELECT id, paciente_id, terapeuta_id, fecha_cita, hora_cita
    FROM historial_citas
    WHERE fecha_cita = p_fecha
      AND estado IN ('programada', 'confirmada')
      AND COALESCE(recordatorio_enviado, 0) = 0
    ORDER BY hora_cita ASC;
END$$

--
-- sp_marcar_recordatorio_enviado  |  LOCAL
--   Reclamo atomico: solo marca si recordatorio_enviado todavia
--   es 0. ROW_COUNT()=1 significa que ESTE proceso gano el envio,
--   lo que evita el doble SMS si dos procesos corren a la vez
--   (el scheduler de APScheduler y el endpoint manual).
--
DROP PROCEDURE IF EXISTS `sp_marcar_recordatorio_enviado`$$
CREATE PROCEDURE `sp_marcar_recordatorio_enviado`(IN p_cita_id INT)
BEGIN
    UPDATE historial_citas
    SET recordatorio_enviado = 1, actualizado_en = UTC_TIMESTAMP()
    WHERE id = p_cita_id AND COALESCE(recordatorio_enviado, 0) = 0;
    SELECT ROW_COUNT() AS marcadas;
END$$

--
-- sp_desmarcar_recordatorio  |  LOCAL
--   Deshace el reclamo cuando el SMS fallo o el paciente no tiene
--   telefono, para que el siguiente ciclo reintente la misma cita.
--
DROP PROCEDURE IF EXISTS `sp_desmarcar_recordatorio`$$
CREATE PROCEDURE `sp_desmarcar_recordatorio`(IN p_cita_id INT)
BEGIN
    UPDATE historial_citas
    SET recordatorio_enviado = 0, actualizado_en = UTC_TIMESTAMP()
    WHERE id = p_cita_id;
    SELECT ROW_COUNT() AS desmarcadas;
END$$

-- --------------------------------------------------------
-- Reporte de pacientes en riesgo de fuga (sustentacion).
--
-- Se calcula SOLO con datos de esta base (moovacloud_citas): el
-- split de bases prohibio las consultas cruzadas, y aqui alcanza
-- porque todo el signal vive en historial_citas.
--
-- Dos senales de abandono:
--   1. No tiene ninguna cita futura programada/confirmada y ya paso
--      bastante tiempo desde su ultima cita (p_dias_umbral).
--   2. Falto (estado 'no_asistio') tres o mas veces: senal fuerte
--      de abandono, con o sin cita futura.
--
-- Devuelve SOLO los pacientes en riesgo, con las metricas crudas.
-- El nombre, el telefono y el nivel lo agrega citas_service.
-- --------------------------------------------------------

--
-- sp_pacientes_en_riesgo  |  LOCAL
--   p_fecha: dia de referencia (hoy en America/Lima).
--   p_dias_umbral: dias desde la ultima cita para la senal 1.
--
DROP PROCEDURE IF EXISTS `sp_pacientes_en_riesgo`$$
CREATE PROCEDURE `sp_pacientes_en_riesgo`(IN p_fecha DATE, IN p_dias_umbral INT)
BEGIN
    SELECT
        h.paciente_id AS paciente_id,
        -- Ultima cita de cualquier tipo ya pasada: incluye las que
        -- quedaron 'programadas' y nunca se cerraron.
        MAX(CASE WHEN h.fecha_cita < p_fecha THEN h.fecha_cita END) AS ultima_cita,
        DATEDIFF(p_fecha, MAX(CASE WHEN h.fecha_cita < p_fecha THEN h.fecha_cita END))
            AS dias_desde_ultima,
        SUM(CASE WHEN h.fecha_cita >= p_fecha
                  AND h.estado IN ('programada', 'confirmada')
                 THEN 1 ELSE 0 END) AS citas_programadas,
        SUM(CASE WHEN h.estado = 'completada' THEN 1 ELSE 0 END) AS completadas,
        SUM(CASE WHEN h.estado = 'cancelada'  THEN 1 ELSE 0 END) AS canceladas,
        SUM(CASE WHEN h.estado = 'no_asistio' THEN 1 ELSE 0 END) AS faltas
    FROM historial_citas h
    GROUP BY h.paciente_id
    HAVING (
        -- 1) Sin cita futura y ya hace rato que no viene.
        (citas_programadas = 0 AND dias_desde_ultima >= p_dias_umbral)
        -- 2) Falto tres o mas veces.
        OR (faltas >= 3)
    )
    ORDER BY dias_desde_ultima DESC, faltas DESC;
END$$

DELIMITER ;

-- ============================================================
-- FIN citas_db.sql
-- ============================================================


-- =============================================================
-- ORIGEN: db_split/pagos_db.sql
-- =============================================================

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
  `cita_liberada` tinyint(1) NOT NULL DEFAULT 0,
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
    -- Solo mientras el pago sigue pendiente. Sin esta condicion cualquier
    -- /iniciar pisaba la referencia de un pago ya pagado, y con ella
    -- pasaba a ser el cobro "valido" de la cita.
    UPDATE pagos
    SET referencia = p_cobro_id
    WHERE cita_id = p_cita_id AND estado_pago = 'pendiente';
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
    -- Acepta tambien 'vencido' (pago pagado por el proveedor despues de
    -- que el job de expiracion lo marcara): el dinero entro igualmente y
    -- descartarlo dejaria al paciente con el cobro hecho y la cita
    -- impagada, que habria que revertir a mano.
    IF p_verificado_por IS NOT NULL THEN
        UPDATE pagos
        SET estado_pago = 'pagado', fecha_pago = NOW(),
            referencia = COALESCE(p_referencia, referencia),
            transaccion_id = COALESCE(p_referencia, transaccion_id),
            datos_respuesta = COALESCE(p_datos_respuesta, datos_respuesta),
            verificado_en = NOW(), verificado_por = p_verificado_por
        WHERE cita_id = p_cita_id
          AND estado_pago IN ('pendiente', 'vencido');
    ELSE
        UPDATE pagos
        SET estado_pago = 'pagado', fecha_pago = NOW(),
            referencia = COALESCE(p_referencia, referencia),
            transaccion_id = COALESCE(p_referencia, transaccion_id),
            datos_respuesta = COALESCE(p_datos_respuesta, datos_respuesta),
            verificado_en = NOW()
        WHERE cita_id = p_cita_id
          AND estado_pago IN ('pendiente', 'vencido');
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
-- sp_liberar_pagos_vencidos  |  LOCAL (FASE 4)
--   Expira los pagos 'pendiente' mas antiguos que p_horas horas para
--   que el espacio de la cita se libere y el paciente pueda volver a
--   reservar. Sin esto, una cita abandonada a mitad del pago queda
--   bloqueada de forma indefinida (no hay job que la limpie).
--
--   Marca pagos pendientes vencidos y devuelve las citas que aun no
--   se han cancelado en citas_service para que el proceso pueda reintentar.
--   Los 'pagado' y 'cancelado' no se alteran. Usa creado_en (indice idx_fecha cubre fecha_pago, pero
--   los pendientes la tienen a NULL, asi que no sirve aqui).
--
DROP PROCEDURE IF EXISTS `sp_liberar_pagos_vencidos`$$
CREATE PROCEDURE `sp_liberar_pagos_vencidos`(IN p_horas INT)
BEGIN
    DECLARE v_limite DATETIME;
    DECLARE v_nuevos INT DEFAULT 0;

    IF p_horas IS NULL OR p_horas <= 0 THEN
        SET p_horas = 24;
    END IF;

    SET v_limite = DATE_SUB(NOW(), INTERVAL p_horas HOUR);

    CREATE TEMPORARY TABLE IF NOT EXISTS tmp_citas_pago_vencido (
        cita_id INT NOT NULL PRIMARY KEY
    ) ENGINE=MEMORY;
    UPDATE pagos
    SET estado_pago = 'vencido',
        cita_liberada = 0,
        notas = CONCAT(COALESCE(notas, ''),
                       ' [expire automatico: pendiente sin confirmar]')
    WHERE estado_pago = 'pendiente'
      AND creado_en < v_limite;
    SET v_nuevos = ROW_COUNT();

    TRUNCATE TABLE tmp_citas_pago_vencido;
    INSERT IGNORE INTO tmp_citas_pago_vencido (cita_id)
    SELECT DISTINCT cita_id
    FROM pagos
    WHERE estado_pago = 'vencido'
      AND cita_liberada = 0
      AND creado_en < v_limite;

    SELECT cita_id FROM tmp_citas_pago_vencido ORDER BY cita_id;
    SELECT v_nuevos AS vencidos;
    DROP TEMPORARY TABLE tmp_citas_pago_vencido;
END$$

DROP PROCEDURE IF EXISTS `sp_marcar_citas_pago_vencido_liberadas`$$
CREATE PROCEDURE `sp_marcar_citas_pago_vencido_liberadas`(IN p_cita_id INT)
BEGIN
    UPDATE pagos
    SET cita_liberada = 1
    WHERE cita_id = p_cita_id AND estado_pago = 'vencido';
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

--
-- sp_usar_sesion_paquete  |  LOCAL (FASE 2)
--   Vincula una cita a un paquete de sesiones (inserta en
--   paquete_sesiones_uso) e incrementa sesiones_usadas del paquete.
--   Solo actua si el paquete esta 'activo' y aun tiene sesiones
--   disponibles; al llegar a total_sesiones lo marca 'agotado'.
--   Lo invoca pagos_service (POST /api/pagos/paquetes/<id>/usar)
--   desde el flujo publico /tratamiento, justo despues de crear la
--   cita de la siguiente sesion del tratamiento.
--
DROP PROCEDURE IF EXISTS `sp_usar_sesion_paquete`$$
CREATE PROCEDURE `sp_usar_sesion_paquete`(
    IN p_paquete_id INT, IN p_cita_id INT
)
BEGIN
    DECLARE v_actualizadas INT DEFAULT 0;

    UPDATE paquetes_sesiones
    SET sesiones_usadas = sesiones_usadas + 1,
        estado = IF(sesiones_usadas + 1 >= total_sesiones, 'agotado', estado)
    WHERE id = p_paquete_id
      AND estado = 'activo'
      AND sesiones_usadas < total_sesiones;

    SET v_actualizadas = ROW_COUNT();

    IF v_actualizadas > 0 THEN
        INSERT IGNORE INTO paquete_sesiones_uso (paquete_id, cita_id)
        VALUES (p_paquete_id, p_cita_id);
    END IF;

    SELECT v_actualizadas AS usadas;
END$$

DELIMITER ;

-- ============================================================
-- FIN pagos_db.sql
-- ============================================================


-- =============================================================
-- ORIGEN: db_split/notas_db.sql
-- =============================================================

-- ============================================================
-- notas_db.sql
-- Base de datos de NOTAS CLINICAS
-- Servicio que la consume: notas_service
-- FASE 1 - Separacion de bases (solo archivos SQL)
--
-- Tablas propias:
--   notas_clinicas  (sin filas actuales en el dump; se conserva
--                    estructura, indices y AUTO_INCREMENT)
--
-- FK internas:
--   (ninguna: las tres referencias de notas_clinicas apuntan a
--    tablas de otras bases, por eso van como comentario)
--
-- Referencias externas (SIN FK, comentadas):
--   notas_clinicas.cita_id      -> historial_citas.id (moovacloud_citas). Sin FK.
--   notas_clinicas.paciente_id  -> pacientes.id (moovacloud_pacientes). Sin FK.
--   notas_clinicas.terapeuta_id -> terapeutas.id (moovacloud_pacientes). Sin FK.
--
-- Notas de FASE 1:
--   - Los procedimientos que tocan tablas de otras bases se
--     conservan comentados y documentados como CROSS-DB
--     (pendientes de convertir en Fase 2).
-- ============================================================
-- --------------------------------------------------------
--
-- Table structure for table `notas_clinicas`
--

CREATE TABLE `notas_clinicas` (
  `id` int(11) NOT NULL,
  `cita_id` int(11) NOT NULL,
  `paciente_id` int(11) NOT NULL,
  `terapeuta_id` int(11) NOT NULL,
  `nota` text NOT NULL,
  `diagnostico` varchar(255) DEFAULT NULL,
  `fecha_creacion` timestamp NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- (La tabla no tiene filas actuales en el dump de origen:
--  no hay INSERTs que conservar.)

--
-- Indexes for table `notas_clinicas`
--
ALTER TABLE `notas_clinicas`
  ADD PRIMARY KEY (`id`),
  ADD KEY `cita_id` (`cita_id`),
  ADD KEY `notas_clinicas_ibfk_2` (`paciente_id`),
  ADD KEY `notas_clinicas_ibfk_3` (`terapeuta_id`);

--
-- AUTO_INCREMENT for table `notas_clinicas`
--
ALTER TABLE `notas_clinicas`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

-- --------------------------------------------------------
-- Constraints (SIN FK real hacia otras bases, solo comentario)
--
-- Ref. historial_citas (moovacloud_citas). Sin FK.
--   notas_clinicas.cita_id -> historial_citas.id
-- Ref. pacientes (moovacloud_pacientes). Sin FK.
--   notas_clinicas.paciente_id -> pacientes.id
-- Ref. terapeutas (moovacloud_pacientes). Sin FK.
--   notas_clinicas.terapeuta_id -> terapeutas.id
-- --------------------------------------------------------

-- --------------------------------------------------------
--
-- Procedimientos del dominio de notas clinicas
--

DELIMITER $$

DROP PROCEDURE IF EXISTS `sp_crear_nota`$$
CREATE PROCEDURE `sp_crear_nota`(
    IN p_cita_id INT, IN p_paciente_id INT, IN p_terapeuta_id INT,
    IN p_nota TEXT, IN p_diagnostico TEXT
)
BEGIN
    INSERT INTO notas_clinicas (cita_id, paciente_id, terapeuta_id, nota, diagnostico)
    VALUES (p_cita_id, p_paciente_id, p_terapeuta_id, p_nota, p_diagnostico);
    SELECT LAST_INSERT_ID() AS id;
END$$

-- --------------------------------------------------------
-- Procedimientos CROSS-DB de FASE 1 ELIMINADOS en FASE 2:
--   sp_obtener_paciente_id_cita (leia historial_citas de moovacloud_citas).
--   El paciente_id de una cita se obtiene hoy via HTTP en
--   notas_service -> citas_client (GET /api/citas/<id>).
-- --------------------------------------------------------

--
-- sp_listar_notas  |  LOCAL (FASE 2)
--   Solo columnas propias. El nombre del autor (usuarios vive en
--   moovacloud_auth, via terapeutas de moovacloud_pacientes) se enriquece en
--   notas_service usando la lista de terapeutas de pacientes_client.
--
DROP PROCEDURE IF EXISTS `sp_listar_notas`$$
CREATE PROCEDURE `sp_listar_notas`(IN p_cita_id INT)
BEGIN
    SELECT nc.*
    FROM notas_clinicas nc
    WHERE nc.cita_id = p_cita_id
    ORDER BY nc.fecha_creacion DESC;
END$$

DELIMITER ;

-- ============================================================
-- FIN notas_db.sql
-- ============================================================


-- =============================================================
-- ORIGEN: db_split/audit_db.sql
-- =============================================================

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
  `entidad_tipo` varchar(20) DEFAULT NULL,
  `entidad_id` int(11) DEFAULT NULL,
  `entidad_nombre` varchar(150) DEFAULT NULL,
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
    IN p_ip_origen VARCHAR(45),
    IN p_entidad_tipo VARCHAR(20),
    IN p_entidad_id INT,
    IN p_entidad_nombre VARCHAR(150)
)
BEGIN
    INSERT INTO logs_auditoria (usuario_id, usuario_tipo, usuario_nombre, accion, detalles, ip_origen,
                                entidad_tipo, entidad_id, entidad_nombre)
    VALUES (p_usuario_id, p_usuario_tipo, p_usuario_nombre, p_accion, p_detalles, p_ip_origen,
            p_entidad_tipo, p_entidad_id, p_entidad_nombre);
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
    IN p_usuario_id INT,
    IN p_usuario_tipo VARCHAR(20),
    IN p_accion VARCHAR(255),
    IN p_fecha_desde DATETIME,
    IN p_fecha_hasta DATETIME,
    IN p_entidad_tipo VARCHAR(20)
)
BEGIN
    SELECT id, usuario_tipo, usuario_id, usuario_nombre,
           accion, detalles, ip_origen, fecha_creacion,
           entidad_tipo, entidad_id, entidad_nombre
    FROM logs_auditoria
    WHERE (p_usuario_id IS NULL OR usuario_id = p_usuario_id)
      AND (p_usuario_tipo IS NULL OR usuario_tipo = p_usuario_tipo)
      AND (p_accion IS NULL OR accion LIKE CONCAT('%', p_accion, '%'))
      AND (p_fecha_desde IS NULL OR fecha_creacion >= p_fecha_desde)
      AND (p_fecha_hasta IS NULL OR fecha_creacion <= p_fecha_hasta)
      AND (p_entidad_tipo IS NULL OR entidad_tipo = p_entidad_tipo)
    ORDER BY fecha_creacion DESC
    LIMIT 200;
END$$

DELIMITER ;


-- =============================================================
-- ORIGEN: db_split/kpis_db.sql
-- =============================================================

-- ============================================================
-- kpis_db.sql
-- Base de datos de REPORTES / KPIs (panel admin)
--
-- Las tablas fuente viven en las BBDD de dominio (split FASE 1/2):
--   historial_citas  -> moovacloud_citas
--   pagos, paquetes_sesiones -> moovacloud_pagos
--   terapeutas       -> moovacloud_pacientes
--   servicios        -> moovacloud_pacientes
--   usuarios         -> moovacloud_auth (nombre del terapeuta)
--
-- Estos procedimientos SON de solo lectura (CROSS-DB) y se ejecutan
-- desde un solo servidor MySQL/MariaDB con privilegios sobre todas
-- las bases moovacloud_*. Los consume citas_service via el endpoint
-- GET /api/kpis (shared/proc.call_proc con db_name="moovacloud_kpis").
-- ============================================================
DELIMITER $$

-- --------------------------------------------------------
-- Resumen general de KPIs en un rango de fechas.
-- Las fechas se interpretan en hora de Peru (America/Lima);
-- las columnas de fecha (date/datetime) se almacenan en hora local.
-- Devuelve UNA fila (todas las metricas del panel).
-- --------------------------------------------------------
DROP PROCEDURE IF EXISTS `sp_kpis_resumen`$$
CREATE PROCEDURE `sp_kpis_resumen`(IN p_desde DATE, IN p_hasta DATE)
BEGIN
    DECLARE v_total INT DEFAULT 0;
    DECLARE v_completadas INT DEFAULT 0;
    DECLARE v_canceladas INT DEFAULT 0;
    DECLARE v_programadas INT DEFAULT 0;

    SELECT COUNT(*),
           COALESCE(SUM(estado = 'completada'), 0),
           COALESCE(SUM(estado = 'cancelada'), 0),
           COALESCE(SUM(estado IN ('programada', 'confirmada')), 0)
      INTO v_total, v_completadas, v_canceladas, v_programadas
      FROM historial_citas
     WHERE fecha_cita BETWEEN p_desde AND p_hasta;

    SELECT v_total AS total_citas,
           v_completadas AS citas_completadas,
           v_canceladas AS citas_canceladas,
           v_programadas AS citas_programadas,
           ROUND(100 * v_completadas / NULLIF(v_total, 0), 2) AS tasa_completadas,
           ROUND(100 * v_canceladas / NULLIF(v_total, 0), 2) AS tasa_cancelacion,
           COALESCE((
               SELECT SUM(monto) FROM pagos
                WHERE estado_pago = 'pagado'
                  AND DATE(fecha_pago) BETWEEN p_desde AND p_hasta
           ), 0) AS ingresos_confirmados,
           COALESCE((
               SELECT SUM(monto) FROM pagos
                WHERE estado_pago = 'pendiente'
           ), 0) AS ingresos_pendientes,
           (SELECT COUNT(*) FROM paquetes_sesiones
             WHERE fecha_compra BETWEEN p_desde AND p_hasta) AS paquetes_vendidos,
           COALESCE((
               SELECT SUM(sesiones_usadas) FROM paquetes_sesiones
                WHERE estado = 'activo'
                  AND fecha_compra BETWEEN p_desde AND p_hasta
           ), 0) AS sesiones_consumidas;
END$$

-- --------------------------------------------------------
-- KPIs por terapeuta en un rango de fechas.
-- Incluye terapeutas sin actividad (totales en 0) para que el
-- panel muestre todo el equipo. El nombre sale de usuarios (auth).
-- Los ingresos se atribuyen al terapeuta via la cita del pago.
-- --------------------------------------------------------
DROP PROCEDURE IF EXISTS `sp_kpis_por_terapeuta`$$
CREATE PROCEDURE `sp_kpis_por_terapeuta`(IN p_desde DATE, IN p_hasta DATE)
BEGIN
    SELECT t.id AS terapeuta_id,
           COALESCE(u.nombre, CONCAT('Terapeuta #', t.id)) AS terapeuta_nombre,
           COALESCE(v.total_citas, 0) AS total_citas,
           COALESCE(v.completadas, 0) AS citas_completadas,
           COALESCE(ROUND(100 * v.completadas / NULLIF(v.total_citas, 0), 2), 0) AS tasa_completadas,
           COALESCE(v.ingresos, 0) AS ingresos
      FROM terapeutas t
      LEFT JOIN usuarios u ON u.id = t.usuario_id
      LEFT JOIN (
            SELECT h.terapeuta_id,
                   COUNT(*) AS total_citas,
                   COALESCE(SUM(h.estado = 'completada'), 0) AS completadas,
                   COALESCE((
                       SELECT SUM(pg.monto)
                         FROM pagos pg
                         JOIN historial_citas hc ON hc.id = pg.cita_id
                        WHERE pg.estado_pago = 'pagado'
                          AND DATE(pg.fecha_pago) BETWEEN p_desde AND p_hasta
                          AND hc.terapeuta_id = h.terapeuta_id
                   ), 0) AS ingresos
              FROM historial_citas h
             WHERE h.fecha_cita BETWEEN p_desde AND p_hasta
               AND h.estado <> 'pendiente_pago'
             GROUP BY h.terapeuta_id
      ) v ON v.terapeuta_id = t.id
     ORDER BY v.ingresos DESC, v.total_citas DESC;
END$$

DELIMITER ;


SET FOREIGN_KEY_CHECKS = 1;

-- =============================================================
-- FIN: BASE UNIFICADA MOOVACLINIC
-- =============================================================
