

DELIMITER $$

-- ============================================================
-- PACIENTES  (services/pacientes_service/routes.py)
-- ============================================================

DROP PROCEDURE IF EXISTS `sp_listar_pacientes`$$
CREATE PROCEDURE `sp_listar_pacientes`()
BEGIN
    SELECT p.*,
           (SELECT COUNT(*) FROM historial_citas WHERE paciente_id = p.id) AS total_citas,
           (SELECT MAX(fecha_cita) FROM historial_citas WHERE paciente_id = p.id) AS ultima_cita
    FROM pacientes p
    ORDER BY p.apellido ASC;
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_paciente_por_dni`$$
CREATE PROCEDURE `sp_obtener_paciente_por_dni`(IN p_dni VARCHAR(20))
BEGIN
    SELECT * FROM pacientes WHERE dni = p_dni;
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_historial_paciente`$$
CREATE PROCEDURE `sp_obtener_historial_paciente`(IN p_paciente_id INT)
BEGIN
    SELECT h.*, u.nombre AS terapeuta, e.nombre AS Especialidad,
           pg.monto, pg.metodo_pago, pg.estado_pago
    FROM historial_citas h
    JOIN terapeutas t ON h.terapeuta_id = t.id
    JOIN usuarios u ON t.usuario_id = u.id
    LEFT JOIN especialidades e ON t.especialidad_id = e.id
    LEFT JOIN pagos pg ON pg.cita_id = h.id
    WHERE h.paciente_id = p_paciente_id
    ORDER BY h.fecha_cita DESC;
END$$

DROP PROCEDURE IF EXISTS `sp_existe_paciente_por_dni`$$
CREATE PROCEDURE `sp_existe_paciente_por_dni`(IN p_dni VARCHAR(20))
BEGIN
    SELECT dni FROM pacientes WHERE dni = p_dni;
END$$

DROP PROCEDURE IF EXISTS `sp_crear_paciente`$$
CREATE PROCEDURE `sp_crear_paciente`(
    IN p_nombre VARCHAR(100), IN p_apellido VARCHAR(100),
    IN p_dni VARCHAR(20), IN p_telefono VARCHAR(20),
    IN p_email VARCHAR(120), IN p_fecha_nacimiento DATE,
    IN p_sexo VARCHAR(10), IN p_direccion VARCHAR(255), IN p_seguro VARCHAR(100)
)
BEGIN
    INSERT INTO pacientes (nombre, apellido, dni, telefono, email, fecha_nacimiento, sexo, direccion, seguro)
    VALUES (p_nombre, p_apellido, p_dni, p_telefono, p_email, p_fecha_nacimiento, p_sexo, p_direccion, p_seguro);
    SELECT LAST_INSERT_ID() AS id;
END$$

DROP PROCEDURE IF EXISTS `sp_actualizar_paciente`$$
CREATE PROCEDURE `sp_actualizar_paciente`(
    IN p_dni_actual VARCHAR(20),
    IN p_nombre VARCHAR(100), IN p_apellido VARCHAR(100),
    IN p_telefono VARCHAR(20), IN p_email VARCHAR(120),
    IN p_estado VARCHAR(20), IN p_fecha_nacimiento DATE,
    IN p_sexo VARCHAR(10), IN p_direccion VARCHAR(255),
    IN p_seguro VARCHAR(100), IN p_dni_nuevo VARCHAR(20)
)
BEGIN
    UPDATE pacientes
    SET nombre = IF(p_nombre IS NOT NULL, p_nombre, nombre),
        apellido = IF(p_apellido IS NOT NULL, p_apellido, apellido),
        telefono = IF(p_telefono IS NOT NULL, p_telefono, telefono),
        email = IF(p_email IS NOT NULL, p_email, email),
        estado = IF(p_estado IS NOT NULL, p_estado, estado),
        fecha_nacimiento = IF(p_fecha_nacimiento IS NOT NULL, p_fecha_nacimiento, fecha_nacimiento),
        sexo = IF(p_sexo IS NOT NULL, p_sexo, sexo),
        direccion = IF(p_direccion IS NOT NULL, p_direccion, direccion),
        seguro = IF(p_seguro IS NOT NULL, p_seguro, seguro),
        dni = IF(p_dni_nuevo IS NOT NULL, p_dni_nuevo, dni)
    WHERE dni = p_dni_actual;
    SELECT ROW_COUNT() AS actualizadas;
