-- Índices para las consultas frecuentes de agenda y KPIs.
-- Idempotente: crea cada índice solo si aún no existe.
-- Ejecutar en la base configurada por DB_NAME.

SET @existe_idx_terapeuta_fecha = (
    SELECT COUNT(*)
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'historial_citas'
      AND index_name = 'idx_terapeuta_fecha'
);
SET @sql_idx_terapeuta_fecha = IF(
    @existe_idx_terapeuta_fecha = 0,
    'ALTER TABLE historial_citas ADD INDEX idx_terapeuta_fecha (terapeuta_id, fecha_cita)',
    'SELECT 1'
);
PREPARE stmt_idx_terapeuta_fecha FROM @sql_idx_terapeuta_fecha;
EXECUTE stmt_idx_terapeuta_fecha;
DEALLOCATE PREPARE stmt_idx_terapeuta_fecha;

SET @existe_idx_terapeuta_estado_paciente = (
    SELECT COUNT(*)
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'historial_citas'
      AND index_name = 'idx_terapeuta_estado_paciente'
);
SET @sql_idx_terapeuta_estado_paciente = IF(
    @existe_idx_terapeuta_estado_paciente = 0,
    'ALTER TABLE historial_citas ADD INDEX idx_terapeuta_estado_paciente (terapeuta_id, estado, paciente_id)',
    'SELECT 1'
);
PREPARE stmt_idx_terapeuta_estado_paciente FROM @sql_idx_terapeuta_estado_paciente;
EXECUTE stmt_idx_terapeuta_estado_paciente;
DEALLOCATE PREPARE stmt_idx_terapeuta_estado_paciente;

SET @existe_idx_fecha_pago = (
    SELECT COUNT(*)
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'pagos'
      AND index_name = 'idx_fecha'
);
SET @sql_idx_fecha_pago = IF(
    @existe_idx_fecha_pago = 0,
    'ALTER TABLE pagos ADD INDEX idx_fecha (fecha_pago)',
    'SELECT 1'
);
PREPARE stmt_idx_fecha_pago FROM @sql_idx_fecha_pago;
EXECUTE stmt_idx_fecha_pago;
DEALLOCATE PREPARE stmt_idx_fecha_pago;
