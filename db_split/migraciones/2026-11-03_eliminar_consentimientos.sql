-- MOOVA Clinic: retirar la funcionalidad de consentimientos no utilizada.
-- Ejecutar una sola vez en la base de datos real configurada en DB_NAME.
-- Realizar una copia de seguridad antes de ejecutar.

-- Retirar la FK si existe para poder eliminar la tabla.
SET @fk_consent_exists = (
    SELECT COUNT(*)
    FROM information_schema.TABLE_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE()
      AND TABLE_NAME = 'consentimientos'
      AND CONSTRAINT_NAME = 'fk_consent_paciente'
      AND CONSTRAINT_TYPE = 'FOREIGN KEY'
);

SET @drop_fk_sql = IF(
    @fk_consent_exists > 0,
    'ALTER TABLE consentimientos DROP FOREIGN KEY fk_consent_paciente',
    'SELECT 1'
);
PREPARE drop_fk_stmt FROM @drop_fk_sql;
EXECUTE drop_fk_stmt;
DEALLOCATE PREPARE drop_fk_stmt;

-- Eliminar tabla y procedimientos almacenados asociados.
DROP TABLE IF EXISTS consentimientos;
DROP PROCEDURE IF EXISTS sp_listar_consentimientos;
DROP PROCEDURE IF EXISTS sp_crear_consentimiento;