END$$

DROP PROCEDURE IF EXISTS `sp_listar_servicios`$$
CREATE PROCEDURE `sp_listar_servicios`()
BEGIN
    SELECT * FROM servicios WHERE activo = 1 ORDER BY nombre;
END$$

DROP PROCEDURE IF EXISTS `sp_listar_paquetes`$$
CREATE PROCEDURE `sp_listar_paquetes`(IN p_paciente_id INT)
BEGIN
    SELECT ps.*, s.nombre AS servicio_nombre, s.duracion_min
    FROM paquetes_sesiones ps
    JOIN servicios s ON ps.servicio_id = s.id
    WHERE ps.paciente_id = p_paciente_id
    ORDER BY ps.fecha_compra DESC;
END$$

DROP PROCEDURE IF EXISTS `sp_crear_paquete`$$
CREATE PROCEDURE `sp_crear_paquete`(
    IN p_paciente_id INT, IN p_servicio_id INT,
    IN p_total_sesiones INT, IN p_fecha_compra DATE, IN p_fecha_vencimiento DATE
)
BEGIN
    INSERT INTO paquetes_sesiones (paciente_id, servicio_id, total_sesiones, fecha_compra, fecha_vencimiento)
    VALUES (p_paciente_id, p_servicio_id, p_total_sesiones, p_fecha_compra, p_fecha_vencimiento);
    SELECT LAST_INSERT_ID() AS id;
END$$

DROP PROCEDURE IF EXISTS `sp_listar_evaluaciones`$$
CREATE PROCEDURE `sp_listar_evaluaciones`(IN p_paciente_id INT)
BEGIN
    SELECT ei.*, u.nombre AS terapeuta_nombre
    FROM evaluaciones_iniciales ei
    JOIN terapeutas t ON ei.terapeuta_id = t.id
    JOIN usuarios u ON t.usuario_id = u.id
    WHERE ei.paciente_id = p_paciente_id
    ORDER BY ei.fecha_creacion DESC;
END$$

DROP PROCEDURE IF EXISTS `sp_crear_evaluacion`$$
CREATE PROCEDURE `sp_crear_evaluacion`(
    IN p_paciente_id INT, IN p_terapeuta_id INT, IN p_motivo_consulta TEXT,
    IN p_escala_dolor_eva INT, IN p_rango_movimiento TEXT, IN p_objetivos_terapeuticos TEXT
)
BEGIN
    INSERT INTO evaluaciones_iniciales
        (paciente_id, terapeuta_id, motivo_consulta, escala_dolor_eva, rango_movimiento, objetivos_terapeuticos)
    VALUES (p_paciente_id, p_terapeuta_id, p_motivo_consulta, p_escala_dolor_eva, p_rango_movimiento, p_objetivos_terapeuticos);
    SELECT LAST_INSERT_ID() AS id;
END$$

DROP PROCEDURE IF EXISTS `sp_listar_consentimientos`$$
CREATE PROCEDURE `sp_listar_consentimientos`(IN p_paciente_id INT)
BEGIN
    SELECT * FROM consentimientos WHERE paciente_id = p_paciente_id ORDER BY aceptado_en DESC;
END$$

DROP PROCEDURE IF EXISTS `sp_crear_consentimiento`$$
CREATE PROCEDURE `sp_crear_consentimiento`(
    IN p_paciente_id INT, IN p_tipo VARCHAR(50), IN p_texto_version VARCHAR(50), IN p_ip_origen VARCHAR(45)
)
BEGIN
    INSERT INTO consentimientos (paciente_id, tipo, texto_version, ip_origen)
    VALUES (p_paciente_id, p_tipo, p_texto_version, p_ip_origen);
    SELECT LAST_INSERT_ID() AS id;
