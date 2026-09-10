-- ============================================================
-- MOOVA Clinic - Migracion v3 (Registro de Rehabilitaciones)
-- ============================================================
-- MODULO: Admin -> Pacientes -> Registro de rehabilitacion.
--
-- PARTE A: Tabla `rehabilitaciones` (aditiva, no toca tablas
--          existentes). Cada fila = una cita/sesion de
--          rehabilitacion numerada (Cita 1, Cita 2, ...).
--          La clave UNIQUE (paciente_id, numero_cita) garantiza
--          a nivel de base de datos que un paciente NO pueda
--          tener dos registros para la misma cita.
--
-- PARTE B: Procedimientos almacenados de lectura/escritura.
--          El numero de cita lo calcula el PROCEDURE (nunca el
--          cliente), de modo que solo se puede registrar la
--          siguiente cita disponible (secuencia estricta).
--
-- EJECUCION:
--   Local (XAMPP):  mysql -u root moovaclinic_db < migration_v3.sql
--   phpMyAdmin:     seleccionar la base correcta (moovacloud_db en
--                   produccion) y ejecutar todo el archivo.
--   Es retrocompatible: solo CREA tabla y PROCEDUREs nuevos.
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;
SET time_zone = '+00:00';

-- ============================================================
-- PARTE A: Tabla rehabilitaciones
-- ============================================================

CREATE TABLE IF NOT EXISTS `rehabilitaciones` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `paciente_id` int(11) NOT NULL,
  `numero_cita` int(11) NOT NULL COMMENT 'Cita 1, Cita 2, ... por paciente (secuencia estricta)',
  `dni` varchar(20) NOT NULL COMMENT 'DNI del paciente (denormalizado para busquedas)',
  `nombres` varchar(200) DEFAULT NULL,
  `apellidos` varchar(200) DEFAULT NULL,
  `fecha_cita` date NOT NULL,
  `hora_ingreso` time DEFAULT NULL,
  `hora_salida` time DEFAULT NULL,
  `motivo_diagnostico` text DEFAULT NULL,
  `area_tipo` varchar(150) DEFAULT NULL,
  `profesional` varchar(200) DEFAULT NULL,
  `observaciones` text DEFAULT NULL,
  `tratamiento` text DEFAULT NULL,
  `evolucion` text DEFAULT NULL,
  `estado` varchar(50) NOT NULL DEFAULT 'registrada',
  `proxima_cita` date DEFAULT NULL,
  `fecha_registro` datetime NOT NULL DEFAULT current_timestamp(),
  `registrado_por` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_rehab_paciente_cita` (`paciente_id`,`numero_cita`),
  KEY `idx_rehab_dni` (`dni`),
  KEY `idx_rehab_paciente` (`paciente_id`),
  CONSTRAINT `fk_rehab_paciente` FOREIGN KEY (`paciente_id`)
    REFERENCES `pacientes` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_rehab_registrado_por` FOREIGN KEY (`registrado_por`)
    REFERENCES `usuarios` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- ============================================================
-- PARTE B: Procedimientos almacenados
-- ============================================================

DELIMITER $$

-- Lista todas las rehabilitaciones de un paciente (0..n, ordenadas)
DROP PROCEDURE IF EXISTS `sp_listar_rehabilitaciones`$$
CREATE PROCEDURE `sp_listar_rehabilitaciones`(IN p_paciente_id INT)
BEGIN
    SELECT * FROM rehabilitaciones
    WHERE paciente_id = p_paciente_id
    ORDER BY numero_cita ASC;
END$$

-- Proxima cita disponible + total de citas registradas del paciente
DROP PROCEDURE IF EXISTS `sp_proxima_cita_rehab`$$
CREATE PROCEDURE `sp_proxima_cita_rehab`(IN p_paciente_id INT)
BEGIN
    SELECT COALESCE(MAX(numero_cita), 0) + 1 AS proxima_cita,
           COUNT(*) AS total_citas
    FROM rehabilitaciones
    WHERE paciente_id = p_paciente_id;
END$$

