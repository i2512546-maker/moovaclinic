-- =============================================================
-- MOOVA CLINIC - ESTRUCTURA UNIFICADA DE TABLAS
-- Crea únicamente las tablas de la base de datos existente.
-- Incluye índices, claves foráneas y valores AUTO_INCREMENT.
-- No inserta datos ni crea procedimientos almacenados.
--
-- Selecciona la base moovacloud_db antes de ejecutar este archivo.
-- =============================================================

USE `moovacloud_db`;

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



SET FOREIGN_KEY_CHECKS = 1;

-- Fin: estructura unificada de tablas.