END$$

-- ============================================================
-- CITAS  (services/citas_service/routes.py)
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

DROP PROCEDURE IF EXISTS `sp_listar_terapeutas`$$
CREATE PROCEDURE `sp_listar_terapeutas`()
BEGIN
    SELECT t.id AS ID, t.precio, u.nombre AS Nombre, e.nombre AS Especialidad
    FROM terapeutas t
    JOIN usuarios u ON t.usuario_id = u.id
    LEFT JOIN especialidades e ON t.especialidad_id = e.id
    WHERE t.activo = 1
    ORDER BY u.nombre;
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

DROP PROCEDURE IF EXISTS `sp_consulta_medico_precio`$$
CREATE PROCEDURE `sp_consulta_medico_precio`(IN p_medico_id INT)
BEGIN
    SELECT t.precio FROM terapeutas t WHERE t.id = p_medico_id AND t.activo = 1;
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_paciente_id_dni`$$
CREATE PROCEDURE `sp_obtener_paciente_id_dni`(IN p_dni VARCHAR(20))
BEGIN
    SELECT id FROM pacientes WHERE dni = p_dni;
END$$

DROP PROCEDURE IF EXISTS `sp_crear_paciente_min`$$
CREATE PROCEDURE `sp_crear_paciente_min`(
    IN p_nombre VARCHAR(100), IN p_apellido VARCHAR(100),
    IN p_dni VARCHAR(20), IN p_telefono VARCHAR(20)
)
BEGIN
    INSERT INTO pacientes (nombre, apellido, dni, telefono) VALUES (p_nombre, p_apellido, p_dni, p_telefono);
    SELECT LAST_INSERT_ID() AS id;
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

DROP PROCEDURE IF EXISTS `sp_obtener_telefono_otp`$$
CREATE PROCEDURE `sp_obtener_telefono_otp`(IN p_dni VARCHAR(20))
BEGIN
    SELECT p.telefono
    FROM pacientes p
    JOIN historial_citas h ON h.paciente_id = p.id
    WHERE p.dni = p_dni AND h.estado = 'programada'
    LIMIT 1;
END$$

DROP PROCEDURE IF EXISTS `sp_invalidar_otps_previos`$$
CREATE PROCEDURE `sp_invalidar_otps_previos`(IN p_dni VARCHAR(20), IN p_accion VARCHAR(20))
BEGIN
    UPDATE otp_verificaciones SET usado = 1 WHERE dni = p_dni AND accion = p_accion AND usado = 0;
END$$

DROP PROCEDURE IF EXISTS `sp_insertar_otp`$$
CREATE PROCEDURE `sp_insertar_otp`(
    IN p_dni VARCHAR(20), IN p_codigo VARCHAR(10), IN p_accion VARCHAR(20), IN p_expira_en DATETIME
)
BEGIN
    INSERT INTO otp_verificaciones (dni, codigo, accion, expira_en)
    VALUES (p_dni, p_codigo, p_accion, p_expira_en);
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_otp`$$
CREATE PROCEDURE `sp_obtener_otp`(IN p_dni VARCHAR(20), IN p_accion VARCHAR(20))
BEGIN
    SELECT * FROM otp_verificaciones
    WHERE dni = p_dni AND accion = p_accion AND usado = 0
    ORDER BY creado_en DESC LIMIT 1;
END$$

DROP PROCEDURE IF EXISTS `sp_incrementar_intentos_otp`$$
CREATE PROCEDURE `sp_incrementar_intentos_otp`(IN p_id INT)
BEGIN
    UPDATE otp_verificaciones SET intentos = intentos + 1 WHERE id = p_id;
END$$

DROP PROCEDURE IF EXISTS `sp_marcar_otp_usado`$$
CREATE PROCEDURE `sp_marcar_otp_usado`(IN p_id INT)
BEGIN
    UPDATE otp_verificaciones SET usado = 1 WHERE id = p_id;
