-- Base de datos: medicos_disponibles
CREATE DATABASE IF NOT EXISTS medicos_disponibles
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_general_ci;

USE medicos_disponibles;

-- Tabla: admins
CREATE TABLE admins (
    id     INT(11)      NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(100) NOT NULL,
    correo VARCHAR(100) NOT NULL,
    clave  VARCHAR(255) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY (correo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla: especialidades (catalogo de especialidades medicas)
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

-- Tabla: terapeutas
CREATE TABLE terapeutas (
    ID               INT(11)      NOT NULL AUTO_INCREMENT,
    Nombre           VARCHAR(100) NOT NULL,
    Especialidad     VARCHAR(100) NOT NULL,
    especialidad_id  INT(11)      DEFAULT NULL,
    Correo           VARCHAR(100) NOT NULL,
    Clave            VARCHAR(255) NOT NULL,
    Telefono         VARCHAR(20)  DEFAULT NULL,
    precio           DECIMAL(10,2) DEFAULT NULL,
    PRIMARY KEY (ID),
    UNIQUE KEY (Correo),
    FOREIGN KEY (especialidad_id) REFERENCES especialidades(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla: personas (pacientes que agendan cita)
CREATE TABLE personas (
    id       INT(11)     NOT NULL AUTO_INCREMENT,
    nombre   VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    dni      VARCHAR(15)  NOT NULL,
    telefono VARCHAR(20)  NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY (dni)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla: historial_citas
CREATE TABLE historial_citas (
    id                    INT(11)      NOT NULL AUTO_INCREMENT,
    persona_id            INT(11)      NOT NULL,
    terapeuta_id          INT(11)      NOT NULL,
    fecha_cita            DATE         NOT NULL,
    descripcion           TEXT         DEFAULT NULL,
    estado                VARCHAR(20)  NOT NULL DEFAULT 'programada',
    recordatorio_enviado  TINYINT(1)   NOT NULL DEFAULT 0,
    -- estado puede ser: programada | cancelada | completada
    PRIMARY KEY (id),
    FOREIGN KEY (persona_id)   REFERENCES personas(id),
    FOREIGN KEY (terapeuta_id) REFERENCES terapeutas(ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla: pagos (control de pagos por cada cita)
CREATE TABLE pagos (
    id              INT(11)      NOT NULL AUTO_INCREMENT,
    cita_id         INT(11)      NOT NULL,
    persona_id      INT(11)      NOT NULL,
    monto           DECIMAL(10,2) NOT NULL,
    metodo_pago     VARCHAR(30)  NOT NULL DEFAULT 'efectivo',
    -- metodo_pago puede ser: efectivo | tarjeta_credito | tarjeta_debito | transferencia | seguro
    estado_pago     VARCHAR(20)  NOT NULL DEFAULT 'pendiente',
    -- estado_pago puede ser: pendiente | pagado | reembolsado | cancelado
    fecha_pago      DATETIME     DEFAULT NULL,
    referencia      VARCHAR(100) DEFAULT NULL,
    notas           TEXT         DEFAULT NULL,
    creado_en       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY (cita_id)    REFERENCES historial_citas(id),
    FOREIGN KEY (persona_id) REFERENCES personas(id),
    INDEX idx_cita (cita_id),
    INDEX idx_estado (estado_pago),
    INDEX idx_fecha (fecha_pago)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla: otp_verificaciones (codigos SMS para modificar/cancelar citas)
CREATE TABLE IF NOT EXISTS otp_verificaciones (
    id         INT(11)     NOT NULL AUTO_INCREMENT,
    dni        VARCHAR(15) NOT NULL,
    codigo     VARCHAR(6)  NOT NULL,
    accion     VARCHAR(20) NOT NULL,        -- 'modificar' | 'cancelar'
    intentos   INT(11)     NOT NULL DEFAULT 0,
    expira_en  DATETIME    NOT NULL,
    usado      TINYINT(1)  NOT NULL DEFAULT 0,
    creado_en  DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_dni_accion (dni, accion)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla: bitacora_auditoria (registro de todas las acciones del sistema)
CREATE TABLE bitacora_auditoria (
    id              INT(11)      NOT NULL AUTO_INCREMENT,
    usuario_tipo    VARCHAR(20)  NOT NULL,
    -- usuario_tipo puede ser: admin | terapeuta | paciente | sistema | api
    usuario_id      INT(11)      DEFAULT NULL,
    usuario_nombre  VARCHAR(100) DEFAULT NULL,
    accion          VARCHAR(50)  NOT NULL,
    -- accion puede ser: login | logout | crear_cita | modificar_cita | cancelar_cita
    --                    registrar_terapeuta | eliminar_terapeuta | cambiar_clave
    --                    verificar_otp | enviar_sms | verificar_dni
    recurso         VARCHAR(50)  DEFAULT NULL,
    recurso_id      INT(11)      DEFAULT NULL,
    detalles        TEXT         DEFAULT NULL,
    ip_address      VARCHAR(45)  DEFAULT NULL,
    exitoso         TINYINT(1)   NOT NULL DEFAULT 1,
    creado_en       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_usuario (usuario_tipo, usuario_id),
    INDEX idx_accion (accion),
    INDEX idx_fecha (creado_en),
    INDEX idx_recurso (recurso, recurso_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla: opiniones (valoraciones de pacientes para tasa de exito)
CREATE TABLE opiniones (
    id              INT(11)      NOT NULL AUTO_INCREMENT,
    persona_id      INT(11)      DEFAULT NULL,
    nombre_paciente VARCHAR(100) NOT NULL,
    calificacion    TINYINT(1)   NOT NULL,
    -- calificacion: 1-5 estrellas
    comentario      TEXT         DEFAULT NULL,
   visible         TINYINT(1)   NOT NULL DEFAULT 1,
    creado_en       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_calificacion (calificacion),
    INDEX idx_visible (visible)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla: configuracion (parametros generales del sistema)
CREATE TABLE configuracion (
    id          INT(11)      NOT NULL AUTO_INCREMENT,
    clave       VARCHAR(50)  NOT NULL,
    valor       VARCHAR(255) NOT NULL,
    descripcion TEXT         DEFAULT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY (clave)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Datos iniciales de configuracion
INSERT INTO configuracion (clave, valor, descripcion) VALUES
('anio_inicio', '2023', 'Anio de inicio de actividades de la clinica');
