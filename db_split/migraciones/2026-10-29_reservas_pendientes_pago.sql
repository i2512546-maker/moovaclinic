-- MOOVA Clinic: mantener las reservas de pago fuera de la agenda hasta confirmar.
-- Ejecutar una sola vez sobre la base moovacloud_citas existente.
DELIMITER $$

ALTER TABLE historial_citas
    MODIFY COLUMN estado ENUM(
        'pendiente_pago','programada','confirmada','cancelada','completada','no_asistio'
    ) NOT NULL DEFAULT 'programada'$$

DROP PROCEDURE IF EXISTS sp_medico_disponible$$
CREATE PROCEDURE sp_medico_disponible(
    IN p_medico_id INT, IN p_fecha DATETIME, IN p_excluir_cita_id INT
)
BEGIN
    SELECT COUNT(*) AS n
    FROM historial_citas
    WHERE terapeuta_id = p_medico_id
      AND fecha_cita = p_fecha
      AND estado IN ('pendiente_pago','programada','confirmada')
      AND (p_excluir_cita_id IS NULL OR id <> p_excluir_cita_id);
END$$

DROP PROCEDURE IF EXISTS sp_crear_cita_pendiente_pago$$
CREATE PROCEDURE sp_crear_cita_pendiente_pago(
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

DROP PROCEDURE IF EXISTS sp_confirmar_cita_pago$$
CREATE PROCEDURE sp_confirmar_cita_pago(IN p_cita_id INT)
BEGIN
    UPDATE historial_citas
    SET estado = 'programada', actualizado_en = UTC_TIMESTAMP()
    WHERE id = p_cita_id AND estado = 'pendiente_pago';
    SELECT ROW_COUNT() AS actualizadas;
END$$

DROP PROCEDURE IF EXISTS sp_cancelar_cita_pago_vencido$$
CREATE PROCEDURE sp_cancelar_cita_pago_vencido(IN p_cita_id INT)
BEGIN
    UPDATE historial_citas
    SET estado = 'cancelada',
        descripcion = CONCAT_WS(' | ', NULLIF(TRIM(descripcion), ''), 'pago vencido o no iniciado'),
        actualizado_en = UTC_TIMESTAMP()
    WHERE id = p_cita_id AND estado IN ('pendiente_pago','programada');
    SELECT ROW_COUNT() AS actualizadas;
END$$

DELIMITER ;