END$$

-- Estadisticas (se mantiene cada select en su propio procedure,
-- llamado bajo try/except para no romper la pagina)
DROP PROCEDURE IF EXISTS `sp_estadisticas_recuperados`$$
CREATE PROCEDURE `sp_estadisticas_recuperados`()
BEGIN
    SELECT COUNT(DISTINCT paciente_id) AS total FROM historial_citas WHERE estado = 'completada';
END$$

DROP PROCEDURE IF EXISTS `sp_estadisticas_especialistas`$$
CREATE PROCEDURE `sp_estadisticas_especialistas`()
BEGIN
    SELECT COUNT(*) AS total FROM terapeutas WHERE activo = 1;
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_configuracion_anio`$$
CREATE PROCEDURE `sp_obtener_configuracion_anio`()
BEGIN
    SELECT valor FROM configuracion WHERE clave = 'anio_inicio';
END$$

DROP PROCEDURE IF EXISTS `sp_estadisticas_opiniones`$$
CREATE PROCEDURE `sp_estadisticas_opiniones`()
BEGIN
    SELECT COUNT(*) AS total, SUM(CASE WHEN calificacion >= 4 THEN 1 ELSE 0 END) AS buenas
    FROM opiniones WHERE visible = 1;
END$$

-- ============================================================
-- AUTH / USUARIOS  (services/auth_service/routes.py)
-- ============================================================

DROP PROCEDURE IF EXISTS `sp_login`$$
CREATE PROCEDURE `sp_login`(IN p_correo VARCHAR(120))
BEGIN
    SELECT u.*, r.nombre AS rol_nombre
    FROM usuarios u
    JOIN roles r ON u.rol_id = r.id
    WHERE u.correo = p_correo AND u.activo = 1;
END$$

DROP PROCEDURE IF EXISTS `sp_actualizar_ultimo_acceso`$$
CREATE PROCEDURE `sp_actualizar_ultimo_acceso`(IN p_id INT)
BEGIN
    UPDATE usuarios SET ultimo_acceso = NOW() WHERE id = p_id;
END$$

DROP PROCEDURE IF EXISTS `sp_listar_usuarios`$$
CREATE PROCEDURE `sp_listar_usuarios`()
BEGIN
    SELECT u.id, u.nombre, u.correo, r.nombre AS rol, u.activo, u.ultimo_acceso
    FROM usuarios u
    JOIN roles r ON u.rol_id = r.id
    ORDER BY r.nombre, u.nombre;
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_rol_id`$$
CREATE PROCEDURE `sp_obtener_rol_id`(IN p_nombre VARCHAR(50))
BEGIN
    SELECT id FROM roles WHERE nombre = p_nombre;
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_rol_id_terapeuta`$$
CREATE PROCEDURE `sp_obtener_rol_id_terapeuta`()
BEGIN
    SELECT id FROM roles WHERE nombre = 'terapeuta';
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_usuario_por_correo`$$
CREATE PROCEDURE `sp_obtener_usuario_por_correo`(IN p_correo VARCHAR(120))
BEGIN
    SELECT id FROM usuarios WHERE correo = p_correo;
END$$

DROP PROCEDURE IF EXISTS `sp_crear_usuario`$$
CREATE PROCEDURE `sp_crear_usuario`(
    IN p_nombre VARCHAR(100), IN p_correo VARCHAR(120),
    IN p_clave VARCHAR(255), IN p_rol_id INT
)
BEGIN
    INSERT INTO usuarios (nombre, correo, clave, rol_id) VALUES (p_nombre, p_correo, p_clave, p_rol_id);
    SELECT LAST_INSERT_ID() AS id;
END$$