-- Registra la SIGUIENTE cita de rehabilitacion del paciente.
-- El numero de cita lo calcula el procedimiento internamente
-- (MAX+1), por lo que el cliente no puede registrar fuera de
-- secuencia ni reutilizar una cita ya registrada.
DROP PROCEDURE IF EXISTS `sp_crear_rehabilitacion`$$
CREATE PROCEDURE `sp_crear_rehabilitacion`(
    IN p_paciente_id INT,
    IN p_dni VARCHAR(20),
    IN p_nombres VARCHAR(200),
    IN p_apellidos VARCHAR(200),
    IN p_fecha_cita DATE,
    IN p_hora_ingreso TIME,
    IN p_hora_salida TIME,
    IN p_motivo_diagnostico TEXT,
    IN p_area_tipo VARCHAR(150),
    IN p_profesional VARCHAR(200),
    IN p_observaciones TEXT,
    IN p_tratamiento TEXT,
    IN p_evolucion TEXT,
    IN p_estado VARCHAR(50),
    IN p_proxima_cita DATE,
    IN p_registrado_por INT
)
BEGIN
    DECLARE v_proximo INT DEFAULT 1;

    SELECT COALESCE(MAX(numero_cita), 0) + 1 INTO v_proximo
    FROM rehabilitaciones
    WHERE paciente_id = p_paciente_id;

    INSERT INTO rehabilitaciones (
        paciente_id, numero_cita, dni, nombres, apellidos,
        fecha_cita, hora_ingreso, hora_salida,
        motivo_diagnostico, area_tipo, profesional,
        observaciones, tratamiento, evolucion,
        estado, proxima_cita, registrado_por
    ) VALUES (
        p_paciente_id, v_proximo, p_dni, p_nombres, p_apellidos,
        p_fecha_cita, p_hora_ingreso, p_hora_salida,
        p_motivo_diagnostico, p_area_tipo, p_profesional,
        p_observaciones, p_tratamiento, p_evolucion,
        COALESCE(NULLIF(p_estado, ''), 'registrada'), p_proxima_cita, p_registrado_por
    );

    SELECT v_proximo AS numero_cita, ROW_COUNT() AS insertadas;
END$$

DELIMITER ;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- VERIFICACION
-- ============================================================
SELECT 'MIGRACION V3 (REHABILITACIONES) COMPLETADA' AS resultado;
DESCRIBE `rehabilitaciones`;
SHOW PROCEDURE STATUS WHERE Db = DATABASE() AND Name LIKE '%rehab';

-- ============ MIGRATION v4 ============


-- ============================================================
-- MOOVA Clinic - Migracion v4 (Pacientes + Rehabilitaciones)
-- ============================================================
-- ADITIVO: no toca tablas ni procedures existentes.
-- Ejecutar: mysql -u root moovacloud_db < migration_v4.sql
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;
SET time_zone = '+00:00';

DELIMITER $$

-- ============================================================
-- PARTE A: Obtener terapeutas activos (catalogo para form rehab)
-- ============================================================

DROP PROCEDURE IF EXISTS `sp_listar_terapeutas_activos`$$
CREATE PROCEDURE `sp_listar_terapeutas_activos`()
BEGIN
    SELECT t.id AS terapeuta_id, u.nombre AS terapeuta_nombre,
           e.nombre AS especialidad
    FROM terapeutas t
    JOIN usuarios u ON t.usuario_id = u.id
    LEFT JOIN especialidades e ON t.especialidad_id = e.id
    WHERE t.activo = 1
    ORDER BY u.nombre;
END$$

-- ============================================================
-- PARTE B: Obtener areas/tipos de rehabilitacion (catalogo)
-- ============================================================

DROP PROCEDURE IF EXISTS `sp_listar_areas_rehabilitacion`$$
CREATE PROCEDURE `sp_listar_areas_rehabilitacion`()
BEGIN
    SELECT id, nombre FROM servicios WHERE activo = 1 ORDER BY nombre;
END$$

-- ============================================================
-- PARTE C: Validar si una cita ya esta registrada (backend check)
-- ============================================================

DROP PROCEDURE IF EXISTS `sp_existe_rehabilitacion_cita`$$
CREATE PROCEDURE `sp_existe_rehabilitacion_cita`(
    IN p_paciente_id INT, IN p_numero_cita INT
)
BEGIN
    SELECT id, numero_cita, estado
    FROM rehabilitaciones
    WHERE paciente_id = p_paciente_id AND numero_cita = p_numero_cita;
END$$

-- ============================================================
-- PARTE D: Resumen de rehabilitaciones (para badges/contadores)
-- ============================================================

