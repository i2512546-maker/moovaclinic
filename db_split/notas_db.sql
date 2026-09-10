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

CREATE DATABASE IF NOT EXISTS `moovacloud_notas` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE `moovacloud_notas`;

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