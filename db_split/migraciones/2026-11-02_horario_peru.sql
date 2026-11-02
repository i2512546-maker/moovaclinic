-- ============================================================
-- MIGRACION: unificar timestamps de MOOVA Clinic en horario Peru
-- Fecha: 2026-11-02
-- Base: moovacloud_database (Railway)
--
-- Ejecutar una vez en Railway MySQL. Es idempotente.
-- Las conexiones de la aplicacion tambien fijan SESSION time_zone=-05:00.
-- Estos procedimientos dejan de usar UTC_TIMESTAMP() para que los
-- DATETIME se guarden con la hora civil de Peru.
-- ============================================================

USE moovacloud_database;
DELIMITER $$

DROP PROCEDURE IF EXISTS sp_crear_cita$$
CREATE PROCEDURE sp_crear_cita(
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
        NOW(), NOW()
    );
    SELECT LAST_INSERT_ID() AS id;
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
        'pendiente_pago', NOW(), NOW()
    );
    SELECT LAST_INSERT_ID() AS id;
END$$

DROP PROCEDURE IF EXISTS sp_confirmar_cita_pago$$
CREATE PROCEDURE sp_confirmar_cita_pago(IN p_cita_id INT)
BEGIN
    UPDATE historial_citas
    SET estado = 'programada', actualizado_en = NOW()
    WHERE id = p_cita_id AND estado = 'pendiente_pago';
    SELECT ROW_COUNT() AS actualizadas;
END$$

DROP PROCEDURE IF EXISTS sp_modificar_cita$$
CREATE PROCEDURE sp_modificar_cita(
    IN p_cita_id INT, IN p_fecha DATETIME, IN p_medico_id INT, IN p_hora TIME
)
BEGIN
    UPDATE historial_citas
    SET fecha_cita = p_fecha,
        hora_cita = p_hora,
        terapeuta_id = p_medico_id,
        actualizado_en = NOW()
    WHERE id = p_cita_id AND estado = 'programada';
    SELECT ROW_COUNT() AS actualizadas;
END$$

DROP PROCEDURE IF EXISTS sp_completar_cita$$
CREATE PROCEDURE sp_completar_cita(IN p_historial_id INT, IN p_descripcion TEXT)
BEGIN
    UPDATE historial_citas
    SET descripcion = p_descripcion, estado = 'completada',
        actualizado_en = NOW()
    WHERE id = p_historial_id;
END$$

DROP PROCEDURE IF EXISTS sp_cancelar_cita$$
CREATE PROCEDURE sp_cancelar_cita(IN p_cita_id INT)
BEGIN
    DECLARE v_afectadas INT DEFAULT 0;
    UPDATE historial_citas
    SET estado = 'cancelada', actualizado_en = NOW()
    WHERE id = p_cita_id AND estado = 'programada';
    SET v_afectadas = ROW_COUNT();
    SELECT v_afectadas AS actualizadas;
END$$

DROP PROCEDURE IF EXISTS sp_cancelar_cita_pago_vencido$$
CREATE PROCEDURE sp_cancelar_cita_pago_vencido(IN p_cita_id INT)
BEGIN
    UPDATE historial_citas
    SET estado = 'cancelada',
        descripcion = CONCAT_WS(
            ' | ', NULLIF(TRIM(descripcion), ''), 'pago vencido o no iniciado'
        ),
        actualizado_en = NOW()
    WHERE id = p_cita_id AND estado IN ('pendiente_pago','programada');
    SELECT ROW_COUNT() AS actualizadas;
END$$

DROP PROCEDURE IF EXISTS sp_marcar_recordatorio_enviado$$
CREATE PROCEDURE sp_marcar_recordatorio_enviado(IN p_cita_id INT)
BEGIN
    UPDATE historial_citas
    SET recordatorio_enviado = 1, actualizado_en = NOW()
    WHERE id = p_cita_id AND COALESCE(recordatorio_enviado, 0) = 0;
    SELECT ROW_COUNT() AS marcadas;
END$$

DROP PROCEDURE IF EXISTS sp_desmarcar_recordatorio$$
CREATE PROCEDURE sp_desmarcar_recordatorio(IN p_cita_id INT)
BEGIN
    UPDATE historial_citas
    SET recordatorio_enviado = 0, actualizado_en = NOW()
    WHERE id = p_cita_id;
    SELECT ROW_COUNT() AS desmarcadas;
END$$

DELIMITER ;
-- ============================================================
-- FIN MIGRACION HORARIO PERU
-- ============================================================