DROP PROCEDURE IF EXISTS `sp_resumen_rehabilitaciones`$$
CREATE PROCEDURE `sp_resumen_rehabilitaciones`(IN p_paciente_id INT)
BEGIN
    SELECT COUNT(*) AS total_registradas,
           COALESCE(MAX(numero_cita), 0) AS ultima_cita,
           COALESCE(MAX(numero_cita), 0) + 1 AS proxima_cita_disponible
    FROM rehabilitaciones
    WHERE paciente_id = p_paciente_id;
END$$

DELIMITER ;

SET FOREIGN_KEY_CHECKS = 1;

SELECT 'MIGRACION v4 (PACIENTES + REHABILITACIONES) COMPLETADA' AS resultado;



-- ============ MIGRATION v5 ============


-- ============================================================
-- MOOVA Clinic - Migracion v5 (Historia Clinica en Rehabilitacion)
-- ============================================================
-- MODULO: Admin -> Pacientes -> Registro de Historia Clinica.
--
-- PARTE A: Amplia la tabla `rehabilitaciones` con los campos
--          completos de Historia Clinica (expediente, cama,
--          datos deportivos, motivo de consulta, diagnostico,
--          mecanismo de lesion, tratamientos previos, etc.).
--          Es ADITIVA: no toca columnas existentes. El UNIQUE
--          (paciente_id, numero_cita) se conserva intacto.
--
-- PARTE B: Recrea `sp_crear_rehabilitacion` con la firma
--          extendida y agrega:
--            - sp_obtener_rehabilitacion   (una cita por id)
--            - sp_actualizar_rehabilitacion (edicion conservando numero_cita)
--
-- EJECUCION: importar UNA sola vez sobre moovacloud_db (produccion)
--   o moovaclinic_db (local) DESPUES de migration_v3 y migration_v4.
--   Es idempotente: las columnas se agregan solo si no existen.
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- Procedimiento temporal que agrega las columnas si no existen
DROP PROCEDURE IF EXISTS `migracion_v5_agregar_columnas`;
DELIMITER $$
CREATE PROCEDURE `migracion_v5_agregar_columnas`()
BEGIN
    DECLARE v_db VARCHAR(128);
    SET v_db = DATABASE();

    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'rehabilitaciones'
                     AND COLUMN_NAME = 'numero_expediente') THEN
        ALTER TABLE `rehabilitaciones` ADD COLUMN `numero_expediente` VARCHAR(50) DEFAULT NULL AFTER `numero_cita`;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'rehabilitaciones'
                     AND COLUMN_NAME = 'cama_cubiculo') THEN
        ALTER TABLE `rehabilitaciones` ADD COLUMN `cama_cubiculo` VARCHAR(50) DEFAULT NULL AFTER `numero_expediente`;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'rehabilitaciones'
                     AND COLUMN_NAME = 'edad') THEN
        ALTER TABLE `rehabilitaciones` ADD COLUMN `edad` INT DEFAULT NULL AFTER `apellidos`;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'rehabilitaciones'
                     AND COLUMN_NAME = 'sexo') THEN
        ALTER TABLE `rehabilitaciones` ADD COLUMN `sexo` VARCHAR(10) DEFAULT NULL AFTER `edad`;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'rehabilitaciones'
                     AND COLUMN_NAME = 'fecha_nacimiento') THEN
        ALTER TABLE `rehabilitaciones` ADD COLUMN `fecha_nacimiento` DATE DEFAULT NULL AFTER `sexo`;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'rehabilitaciones'
                     AND COLUMN_NAME = 'domicilio') THEN
        ALTER TABLE `rehabilitaciones` ADD COLUMN `domicilio` VARCHAR(255) DEFAULT NULL AFTER `fecha_nacimiento`;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'rehabilitaciones'
                     AND COLUMN_NAME = 'telefono') THEN
        ALTER TABLE `rehabilitaciones` ADD COLUMN `telefono` VARCHAR(20) DEFAULT NULL AFTER `domicilio`;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'rehabilitaciones'
                     AND COLUMN_NAME = 'email') THEN
        ALTER TABLE `rehabilitaciones` ADD COLUMN `email` VARCHAR(120) DEFAULT NULL AFTER `telefono`;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'rehabilitaciones'
                     AND COLUMN_NAME = 'deporte') THEN
        ALTER TABLE `rehabilitaciones` ADD COLUMN `deporte` VARCHAR(150) DEFAULT NULL AFTER `email`;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'rehabilitaciones'
                     AND COLUMN_NAME = 'posicion') THEN
        ALTER TABLE `rehabilitaciones` ADD COLUMN `posicion` VARCHAR(100) DEFAULT NULL AFTER `deporte`;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'rehabilitaciones'
                     AND COLUMN_NAME = 'antiguedad_practica') THEN
        ALTER TABLE `rehabilitaciones` ADD COLUMN `antiguedad_practica` VARCHAR(50) DEFAULT NULL AFTER `posicion`;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'rehabilitaciones'
                     AND COLUMN_NAME = 'nivel_competitivo') THEN
        ALTER TABLE `rehabilitaciones` ADD COLUMN `nivel_competitivo` VARCHAR(50) DEFAULT NULL AFTER `antiguedad_practica`;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'rehabilitaciones'
                     AND COLUMN_NAME = 'motivo_consulta') THEN
        ALTER TABLE `rehabilitaciones` ADD COLUMN `motivo_consulta` TEXT DEFAULT NULL AFTER `nivel_competitivo`;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'rehabilitaciones'
                     AND COLUMN_NAME = 'diagnostico_medico') THEN
        ALTER TABLE `rehabilitaciones` ADD COLUMN `diagnostico_medico` TEXT DEFAULT NULL AFTER `motivo_consulta`;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'rehabilitaciones'
                     AND COLUMN_NAME = 'mecanismo_lesion') THEN
        ALTER TABLE `rehabilitaciones` ADD COLUMN `mecanismo_lesion` TEXT DEFAULT NULL AFTER `diagnostico_medico`;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'rehabilitaciones'
                     AND COLUMN_NAME = 'tratamientos_previos') THEN
        ALTER TABLE `rehabilitaciones` ADD COLUMN `tratamientos_previos` TEXT DEFAULT NULL AFTER `mecanismo_lesion`;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'rehabilitaciones'
                     AND COLUMN_NAME = 'peso') THEN
        ALTER TABLE `rehabilitaciones` ADD COLUMN `peso` DECIMAL(5,2) DEFAULT NULL AFTER `tratamientos_previos`;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'rehabilitaciones'
                     AND COLUMN_NAME = 'talla') THEN
        ALTER TABLE `rehabilitaciones` ADD COLUMN `talla` DECIMAL(5,2) DEFAULT NULL AFTER `peso`;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'rehabilitaciones'
                     AND COLUMN_NAME = 'antecedentes') THEN
        ALTER TABLE `rehabilitaciones` ADD COLUMN `antecedentes` TEXT DEFAULT NULL AFTER `talla`;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                   WHERE TABLE_SCHEMA = v_db AND TABLE_NAME = 'rehabilitaciones'
                     AND COLUMN_NAME = 'examen_fisico') THEN
        ALTER TABLE `rehabilitaciones` ADD COLUMN `examen_fisico` TEXT DEFAULT NULL AFTER `antecedentes`;
    END IF;
