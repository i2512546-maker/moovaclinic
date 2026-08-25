# MOOVA Clinic - Diagramas de Arquitectura

## 1. Diagrama de Arquitectura General (Microservicios)

```mermaid
graph TB
    subgraph "Frontend (Nginx / Load Balancer)"
        FE[Web UI - Jinja2 Templates]
    end

    subgraph "API Gateway"
        GW[API Gateway / Kong / Traefik]
    end

    subgraph "Microservicios"
        AS[AuthService<br/>:5001]
        PS[PatientService<br/>:5002]
        APS[AppointmentService<br/>:5003]
        NS[NotificationService<br/>:5004]
        TS[TherapistService<br/>:5005]
    end

    subgraph "Bases de Datos"
        DB1[(auth_db<br/>MySQL)]
        DB2[(patients_db<br/>MySQL)]
        DB3[(appointments_db<br/>MySQL)]
        DB4[(notifications_db<br/>MySQL)]
        DB5[(therapists_db<br/>MySQL)]
    end

    subgraph "Servicios Externos"
        EXT1[APISperu<br/>DNI Lookup]
        EXT2[TextBee SMS<br/>WhatsApp Gateway]
    end

    subgraph "Cola de Mensajes"
        MQ[Redis / RabbitMQ]
    end

    FE --> GW
    GW --> AS
    GW --> PS
    GW --> APS
    GW --> TS

    AS --> DB1
    PS --> DB2
    APS --> DB3
    NS --> DB4
    TS --> DB5

    PS --> EXT1
    NS --> EXT2

    APS -->|evento cita_creada| MQ
    APS -->|evento cita_modificada| MQ
    APS -->|evento cita_cancelada| MQ
    MQ --> NS

    APS -.->|HTTP REST| PS
    APS -.->|HTTP REST| TS
    TS -.->|HTTP REST| APS
```

---

## 2. Diagrama de Flujo - Agendar Cita

```mermaid
sequenceDiagram
    participant U as Usuario
    participant FE as Frontend
    participant APS as AppointmentService
    participant PS as PatientService
    participant TS as TherapistService
    participant NS as NotificationService
    participant DB as appointments_db

    U->>FE: Completa formulario cita
    FE->>APS: POST /citas

    APS->>PS: GET /api/pacientes/dni/{dni}
    PS-->>APS: Datos paciente (o crea nuevo)

    APS->>TS: GET /api/terapeutas/{id}
    TS-->>APS: Datos terapeuta

    APS->>DB: Verificar disponibilidad medico
    DB-->>APS: Sin conflicto

    APS->>DB: INSERT cita (estado=programada)
    DB-->>APS: cita_id

    APS->>NS: POST /api/notificar (evento cita_creada)
    NS->>NS: SMS confirmacion paciente
    NS->>NS: SMS notificacion medico

    APS-->>FE: Redirect a /retorno
    FE-->>U: Pagina confirmacion
```

---

## 3. Diagrama de Flujo - Modificar Cita (con OTP)

```mermaid
sequenceDiagram
    participant U as Usuario
    participant FE as Frontend
    participant APS as AppointmentService
    participant NS as NotificationService
    participant PS as PatientService
    participant DB as appointments_db
    participant OTP_DB as notifications_db

    Note over U,OTP_DB: Paso 1: Solicitar OTP
    U->>FE: Ingresa DNI
    FE->>APS: POST /citas/modificar (accion=solicitar)
    APS->>PS: GET /api/pacientes/dni/{dni}
    PS-->>APS: telefono paciente
    APS->>NS: POST /api/otp/generar
    NS->>OTP_DB: Guardar OTP
    NS->>NS: Enviar SMS con codigo
    NS-->>APS: OTP enviado
    APS-->>FE: Mostrar paso verificacion

    Note over U,OTP_DB: Paso 2: Verificar OTP
    U->>FE: Ingresa codigo OTP
    FE->>APS: POST /citas/modificar (accion=verificar)
    APS->>NS: POST /api/otp/verificar
    NS->>OTP_DB: Validar codigo
    OTP_DB-->>NS: ok
    NS-->>APS: Verificado
    APS->>DB: SELECT citas programadas
    DB-->>APS: Lista citas
    APS-->>FE: Mostrar citas para editar

    Note over U,OTP_DB: Paso 3: Guardar cambios
    U->>FE: Selecciona nueva fecha/medico
    FE->>APS: POST /citas/modificar (accion=guardar)
    APS->>DB: UPDATE cita
    APS-->>FE: Cita modificada
```

---

## 4. Diagrama de Flujo - Recordatorios 24h

```mermaid
sequenceDiagram
    participant SCH as APScheduler
    participant NS as NotificationService
    participant DB as notifications_db
    participant APT_DB as appointments_db
    participant SMS as TextBee API

    loop Cada 1 hora
        SCH->>NS: Ejecutar enviar_recordatorios_24h()
        NS->>APT_DB: SELECT citas para manana (recordatorio_enviado=0)
        APT_DB-->>NS: Lista citas

        loop Cada cita
            NS->>SMS: SMS recordatorio paciente
            NS->>SMS: SMS recordatorio medico
            NS->>APT_DB: UPDATE recordatorio_enviado=1
        end

        NS-->>SCH: Completado
    end
```