DROP PROCEDURE IF EXISTS `sp_actualizar_usuario`$$
CREATE PROCEDURE `sp_actualizar_usuario`(
    IN p_usuario_id INT, IN p_nombre VARCHAR(100), IN p_correo VARCHAR(120),
    IN p_activo TINYINT, IN p_clave VARCHAR(255), IN p_rol_id INT
)
BEGIN
    UPDATE usuarios
    SET nombre = IF(p_nombre IS NOT NULL, p_nombre, nombre),
        correo = IF(p_correo IS NOT NULL, p_correo, correo),
        activo = IF(p_activo IS NOT NULL, p_activo, activo),
        clave = IF(p_clave IS NOT NULL, p_clave, clave),
        rol_id = IF(p_rol_id IS NOT NULL, p_rol_id, rol_id)
    WHERE id = p_usuario_id;
    SELECT ROW_COUNT() AS actualizados;
END$$

DROP PROCEDURE IF EXISTS `sp_listar_roles`$$
CREATE PROCEDURE `sp_listar_roles`()
BEGIN
    SELECT * FROM roles WHERE activo = 1 ORDER BY nombre;
END$$

DROP PROCEDURE IF EXISTS `sp_verificar_usuario`$$
CREATE PROCEDURE `sp_verificar_usuario`(IN p_usuario_id INT)
BEGIN
    SELECT u.id, u.nombre, u.rol_id, r.nombre AS rol
    FROM usuarios u
    JOIN roles r ON u.rol_id = r.id
    WHERE u.id = p_usuario_id AND u.activo = 1;
END$$

-- ============================================================
-- PAGOS  (services/pagos_service/routes.py)
-- ============================================================

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

DROP PROCEDURE IF EXISTS `sp_guardar_referencia`$$
CREATE PROCEDURE `sp_guardar_referencia`(IN p_cita_id INT, IN p_cobro_id VARCHAR(100))
BEGIN
    UPDATE pagos SET referencia = p_cobro_id WHERE cita_id = p_cita_id;
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_cita_para_confirmar`$$
CREATE PROCEDURE `sp_obtener_cita_para_confirmar`(IN p_cita_id INT)
BEGIN
    SELECT h.fecha_cita, p.nombre, p.apellido, p.telefono AS telefono_paciente,
           u.nombre AS terapeuta, e.nombre AS Especialidad, u.telefono AS telefono_medico
    FROM historial_citas h
    JOIN pacientes p ON h.paciente_id = p.id
    JOIN terapeutas t ON h.terapeuta_id = t.id
    JOIN usuarios u ON t.usuario_id = u.id
    LEFT JOIN especialidades e ON t.especialidad_id = e.id
    WHERE h.id = p_cita_id;
END$$

DROP PROCEDURE IF EXISTS `sp_confirmar_pago`$$
CREATE PROCEDURE `sp_confirmar_pago`(
    IN p_cita_id INT, IN p_referencia VARCHAR(100),
    IN p_datos_respuesta TEXT, IN p_verificado_por INT
)
BEGIN
    IF p_verificado_por IS NOT NULL THEN
        UPDATE pagos
        SET estado_pago = 'pagado', fecha_pago = NOW(),
            referencia = COALESCE(p_referencia, referencia),
            transaccion_id = COALESCE(p_referencia, transaccion_id),
            datos_respuesta = COALESCE(p_datos_respuesta, datos_respuesta),
            verificado_en = NOW(), verificado_por = p_verificado_por
        WHERE cita_id = p_cita_id AND estado_pago = 'pendiente';
    ELSE
        UPDATE pagos
        SET estado_pago = 'pagado', fecha_pago = NOW(),
            referencia = COALESCE(p_referencia, referencia),
            transaccion_id = COALESCE(p_referencia, transaccion_id),
            datos_respuesta = COALESCE(p_datos_respuesta, datos_respuesta),
            verificado_en = NOW()
        WHERE cita_id = p_cita_id AND estado_pago = 'pendiente';
    END IF;
    SELECT ROW_COUNT() AS pagado;
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_pago`$$
CREATE PROCEDURE `sp_obtener_pago`(IN p_cita_id INT)
BEGIN
    SELECT * FROM pagos WHERE cita_id = p_cita_id;
END$$

-- ============================================================
-- NOTAS  (services/notas_service/routes.py)
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

