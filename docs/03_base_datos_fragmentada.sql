-- ================================================================
-- MOOVA Clinic - Base de Datos Fragmentada por Microservicio (8 tablas)
-- ================================================================
-- Cada microservicio tiene su propia base de datos independiente.
-- Las tablas compartidas se replican como tablas de referencia
-- (sin FK hacia otras bases de datos).
-- ================================================================

-- ================================================================
-- 1. AUTH DATABASE (AuthService - Puerto 5001)
-- ================================================================
CREATE DATABASE IF NOT EXISTS moova_auth
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_general_ci;

USE moova_auth;

-- Administradores (credenciales de login)
CREATE TABLE admins (
    id         INT(11)      NOT NULL AUTO_INCREMENT,
    nombre     VARCHAR(100) NOT NULL,
    correo     VARCHAR(100) NOT NULL,
    clave      VARCHAR(255) NOT NULL,
    activo     TINYINT(1)   NOT NULL DEFAULT 1,
    creado_en  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY (correo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Credenciales de terapeutas para login (solo datos de autenticacion)
CREATE TABLE terapeutas_auth (
    id         INT(11)      NOT NULL,
    correo     VARCHAR(100) NOT NULL,
    clave      VARCHAR(255) NOT NULL,
    activo     TINYINT(1)   NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    UNIQUE KEY (correo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Registro de intentos de login (auditoria de seguridad)
CREATE TABLE login_attempts (
    id          INT(11)      NOT NULL AUTO_INCREMENT,
    ip_address  VARCHAR(45)  NOT NULL,
    correo      VARCHAR(100) NOT NULL,
    exitoso     TINYINT(1)   NOT NULL DEFAULT 0,
    intentado_en DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_ip (ip_address),
    INDEX idx_correo (correo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Bitacora de auditoria (registro de todas las acciones del sistema)
CREATE TABLE bitacora_auditoria (
    id              INT(11)      NOT NULL AUTO_INCREMENT,
    usuario_tipo    VARCHAR(20)  NOT NULL,
    usuario_id      INT(11)      DEFAULT NULL,
    usuario_nombre  VARCHAR(100) DEFAULT NULL,
    accion          VARCHAR(50)  NOT NULL,
    recurso         VARCHAR(50)  DEFAULT NULL,
    recurso_id      INT(11)      DEFAULT NULL,
    detalles        TEXT         DEFAULT NULL,
    ip_address      VARCHAR(45)  DEFAULT NULL,
    exitoso         TINYINT(1)   NOT NULL DEFAULT 1,
    creado_en       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_usuario (usuario_tipo, usuario_id),
    INDEX idx_accion (accion),
    INDEX idx_fecha (creado_en)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ================================================================
-- 2. PATIENTS DATABASE (PatientService - Puerto 5002)
-- ================================================================
CREATE DATABASE IF NOT EXISTS moova_patients
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_general_ci;

USE moova_patients;

-- Pacientes registrados
CREATE TABLE pacientes (
    id          INT(11)      NOT NULL AUTO_INCREMENT,
    nombre      VARCHAR(100) NOT NULL,
    apellido    VARCHAR(100) NOT NULL,
    dni         VARCHAR(15)  NOT NULL,
    telefono    VARCHAR(20)  NOT NULL,
    email       VARCHAR(100) DEFAULT NULL,
    fecha_nacimiento DATE    DEFAULT NULL,
    direccion   VARCHAR(255) DEFAULT NULL,
    activo      TINYINT(1)   NOT NULL DEFAULT 1,
    creado_en   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en DATETIME  DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY (dni),
    INDEX idx_nombre (nombre, apellido),
    INDEX idx_telefono (telefono)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Historial de consultas DNI a APISperu (cache + auditoria)
CREATE TABLE dni_lookups (
    id          INT(11)      NOT NULL AUTO_INCREMENT,
    dni         VARCHAR(15)  NOT NULL,
    nombre_api  VARCHAR(100) DEFAULT NULL,
    apellido_api VARCHAR(100) DEFAULT NULL,
    exitoso     TINYINT(1)   NOT NULL DEFAULT 1,
    consultado_en DATETIME   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_dni (dni)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ================================================================
-- 3. APPOINTMENTS DATABASE (AppointmentService - Puerto 5003)
-- ================================================================
CREATE DATABASE IF NOT EXISTS moova_appointments
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_general_ci;

USE moova_appointments;

-- Tabla de referencia: Pacientes (copia de solo lectura desde PatientService)
CREATE TABLE pacientes_ref (
    id          INT(11)      NOT NULL,
    nombre      VARCHAR(100) NOT NULL,
    apellido    VARCHAR(100) NOT NULL,
    dni         VARCHAR(15)  NOT NULL,
    telefono    VARCHAR(20)  NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY (dni)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla de referencia: Terapeutas (copia de solo lectura desde TherapistService)
CREATE TABLE terapeutas_ref (
    id           INT(11)      NOT NULL,
    Nombre       VARCHAR(100) NOT NULL,
    Especialidad VARCHAR(100) NOT NULL,
    Telefono     VARCHAR(20)  DEFAULT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Citas (entidad principal de este microservicio)
CREATE TABLE citas (
    id                   INT(11)     NOT NULL AUTO_INCREMENT,
    paciente_ref_id      INT(11)     NOT NULL,
    terapeuta_ref_id     INT(11)     NOT NULL,
    fecha_cita           DATE        NOT NULL,
    descripcion          TEXT        DEFAULT NULL,
    estado               VARCHAR(20) NOT NULL DEFAULT 'programada',
    recordatorio_enviado TINYINT(1)  NOT NULL DEFAULT 0,
    creado_en            DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en       DATETIME    DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_paciente (paciente_ref_id),
    INDEX idx_terapeuta (terapeuta_ref_id),
    INDEX idx_fecha (fecha_cita),
    INDEX idx_estado (estado),
    INDEX idx_terapeuta_fecha (terapeuta_ref_id, fecha_cita, estado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Log de eventos de citas (para auditoria y notificaciones)
CREATE TABLE cita_eventos (
    id          INT(11)      NOT NULL AUTO_INCREMENT,
    cita_id     INT(11)      NOT NULL,
    evento      VARCHAR(50)  NOT NULL,
    datos_json  JSON         DEFAULT NULL,
    creado_en   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_cita (cita_id),
    INDEX idx_evento (evento)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Pagos (control de pagos por cada cita)
CREATE TABLE pagos (
    id              INT(11)       NOT NULL AUTO_INCREMENT,
    cita_id         INT(11)       NOT NULL,
    paciente_ref_id INT(11)       NOT NULL,
    monto           DECIMAL(10,2) NOT NULL,
    metodo_pago     VARCHAR(30)   NOT NULL DEFAULT 'efectivo',
    estado_pago     VARCHAR(20)   NOT NULL DEFAULT 'pendiente',
    fecha_pago      DATETIME      DEFAULT NULL,
    referencia      VARCHAR(100)  DEFAULT NULL,
    notas           TEXT          DEFAULT NULL,
    creado_en       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_cita (cita_id),
    INDEX idx_paciente (paciente_ref_id),
    INDEX idx_estado (estado_pago)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ================================================================
-- 4. NOTIFICATIONS DATABASE (NotificationService - Puerto 5004)
-- ================================================================
CREATE DATABASE IF NOT EXISTS moova_notifications
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_general_ci;

USE moova_notifications;

-- Codigos OTP para modificar/cancelar citas
CREATE TABLE otp_verificaciones (
    id         INT(11)     NOT NULL AUTO_INCREMENT,
    dni        VARCHAR(15) NOT NULL,
    codigo     VARCHAR(6)  NOT NULL,
    accion     VARCHAR(20) NOT NULL,
    intentos   INT(11)     NOT NULL DEFAULT 0,
    expira_en  DATETIME    NOT NULL,
    usado      TINYINT(1)  NOT NULL DEFAULT 0,
    creado_en  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_dni_accion (dni, accion),
    INDEX idx_expira (expira_en)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Log de SMS enviados (auditoria de notificaciones)
CREATE TABLE sms_log (
    id              INT(11)      NOT NULL AUTO_INCREMENT,
    telefono        VARCHAR(20)  NOT NULL,
    mensaje         TEXT         NOT NULL,
    tipo            VARCHAR(50)  NOT NULL,
    exitoso         TINYINT(1)   NOT NULL DEFAULT 0,
    respuesta_api   TEXT         DEFAULT NULL,
    enviado_en      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_tipo (tipo),
    INDEX idx_fecha (enviado_en)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Cola de notificaciones pendientes (para processamiento asincrono)
CREATE TABLE notificacion_cola (
    id              INT(11)      NOT NULL AUTO_INCREMENT,
    tipo            VARCHAR(50)  NOT NULL,
    destino         VARCHAR(20)  NOT NULL,
    mensaje         TEXT         NOT NULL,
    metadata_json   JSON         DEFAULT NULL,
    estado          VARCHAR(20)  NOT NULL DEFAULT 'pendiente',
    intentos        INT(11)      NOT NULL DEFAULT 0,
    max_intentos    INT(11)      NOT NULL DEFAULT 3,
    creado_en       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    procesado_en    DATETIME     DEFAULT NULL,
    PRIMARY KEY (id),
    INDEX idx_estado (estado),
    INDEX idx_tipo (tipo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ================================================================
-- 5. THERAPISTS DATABASE (TherapistService - Puerto 5005)
-- ================================================================
CREATE DATABASE IF NOT EXISTS moova_therapists
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_general_ci;

USE moova_therapists;

-- Terapeutas (entidad principal de este microservicio)
CREATE TABLE terapeutas (
    ID           INT(11)      NOT NULL AUTO_INCREMENT,
    Nombre       VARCHAR(100) NOT NULL,
    Especialidad VARCHAR(100) NOT NULL,
    especialidad_id INT(11)   DEFAULT NULL,
    Correo       VARCHAR(100) NOT NULL,
    Clave        VARCHAR(255) NOT NULL,
    Telefono     VARCHAR(20)  DEFAULT NULL,
    activo       TINYINT(1)   NOT NULL DEFAULT 1,
    creado_en    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en DATETIME   DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ID),
    UNIQUE KEY (Correo),
    INDEX idx_especialidad (Especialidad),
    INDEX idx_nombre (Nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Catalogo de especialidades medicas
CREATE TABLE especialidades (
    id          INT(11)      NOT NULL AUTO_INCREMENT,
    nombre      VARCHAR(100) NOT NULL,
    descripcion TEXT         DEFAULT NULL,
    activa      TINYINT(1)   NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    UNIQUE KEY (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Datos iniciales de especialidades
INSERT INTO especialidades (nombre, descripcion) VALUES
('Fisioterapia', 'Tratamiento de lesiones y enfermedades del sistema musculoesqueletico'),
('Terapia Ocupacional', 'Rehabilitacion para realizar actividades de la vida diaria'),
('Fonoaudiologia', 'Trastornos del lenguaje, audicion y deglucion'),
('Kinesiologia', 'Ciencia del movimiento y rehabilitacion fisica'),
('Psicologia', 'Atencion psicologica y salud mental'),
('Rehabilitacion Cardiaca', 'Programa de recuperacion post-cardiopatia');

-- Tabla de referencia: Citas del dia (vista materializada para dashboard)
CREATE TABLE citas_diarias_ref (
    id              INT(11)      NOT NULL,
    paciente_nombre VARCHAR(100) NOT NULL,
    paciente_apellido VARCHAR(100) NOT NULL,
    paciente_dni    VARCHAR(15)  NOT NULL,
    paciente_telefono VARCHAR(20) NOT NULL,
    fecha_cita      DATE         NOT NULL,
    descripcion     TEXT         DEFAULT NULL,
    estado          VARCHAR(20)  NOT NULL,
    terapeuta_id    INT(11)      NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_terapeuta_fecha (terapeuta_id, fecha_cita)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Notas de sesion (descripcion de cada cita completada)
CREATE TABLE notas_sesion (
    id              INT(11)      NOT NULL AUTO_INCREMENT,
    cita_ref_id     INT(11)      NOT NULL,
    terapeuta_id    INT(11)      NOT NULL,
    paciente_ref_id INT(11)      NOT NULL,
    descripcion     TEXT         NOT NULL,
    creado_en       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_cita (cita_ref_id),
    INDEX idx_terapeuta (terapeuta_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ================================================================
-- SCRIPTS DE SINCRONIZACION DE TABLAS DE REFERENCIA
-- ================================================================
-- Estos scripts deben ejecutarse periodicamente (cron job) o
-- activarse via triggers/events para mantener las tablas de
-- referencia actualizadas entre microservicios.

-- Ejemplo: Sincronizar pacientes_ref desde PatientService
-- INSERT INTO moova_appointments.pacientes_ref
-- SELECT id, nombre, apellido, dni, telefono
-- FROM moova_patients.pacientes
-- ON DUPLICATE KEY UPDATE
--     nombre = VALUES(nombre),
--     apellido = VALUES(apellido),
--     telefono = VALUES(telefono);

-- Ejemplo: Sincronizar terapeutas_ref desde TherapistService
-- INSERT INTO moova_appointments.terapeutas_ref
-- SELECT ID, Nombre, Especialidad, Telefono
-- FROM moova_therapists.terapeutas
-- ON DUPLICATE KEY UPDATE
--     Nombre = VALUES(Nombre),
--     Especialidad = VALUES(Especialidad),
--     Telefono = VALUES(Telefono);