END$$
DELIMITER ;

CALL `migracion_v5_agregar_columnas`();
DROP PROCEDURE IF EXISTS `migracion_v5_agregar_columnas`;

-- ============================================================
-- PARTE B: Procedimientos de lectura/escritura
-- ============================================================

DELIMITER $$

-- Obtener una cita de rehabilitacion por su id (parametro de ruta)
DROP PROCEDURE IF EXISTS `sp_obtener_rehabilitacion`$$
CREATE PROCEDURE `sp_obtener_rehabilitacion`(IN p_id INT)
BEGIN
    SELECT * FROM rehabilitaciones WHERE id = p_id LIMIT 1;
END$$

-- Registra la SIGUIENTE cita de rehabilitacion con historia clinica.
-- El numero de cita lo calcula el procedimiento internamente
-- (MAX+1): el cliente nunca elige la cita.
DROP PROCEDURE IF EXISTS `sp_crear_rehabilitacion`$$
CREATE PROCEDURE `sp_crear_rehabilitacion`(
    IN p_paciente_id INT,
    IN p_dni VARCHAR(20),
    IN p_nombres VARCHAR(200),
    IN p_apellidos VARCHAR(200),
    IN p_fecha_cita DATE,
    IN p_hora_ingreso TIME,
    IN p_hora_salida TIME,
    IN p_numero_expediente VARCHAR(50),
    IN p_cama_cubiculo VARCHAR(50),
    IN p_edad INT,
    IN p_sexo VARCHAR(10),
    IN p_fecha_nacimiento DATE,
    IN p_domicilio VARCHAR(255),
    IN p_telefono VARCHAR(20),
    IN p_email VARCHAR(120),
    IN p_deporte VARCHAR(150),
    IN p_posicion VARCHAR(100),
    IN p_antiguedad_practica VARCHAR(50),
    IN p_nivel_competitivo VARCHAR(50),
    IN p_motivo_consulta TEXT,
    IN p_diagnostico_medico TEXT,
    IN p_mecanismo_lesion TEXT,
    IN p_tratamientos_previos TEXT,
    IN p_area_tipo VARCHAR(150),
    IN p_profesional VARCHAR(200),
    IN p_peso DECIMAL(5,2),
    IN p_talla DECIMAL(5,2),
    IN p_antecedentes TEXT,
    IN p_examen_fisico TEXT,
    IN p_observaciones TEXT,
    IN p_tratamiento TEXT,
    IN p_evolucion TEXT,
    IN p_estado VARCHAR(50),
    IN p_proxima_cita DATE,
    IN p_registrado_por INT
)
BEGIN
    DECLARE v_proximo INT DEFAULT 1;

    SELECT COALESCE(MAX(numero_cita), 0) + 1 INTO v_proximo
    FROM rehabilitaciones
    WHERE paciente_id = p_paciente_id;

    INSERT INTO rehabilitaciones (
        paciente_id, numero_cita, dni, nombres, apellidos,
        fecha_cita, hora_ingreso, hora_salida,
        numero_expediente, cama_cubiculo, edad, sexo, fecha_nacimiento,
        domicilio, telefono, email,
        deporte, posicion, antiguedad_practica, nivel_competitivo,
        motivo_consulta, diagnostico_medico, mecanismo_lesion, tratamientos_previos,
        motivo_diagnostico,
        area_tipo, profesional, peso, talla, antecedentes, examen_fisico,
        observaciones, tratamiento, evolucion,
        estado, proxima_cita, registrado_por
    ) VALUES (
        p_paciente_id, v_proximo, p_dni, p_nombres, p_apellidos,
        p_fecha_cita, p_hora_ingreso, p_hora_salida,
        NULLIF(p_numero_expediente, ''), NULLIF(p_cama_cubiculo, ''), p_edad,
        NULLIF(p_sexo, ''), p_fecha_nacimiento, NULLIF(p_domicilio, ''),
        NULLIF(p_telefono, ''), NULLIF(p_email, ''),
        NULLIF(p_deporte, ''), NULLIF(p_posicion, ''), NULLIF(p_antiguedad_practica, ''),
        NULLIF(p_nivel_competitivo, ''),
        NULLIF(p_motivo_consulta, ''), NULLIF(p_diagnostico_medico, ''),
        NULLIF(p_mecanismo_lesion, ''), NULLIF(p_tratamientos_previos, ''),
        NULLIF(p_motivo_consulta, ''),
        NULLIF(p_area_tipo, ''), NULLIF(p_profesional, ''), p_peso, p_talla,
        NULLIF(p_antecedentes, ''), NULLIF(p_examen_fisico, ''),
        NULLIF(p_observaciones, ''), NULLIF(p_tratamiento, ''), NULLIF(p_evolucion, ''),
        COALESCE(NULLIF(p_estado, ''), 'registrada'), p_proxima_cita, p_registrado_por
    );

    SELECT v_proximo AS numero_cita, ROW_COUNT() AS insertadas;
