-- ============================================================
-- MOOVA Clinic - Reset de desarrollo
-- Limpia datos de prueba y reinicia contador de IDs.
-- SOLO para entorno de desarrollo.
-- ============================================================

SET FOREIGN_KEY_CHECKS = 0;

DELETE FROM moovacloud_notas.notas_clinicas;
DELETE FROM moovacloud_pagos.pagos;
DELETE FROM moovacloud_citas.historial_citas;
DELETE FROM moovacloud_pacientes.consentimientos;
DELETE FROM moovacloud_pacientes.evaluaciones_iniciales;
DELETE FROM moovacloud_pacientes.opiniones;
DELETE FROM moovacloud_pacientes.pacientes;
DELETE FROM moovacloud_auth.usuarios;

ALTER TABLE moovacloud_notas.notas_clinicas AUTO_INCREMENT = 1;
ALTER TABLE moovacloud_pagos.pagos AUTO_INCREMENT = 1;
ALTER TABLE moovacloud_citas.historial_citas AUTO_INCREMENT = 1;
ALTER TABLE moovacloud_pacientes.consentimientos AUTO_INCREMENT = 1;
ALTER TABLE moovacloud_pacientes.evaluaciones_iniciales AUTO_INCREMENT = 1;
ALTER TABLE moovacloud_pacientes.opiniones AUTO_INCREMENT = 1;
ALTER TABLE moovacloud_pacientes.pacientes AUTO_INCREMENT = 1;
ALTER TABLE moovacloud_auth.usuarios AUTO_INCREMENT = 1;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- Observación importante:
-- Si hay más tablas hijas en otras bases, añádelas aquí.
-- ============================================================
