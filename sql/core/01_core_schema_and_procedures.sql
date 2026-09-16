-- ============================================================
-- MOOVA Clinic - SQL Core
-- Scripts válidos y necesarios para la app actual.
-- ============================================================

DELIMITER $$

-- ============================================================
-- PACIENTES
-- ============================================================

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

DROP PROCEDURE IF EXISTS `sp_obtener_paciente_id_dni`$$
CREATE PROCEDURE `sp_obtener_paciente_id_dni`(IN p_dni VARCHAR(20))
BEGIN
    SELECT id FROM pacientes WHERE dni = p_dni;
END$$

DROP PROCEDURE IF EXISTS `sp_listar_servicios`$$
CREATE PROCEDURE `sp_listar_servicios`()
BEGIN
    SELECT * FROM servicios WHERE activo = 1 ORDER BY nombre;
END$$

-- ============================================================
-- CITAS
-- ============================================================

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

DROP PROCEDURE IF EXISTS `sp_detalle_cita`$$
CREATE PROCEDURE `sp_detalle_cita`(IN p_cita_id INT)
BEGIN
    SELECT h.*, p.nombre, p.apellido, p.dni, p.telefono,
           u.nombre AS terapeuta, e.nombre AS Especialidad
    FROM historial_citas h
    JOIN pacientes p ON h.paciente_id = p.id
    JOIN terapeutas t ON h.terapeuta_id = t.id
    JOIN usuarios u ON t.usuario_id = u.id
    LEFT JOIN especialidades e ON t.especialidad_id = e.id
    WHERE h.id = p_cita_id;
END$$

DROP PROCEDURE IF EXISTS `sp_listar_citas`$$
CREATE PROCEDURE `sp_listar_citas`(
    IN p_estado VARCHAR(20), IN p_dni VARCHAR(20), IN p_fecha DATETIME, IN p_medico_id INT
)
BEGIN
    SELECT h.id, h.fecha_cita, h.estado, h.descripcion, h.hora_cita,
           p.nombre, p.apellido, p.dni, p.telefono,
           u.nombre AS terapeuta, e.nombre AS Especialidad, h.terapeuta_id
    FROM historial_citas h
    JOIN pacientes p ON h.paciente_id = p.id
    JOIN terapeutas t ON h.terapeuta_id = t.id
    JOIN usuarios u ON t.usuario_id = u.id
    LEFT JOIN especialidades e ON t.especialidad_id = e.id
    WHERE h.estado = p_estado
      AND (p_dni IS NULL OR p.dni = p_dni)
      AND (p_fecha IS NULL OR h.fecha_cita = p_fecha)
      AND (p_medico_id IS NULL OR h.terapeuta_id = p_medico_id)
    ORDER BY h.fecha_cita ASC;
END$$

DROP PROCEDURE IF EXISTS `sp_modificar_cita`$$
CREATE PROCEDURE `sp_modificar_cita`(IN p_cita_id INT, IN p_fecha DATETIME, IN p_medico_id INT)
BEGIN
    UPDATE historial_citas SET fecha_cita = p_fecha, terapeuta_id = p_medico_id
    WHERE id = p_cita_id AND estado = 'programada';
    SELECT ROW_COUNT() AS actualizadas;
END$$

DROP PROCEDURE IF EXISTS `sp_cancelar_cita`$$
CREATE PROCEDURE `sp_cancelar_cita`(IN p_cita_id INT)
BEGIN
    DECLARE v_afectadas INT DEFAULT 0;
    UPDATE historial_citas SET estado = 'cancelada'
    WHERE id = p_cita_id AND estado = 'programada';
    SET v_afectadas = ROW_COUNT();
    UPDATE pagos SET estado_pago = 'cancelado'
    WHERE cita_id = p_cita_id AND estado_pago = 'pendiente';
    SELECT v_afectadas AS actualizadas;
END$$

-- ============================================================
-- PAGOS
-- ============================================================

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

DROP PROCEDURE IF EXISTS `sp_obtener_pago`$$
CREATE PROCEDURE `sp_obtener_pago`(IN p_cita_id INT)
BEGIN
    SELECT * FROM pagos WHERE cita_id = p_cita_id;
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_pago_pendiente`$$
CREATE PROCEDURE `sp_obtener_pago_pendiente`(IN p_cita_id INT)
BEGIN
    SELECT h.id, p.nombre, p.apellido, u.nombre AS terapeuta, e.nombre AS Especialidad,
           pg.monto, pg.metodo_pago, pg.estado_pago, pg.referencia
    FROM historial_citas h
    JOIN pacientes p ON h.paciente_id = p.id
    JOIN terapeutas t ON h.terapeuta_id = t.id
    JOIN usuarios u ON t.usuario_id = u.id
    LEFT JOIN especialidades e ON t.especialidad_id = e.id
    LEFT JOIN pagos pg ON pg.cita_id = h.id
    WHERE h.id = p_cita_id;
END$$

-- ============================================================
-- NOTAS
-- ============================================================

DROP PROCEDURE IF EXISTS `sp_listar_notas`$$
CREATE PROCEDURE `sp_listar_notas`(IN p_cita_id INT)
BEGIN
    SELECT nc.*, u.nombre AS autor
    FROM notas_clinicas nc
    LEFT JOIN terapeutas t ON nc.terapeuta_id = t.id
    LEFT JOIN usuarios u ON t.usuario_id = u.id
    WHERE nc.cita_id = p_cita_id
    ORDER BY nc.fecha_creacion DESC;
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_paciente_id_cita`$$
CREATE PROCEDURE `sp_obtener_paciente_id_cita`(IN p_cita_id INT)
BEGIN
    SELECT paciente_id FROM historial_citas WHERE id = p_cita_id;
END$$

DELIMITER ;

-- ============================================================
-- FIN
-- ============================================================