END$$

-- Edita una cita existente. NUNCA modifica numero_cita ni el vÃ­nculo
-- con el paciente: solo los datos propios de la historia clinica.
DROP PROCEDURE IF EXISTS `sp_actualizar_rehabilitacion`$$
CREATE PROCEDURE `sp_actualizar_rehabilitacion`(
    IN p_id INT,
    IN p_fecha_cita DATE,
    IN p_hora_ingreso TIME,
    IN p_hora_salida TIME,
    IN p_numero_expediente VARCHAR(50),
    IN p_cama_cubiculo VARCHAR(50),
    IN p_edad INT,
    IN p_sexo VARCHAR(10),
    IN p_fecha_nacimiento DATE,
    IN p_domicilio VARCHAR(255),
    IN p_telefono VARCHAR(20),
    IN p_email VARCHAR(120),
    IN p_deporte VARCHAR(150),
    IN p_posicion VARCHAR(100),
    IN p_antiguedad_practica VARCHAR(50),
    IN p_nivel_competitivo VARCHAR(50),
    IN p_motivo_consulta TEXT,
    IN p_diagnostico_medico TEXT,
    IN p_mecanismo_lesion TEXT,
    IN p_tratamientos_previos TEXT,
    IN p_area_tipo VARCHAR(150),
    IN p_profesional VARCHAR(200),
    IN p_peso DECIMAL(5,2),
    IN p_talla DECIMAL(5,2),
    IN p_antecedentes TEXT,
    IN p_examen_fisico TEXT,
    IN p_observaciones TEXT,
    IN p_tratamiento TEXT,
    IN p_evolucion TEXT,
    IN p_estado VARCHAR(50),
    IN p_proxima_cita DATE,
    IN p_registrado_por INT
)
BEGIN
    UPDATE rehabilitaciones
    SET fecha_cita = IF(p_fecha_cita IS NOT NULL, p_fecha_cita, fecha_cita),
        hora_ingreso = IF(p_hora_ingreso IS NOT NULL, p_hora_ingreso, hora_ingreso),
        hora_salida = IF(p_hora_salida IS NOT NULL, p_hora_salida, hora_salida),
        numero_expediente = IF(p_numero_expediente IS NOT NULL, p_numero_expediente, numero_expediente),
        cama_cubiculo = IF(p_cama_cubiculo IS NOT NULL, p_cama_cubiculo, cama_cubiculo),
        edad = IF(p_edad IS NOT NULL, p_edad, edad),
        sexo = IF(p_sexo IS NOT NULL, p_sexo, sexo),
        fecha_nacimiento = IF(p_fecha_nacimiento IS NOT NULL, p_fecha_nacimiento, fecha_nacimiento),
        domicilio = IF(p_domicilio IS NOT NULL, p_domicilio, domicilio),
        telefono = IF(p_telefono IS NOT NULL, p_telefono, telefono),
        email = IF(p_email IS NOT NULL, p_email, email),
        deporte = IF(p_deporte IS NOT NULL, p_deporte, deporte),
        posicion = IF(p_posicion IS NOT NULL, p_posicion, posicion),
        antiguedad_practica = IF(p_antiguedad_practica IS NOT NULL, p_antiguedad_practica, antiguedad_practica),
        nivel_competitivo = IF(p_nivel_competitivo IS NOT NULL, p_nivel_competitivo, nivel_competitivo),
        motivo_consulta = IF(p_motivo_consulta IS NOT NULL, p_motivo_consulta, motivo_consulta),
        diagnostico_medico = IF(p_diagnostico_medico IS NOT NULL, p_diagnostico_medico, diagnostico_medico),
        mecanismo_lesion = IF(p_mecanismo_lesion IS NOT NULL, p_mecanismo_lesion, mecanismo_lesion),
        tratamientos_previos = IF(p_tratamientos_previos IS NOT NULL, p_tratamientos_previos, tratamientos_previos),
        area_tipo = IF(p_area_tipo IS NOT NULL, p_area_tipo, area_tipo),
        profesional = IF(p_profesional IS NOT NULL, p_profesional, profesional),
        peso = IF(p_peso IS NOT NULL, p_peso, peso),
        talla = IF(p_talla IS NOT NULL, p_talla, talla),
        antecedentes = IF(p_antecedentes IS NOT NULL, p_antecedentes, antecedentes),
        examen_fisico = IF(p_examen_fisico IS NOT NULL, p_examen_fisico, examen_fisico),
        observaciones = IF(p_observaciones IS NOT NULL, p_observaciones, observaciones),
        tratamiento = IF(p_tratamiento IS NOT NULL, p_tratamiento, tratamiento),
        evolucion = IF(p_evolucion IS NOT NULL, p_evolucion, evolucion),
        estado = IF(p_estado IS NOT NULL, p_estado, estado),
        proxima_cita = IF(p_proxima_cita IS NOT NULL, p_proxima_cita, proxima_cita),
        registrado_por = IF(p_registrado_por IS NOT NULL, p_registrado_por, registrado_por)
    WHERE id = p_id;

    SELECT ROW_COUNT() AS actualizadas;
END$$

DELIMITER ;

SET FOREIGN_KEY_CHECKS = 1;

SELECT 'MIGRACION v5 (HISTORIA CLINICA EN REHABILITACION) COMPLETADA' AS resultado;