-- ============================================================
-- ADMIN / GATEWAY  (gateway/app.py)
-- ============================================================

DROP PROCEDURE IF EXISTS `sp_completar_cita`$$
CREATE PROCEDURE `sp_completar_cita`(IN p_historial_id INT, IN p_descripcion TEXT)
BEGIN
    UPDATE historial_citas SET descripcion = p_descripcion, estado = 'completada'
    WHERE id = p_historial_id;
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_usuario_por_nombre`$$
CREATE PROCEDURE `sp_obtener_usuario_por_nombre`(IN p_nombre VARCHAR(100))
BEGIN
    SELECT u.id FROM usuarios u WHERE u.nombre = p_nombre;
END$$

DROP PROCEDURE IF EXISTS `sp_crear_usuario_admin`$$
CREATE PROCEDURE `sp_crear_usuario_admin`(
    IN p_nombre VARCHAR(100), IN p_correo VARCHAR(120),
    IN p_telefono VARCHAR(20), IN p_clave VARCHAR(255), IN p_rol_id INT
)
BEGIN
    INSERT INTO usuarios (nombre, correo, telefono, clave, rol_id)
    VALUES (p_nombre, p_correo, p_telefono, p_clave, p_rol_id);
    SELECT LAST_INSERT_ID() AS id;
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_especialidad_id`$$
CREATE PROCEDURE `sp_obtener_especialidad_id`(IN p_nombre VARCHAR(100))
BEGIN
    SELECT id FROM especialidades WHERE nombre = p_nombre;
END$$

DROP PROCEDURE IF EXISTS `sp_crear_terapeuta`$$
CREATE PROCEDURE `sp_crear_terapeuta`(IN p_usuario_id INT, IN p_especialidad_id INT, IN p_precio DECIMAL(10,2))
BEGIN
    INSERT INTO terapeutas (usuario_id, especialidad_id, precio) VALUES (p_usuario_id, p_especialidad_id, p_precio);
    SELECT LAST_INSERT_ID() AS id;
END$$

DROP PROCEDURE IF EXISTS `sp_actualizar_precio`$$
CREATE PROCEDURE `sp_actualizar_precio`(IN p_medico_id INT, IN p_precio DECIMAL(10,2))
BEGIN
    UPDATE terapeutas SET precio = p_precio WHERE id = p_medico_id;
END$$

DROP PROCEDURE IF EXISTS `sp_obtener_usuario_id_terapeuta`$$
CREATE PROCEDURE `sp_obtener_usuario_id_terapeuta`(IN p_medico_id INT)
BEGIN
    SELECT usuario_id FROM terapeutas WHERE id = p_medico_id;
END$$

DROP PROCEDURE IF EXISTS `sp_set_terapeuta_activo`$$
CREATE PROCEDURE `sp_set_terapeuta_activo`(IN p_medico_id INT, IN p_activo TINYINT)
BEGIN
    UPDATE terapeutas SET activo = p_activo WHERE id = p_medico_id;
END$$

DROP PROCEDURE IF EXISTS `sp_set_usuario_activo`$$
CREATE PROCEDURE `sp_set_usuario_activo`(IN p_usuario_id INT, IN p_activo TINYINT)
BEGIN
    UPDATE usuarios SET activo = p_activo WHERE id = p_usuario_id;
END$$

DROP PROCEDURE IF EXISTS `sp_cambiar_clave_usuario`$$
CREATE PROCEDURE `sp_cambiar_clave_usuario`(IN p_usuario_id INT, IN p_clave VARCHAR(255))
BEGIN
    UPDATE usuarios SET clave = p_clave WHERE id = p_usuario_id;
END$$

DROP PROCEDURE IF EXISTS `sp_consultar_medicos_admin`$$
CREATE PROCEDURE `sp_consultar_medicos_admin`()
BEGIN
    SELECT t.id AS ID, u.nombre AS Nombre, u.telefono AS Telefono, t.precio, t.activo,
           e.nombre AS Especialidad
    FROM terapeutas t
    JOIN usuarios u ON t.usuario_id = u.id
    LEFT JOIN especialidades e ON t.especialidad_id = e.id
    ORDER BY u.nombre;
