-- ============================================================
-- Evaluacion inicial: servicio visible, precio S/ 55 y una sola
-- reserva/evaluacion por paciente (DNI resuelto a pacientes.id).
--
-- IMPORTANTE:
-- 1) Hacer backup de ambas bases antes de ejecutar.
-- 2) Revisar duplicados existentes antes de crear uq_evaluacion_paciente:
--      SELECT paciente_id, COUNT(*) total
--      FROM evaluaciones_iniciales GROUP BY paciente_id HAVING COUNT(*) > 1;
--    Si devuelve filas, conciliarlas manualmente; esta migracion no borra datos.
-- 3) Ejecutar en phpMyAdmin con permisos para ALTER/CREATE PROCEDURE.
-- ============================================================

USE moovacloud_pacientes;

-- Si el catalogo ya tiene Evaluacion Inicial, la reactiva y normaliza.
UPDATE servicios
SET descripcion = 'Primera valoracion funcional y clinica antes de iniciar el tratamiento',
    duracion_min = 30,
    precio = 55.00,
    activo = 1
WHERE LOWER(nombre) IN ('evaluacion inicial', 'evaluación inicial');

-- Si no existe, la agrega con el siguiente ID disponible.
INSERT INTO servicios (nombre, descripcion, duracion_min, precio, activo)
SELECT
    'Evaluacion Inicial',
    'Primera valoracion funcional y clinica antes de iniciar el tratamiento',
    30, 55.00, 1
WHERE NOT EXISTS (
    SELECT 1 FROM servicios
    WHERE LOWER(nombre) IN ('evaluacion inicial', 'evaluación inicial')
);

ALTER TABLE evaluaciones_iniciales
    ADD UNIQUE KEY uq_evaluacion_paciente (paciente_id);

DROP PROCEDURE IF EXISTS sp_existe_evaluacion_paciente;
DELIMITER $$
CREATE PROCEDURE sp_existe_evaluacion_paciente(IN p_paciente_id INT)
BEGIN
    SELECT 1 AS existe
    FROM evaluaciones_iniciales
    WHERE paciente_id = p_paciente_id
    LIMIT 1;
END$$
DELIMITER ;

-- ------------------------------------------------------------
-- La reserva de evaluacion tambien queda marcada en historial_citas.
-- La columna generada + UNIQUE bloquea incluso solicitudes simultaneas.
-- ------------------------------------------------------------

USE moovacloud_citas;

ALTER TABLE historial_citas
    ADD COLUMN es_evaluacion_inicial TINYINT(1) NOT NULL DEFAULT 0
        AFTER estado,
    ADD COLUMN evaluacion_inicial_paciente_id INT
        GENERATED ALWAYS AS (
            CASE WHEN es_evaluacion_inicial = 1 THEN paciente_id ELSE NULL END
        ) STORED
        AFTER es_evaluacion_inicial,
    ADD UNIQUE KEY uq_evaluacion_inicial_paciente (evaluacion_inicial_paciente_id);

DROP PROCEDURE IF EXISTS sp_existe_evaluacion_inicial;
DROP PROCEDURE IF EXISTS sp_crear_cita_evaluacion;
DROP PROCEDURE IF EXISTS sp_crear_cita_evaluacion_pendiente_pago;

DELIMITER $$
CREATE PROCEDURE sp_existe_evaluacion_inicial(IN p_paciente_id INT)
BEGIN
    SELECT 1 AS existe
    FROM historial_citas
    WHERE paciente_id = p_paciente_id
      AND es_evaluacion_inicial = 1
    LIMIT 1;
END$$

CREATE PROCEDURE sp_crear_cita_evaluacion(
    IN p_paciente_id INT, IN p_terapeuta_id INT, IN p_servicio_id INT,
    IN p_fecha DATETIME, IN p_hora TIME
)
BEGIN
    INSERT INTO historial_citas (
        paciente_id, terapeuta_id, servicio_id, fecha_cita, hora_cita,
        estado, es_evaluacion_inicial, creado_en, actualizado_en
    )
    VALUES (
        p_paciente_id, p_terapeuta_id, p_servicio_id, p_fecha, p_hora,
        'programada', 1, NOW(), NOW()
    );
    SELECT LAST_INSERT_ID() AS id;
END$$

CREATE PROCEDURE sp_crear_cita_evaluacion_pendiente_pago(
    IN p_paciente_id INT, IN p_terapeuta_id INT, IN p_servicio_id INT,
    IN p_fecha DATETIME, IN p_hora TIME
)
BEGIN
    INSERT INTO historial_citas (
        paciente_id, terapeuta_id, servicio_id, fecha_cita, hora_cita,
        estado, es_evaluacion_inicial, creado_en, actualizado_en
    )
    VALUES (
        p_paciente_id, p_terapeuta_id, p_servicio_id, p_fecha, p_hora,
        'pendiente_pago', 1, NOW(), NOW()
    );
    SELECT LAST_INSERT_ID() AS id;
END$$
DELIMITER ;

-- ============================================================
-- Fin de migracion. Precio base S/ 55.00 (rango permitido 50-60).
-- ============================================================
