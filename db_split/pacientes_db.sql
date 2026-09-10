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

CREATE DATABASE IF NOT EXISTS `moovacloud_pacientes` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE `moovacloud_pacientes`;

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
-- sp_obtener_paciente_id_dni  |  LOCAL (FASE 2)
--   Devuelve el id del paciente segun dni (para resolver ids que antes
--   resolvian ingresando a moovacloud_citas via JOIN).
--
DROP PROCEDURE IF EXISTS `sp_obtener_paciente_id_dni`$$
CREATE PROCEDURE `sp_obtener_paciente_id_dni`(IN p_dni VARCHAR(20))
BEGIN
    SELECT id FROM pacientes WHERE dni = p_dni;
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

--
-- sp_obtener_usuario_id_terapeuta  |  LOCAL (FASE 2)
--
DROP PROCEDURE IF EXISTS `sp_obtener_usuario_id_terapeuta`$$
CREATE PROCEDURE `sp_obtener_usuario_id_terapeuta`(IN p_medico_id INT)
BEGIN
    SELECT usuario_id FROM terapeutas WHERE id = p_medico_id;
END$$

DELIMITER ;

-- ============================================================
-- FIN pacientes_db.sql
-- ============================================================