---

## 5. Diagrama de Base de Datos Fragmentada (8 Tablas)

```mermaid
erDiagram
    auth_db {
        INT id PK
        VARCHAR nombre
        VARCHAR correo UK
        VARCHAR clave
        BOOLEAN activo
    }

    auth_db_login_attempts {
        INT id PK
        VARCHAR ip_address
        VARCHAR correo
        BOOLEAN exitoso
        DATETIME intentado_en
    }

    auth_db_bitacora {
        INT id PK
        VARCHAR usuario_tipo
        INT usuario_id
        VARCHAR accion
        VARCHAR recurso
        INT recurso_id
        TEXT detalles
        VARCHAR ip_address
        BOOLEAN exitoso
        DATETIME creado_en
    }

    patients_db {
        INT id PK
        VARCHAR nombre
        VARCHAR apellido
        VARCHAR dni UK
        VARCHAR telefono
        VARCHAR email
        DATE fecha_nacimiento
    }

    appointments_db {
        INT id PK
        INT paciente_ref_id FK
        INT terapeuta_ref_id FK
        DATE fecha_cita
        TEXT descripcion
        ENUM estado "programada | cancelada | completada"
        BOOLEAN recordatorio_enviado
    }

    appointments_db_pagos {
        INT id PK
        INT cita_id FK
        INT paciente_ref_id FK
        DECIMAL monto
        VARCHAR metodo_pago
        VARCHAR estado_pago
        DATETIME fecha_pago
        VARCHAR referencia
    }

    notifications_db {
        INT id PK
        VARCHAR dni
        VARCHAR codigo
        ENUM accion "modificar | cancelar"
        INT intentos
        DATETIME expira_en
        BOOLEAN usado
        DATETIME creado_en
    }

    therapists_db {
        INT id PK
        VARCHAR nombre
        VARCHAR especialidad
        VARCHAR correo UK
        VARCHAR clave
        VARCHAR telefono
    }

    therapists_db_especialidades {
        INT id PK
        VARCHAR nombre UK
        TEXT descripcion
        BOOLEAN activa
    }

    appointments_db ||--o{ appointments_db_pagos : "tiene pagos"
    patients_db ||--o{ appointments_db : "agenda citas"
    therapists_db ||--o{ appointments_db : "atiende citas"
    therapists_db }o--|| therapists_db_especialidades : "tiene especialidad"
```

---

## 6. Diagrama de Despliegue

```mermaid
graph LR
    subgraph "Servidor / Docker"
        subgraph "Contenedor: nginx"
            LB[Nginx<br/>Proxy Inverso]
        end

        subgraph "Contenedor: auth-service"
            AS[AuthService<br/>Flask :5001]
        end

        subgraph "Contenedor: patient-service"
            PS[PatientService<br/>Flask :5002]
        end

        subgraph "Contenedor: appointment-service"
            APS[AppointmentService<br/>Flask :5003]
        end

        subgraph "Contenedor: notification-service"
            NS[NotificationService<br/>Flask :5004]
        end

        subgraph "Contenedor: therapist-service"
            TS[TherapistService<br/>Flask :5005]
        end

        subgraph "Contenedor: redis"
            REDIS[Redis<br/>Cola + Cache]
        end

        subgraph "Contenedor: mysql"
            MYSQL[MySQL<br/>5 esquemas]
        end
    end

    LB --> AS
    LB --> PS
    LB --> APS
    LB --> TS

    APS --> REDIS
    REDIS --> NS

    AS --> MYSQL
    PS --> MYSQL
    APS --> MYSQL
    NS --> MYSQL
    TS --> MYSQL
```

---

## 7. Docker Compose (Referencia)

```yaml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - auth-service
      - patient-service
      - appointment-service
      - therapist-service

  auth-service:
    build: ./services/auth
    ports:
      - "5001:5001"
    env_file: .env
    depends_on:
      - mysql

  patient-service:
    build: ./services/patient
    ports:
      - "5002:5002"
    env_file: .env
    depends_on:
      - mysql

  appointment-service:
    build: ./services/appointment
    ports:
      - "5003:5003"
    env_file: .env
    depends_on:
      - mysql
      - redis
      - patient-service
      - therapist-service

  notification-service:
    build: ./services/notification
    ports:
      - "5004:5004"
    env_file: .env
    depends_on:
      - mysql
      - redis

  therapist-service:
    build: ./services/therapist
    ports:
      - "5005:5005"
    env_file: .env
    depends_on:
      - mysql
      - appointment-service

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  mysql:
    image: mysql:8.0
    ports:
      - "3306:3306"
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_PASSWORD}
    volumes:
      - ./sql/init:/docker-entrypoint-initdb.d
```