END$$

DROP PROCEDURE IF EXISTS `sp_listar_especialidades`$$
CREATE PROCEDURE `sp_listar_especialidades`()
BEGIN
    SELECT id, nombre FROM especialidades WHERE activa = 1 ORDER BY nombre;
END$$

-- ============================================================
-- FICHA CLINICA  (services/pacientes_service/routes.py -> PDF)
-- Devuelve 4 result sets en orden:
--   1. Datos del paciente (0 o 1 fila)
--   2. Historial de citas con notas clinicas y pago (0..n)
--   3. Evaluaciones iniciales (0..n)
--   4. Paquetes de sesiones (0..n)
-- La app los lee con shared.proc.call_proc_results().
-- ============================================================

DROP PROCEDURE IF EXISTS `sp_obtener_ficha_clinica_completa`$$
CREATE PROCEDURE `sp_obtener_ficha_clinica_completa`(IN p_paciente_id INT)
BEGIN
    -- Resultado 1: datos del paciente
    SELECT * FROM pacientes WHERE id = p_paciente_id;

    -- Resultado 2: citas + notas clinicas + pago
    SELECT h.id AS cita_id, h.fecha_cita, h.hora_cita, h.estado, h.descripcion,
           u.nombre AS terapeuta, e.nombre AS Especialidad,
           pg.monto, pg.metodo_pago, pg.estado_pago,
           nc.id AS nota_id, nc.nota, nc.diagnostico, nc.fecha_creacion AS nota_fecha
    FROM historial_citas h
    JOIN terapeutas t ON h.terapeuta_id = t.id
    JOIN usuarios u ON t.usuario_id = u.id
    LEFT JOIN especialidades e ON t.especialidad_id = e.id
    LEFT JOIN pagos pg ON pg.cita_id = h.id
    LEFT JOIN notas_clinicas nc ON nc.cita_id = h.id
    WHERE h.paciente_id = p_paciente_id
    ORDER BY h.fecha_cita DESC, h.hora_cita DESC;

    -- Resultado 3: evaluaciones iniciales
    SELECT ei.*, u.nombre AS terapeuta_nombre
    FROM evaluaciones_iniciales ei
    JOIN terapeutas t ON ei.terapeuta_id = t.id
    JOIN usuarios u ON t.usuario_id = u.id
    WHERE ei.paciente_id = p_paciente_id
    ORDER BY ei.fecha_creacion DESC;

    -- Resultado 4: paquetes de sesiones
    SELECT ps.*, s.nombre AS servicio_nombre, s.duracion_min
    FROM paquetes_sesiones ps
    JOIN servicios s ON ps.servicio_id = s.id
    WHERE ps.paciente_id = p_paciente_id
    ORDER BY ps.fecha_compra DESC;
END$$

DELIMITER ;

-- ============================================================
-- AUDITORIA  (shared/audit.py)
-- ============================================================

DELIMITER $$

DROP PROCEDURE IF EXISTS `sp_insertar_log_auditoria`$$
CREATE PROCEDURE `sp_insertar_log_auditoria`(
    IN p_usuario_id INT, IN p_accion VARCHAR(100),
    IN p_tabla_afectada VARCHAR(50), IN p_registro_id INT,
    IN p_detalle TEXT, IN p_ip_origen VARCHAR(45)
)
BEGIN
    INSERT INTO logs_auditoria (usuario_id, accion, tabla_afectada, registro_id, detalle, ip_origen)
    VALUES (p_usuario_id, p_accion, p_tabla_afectada, p_registro_id, p_detalle, p_ip_origen);
END$$

DELIMITER ;

-- ============================================================
-- VERIFICACION
-- ============================================================
SELECT 'PROCEDIMIENTOS CREADOS CORRECTAMENTE' AS resultado;
SHOW PROCEDURE STATUS WHERE Db = 'moovacloud_db';
