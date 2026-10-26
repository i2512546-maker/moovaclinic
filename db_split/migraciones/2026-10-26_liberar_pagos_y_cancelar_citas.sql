-- ============================================================
-- MIGRACION: retry-safe release of expired payments and their appointments
-- Fecha: 2026-10-26
--
-- Run this file once in the Railway MySQL instance before deployment.
-- Re-running is safe. Each schema is selected explicitly and the
-- column/procedures are safe to recreate. Requires access to both moovacloud_pagos and
-- moovacloud_citas.
-- ============================================================

USE moovacloud_pagos;

SET @add_cita_liberada = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE()
       AND TABLE_NAME = 'pagos'
       AND COLUMN_NAME = 'cita_liberada') = 0,
    'ALTER TABLE pagos ADD COLUMN cita_liberada TINYINT(1) NOT NULL DEFAULT 0',
    'SELECT 1'
);
PREPARE add_cita_liberada_stmt FROM @add_cita_liberada;
EXECUTE add_cita_liberada_stmt;
DEALLOCATE PREPARE add_cita_liberada_stmt;

DELIMITER $$

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

USE moovacloud_citas$$

DROP PROCEDURE IF EXISTS `sp_cancelar_cita_pago_vencido`$$
CREATE PROCEDURE `sp_cancelar_cita_pago_vencido`(IN p_cita_id INT)
BEGIN
    UPDATE historial_citas
    SET estado = 'cancelada',
        descripcion = CONCAT_WS(
            ' | ', NULLIF(TRIM(descripcion), ''), 'pago vencido'
        ),
        actualizado_en = UTC_TIMESTAMP()
    WHERE id = p_cita_id AND estado = 'programada';
    SELECT ROW_COUNT() AS actualizadas;
END$$

DELIMITER ;

-- ============================================================
-- FIN 2026-10-26_liberar_pagos_y_cancelar_citas.sql
-- ============================================================
