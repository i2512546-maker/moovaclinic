# MOOVA Clinic - Guia de Migracion: Monolito a Microservicios

## Estructura Propuesta

```
moovafinal-main/
├── services/
│   ├── auth/
│   │   ├── app.py
│   │   ├── config.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── patient/
│   │   ├── app.py
│   │   ├── config.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── appointment/
│   │   ├── app.py
│   │   ├── config.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── notification/
│   │   ├── app.py
│   │   ├── config.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   └── therapist/
│       ├── app.py
│       ├── config.py
│       ├── requirements.txt
│       └── Dockerfile
├── gateway/
│   └── nginx.conf
├── sql/
│   └── init/
│       ├── 01_auth.sql
│       ├── 02_patients.sql
│       ├── 03_appointments.sql
│       ├── 04_notifications.sql
│       └── 05_therapists.sql
├── docker-compose.yml
├── docs/
│   ├── 01_microservicios_identificacion.md
│   ├── 02_diagramas_arquitectura.md
│   ├── 03_base_datos_fragmentada.sql
│   └── 04_guia_migracion.md
└── README.md
```

---

## Paso a Paso de Migracion

### Fase 1: Preparacion

1. **Crear la estructura de carpetas** con los servicios individuales
2. **Copiar cada tab SQL** a su archivo init correspondiente en `sql/init/`
3. **Configurar docker-compose.yml** con todos los servicios

### Fase 2: Extraer AuthService

1. Crear `services/auth/app.py` con:
   - Funciones: `obtener_ip()`, `ip_esta_bloqueada()`, `registrar_intento_fallido()`, `limpiar_intentos()`
   - Decoradores: `@login_required`, `@admin_required`
   - Rutas: `POST /login`, `GET /logout`
   - Puntos de acceso internos: `POST /api/auth/verificar` (para que otros servicios validen tokens)

2. Crear `services/auth/config.py` con variables de entorno

### Fase 3: Extraer PatientService

1. Crear `services/patient/app.py` con:
   - Funcion: `consultar_dni_apiperu()`
   - Rutas: `GET /api/pacientes/<id>`, `GET /api/pacientes/dni/<dni>`, `POST /api/pacientes`

2. Crear `services/patient/config.py`

### Fase 4: Extraer AppointmentService

1. Crear `services/appointment/app.py` con:
   - Funcion: `medico_disponible()`
   - Todas las rutas de `/citas`, `/citas/modificar`, `/citas/cancelar`
   - Toda la API REST `/api/citas/*`
   - Logica de creacion de pacientes nuevos (llamando a PatientService)

2. Crear `services/appointment/config.py`

### Fase 5: Extraer NotificationService

1. Crear `services/notification/app.py` con:
   - Funciones: `_enviar_sms()`, `_normalizar_telefono()`
   - Funciones OTP: `generar_otp()`, `enviar_sms_otp()`, `guardar_otp()`, `verificar_otp()`
   - Funciones SMS: `enviar_sms_confirmacion_paciente()`, `enviar_sms_notificacion_medico()`
   - Scheduler: `enviar_recordatorios_24h()`
   - Rutas internas: `POST /api/otp/generar`, `POST /api/otp/verificar`, `POST /api/notificar`

2. Crear `services/notification/config.py`

### Fase 6: Extraer TherapistService

1. Crear `services/therapist/app.py` con:
   - Rutas: `GET /interfaz`, `POST /guardar_descripcion`
   - Panel admin: `GET/POST /panel_admin`, `POST /panel_admin/cancelar_cita/<id>`
   - CRUD de terapeutas
   - Rutas internas: `GET /api/terapeutas/<id>`, `GET /api/terapeutas`

2. Crear `services/therapist/config.py`

### Fase 7: Configurar Gateway y Comunicacion

1. Configurar `nginx.conf` como proxy inverso
2. Configurar Redis para cola de eventos
3. Implementar sincronizacion de tablas de referencia
4. Configurar verificaciones de salud entre servicios

---

## Mapeo de Rutas (Monolito → Microservicios)

| Ruta Monolito | Microservicio | Nueva Ruta |
|---|---|---|
| `GET /` | Frontend/TherapistService | `GET /` (nginx) |
| `POST /login` | AuthService | `POST /auth/login` |
| `GET /logout` | AuthService | `GET /auth/logout` |
| `GET/POST /citas` | AppointmentService | `GET/POST /citas` |
| `GET/POST /citas/modificar` | AppointmentService + NotificationService | `GET/POST /citas/modificar` |
| `GET/POST /citas/cancelar` | AppointmentService + NotificationService | `GET/POST /citas/cancelar` |
| `GET /retorno` | Frontend | `GET /retorno` |
| `GET /interfaz` | TherapistService | `GET /interfaz` |
| `POST /guardar_descripcion` | TherapistService | `POST /guardar_descripcion` |
| `GET/POST /panel_admin` | TherapistService | `GET/POST /panel_admin` |
| `POST /api/verificar_dni` | PatientService | `POST /api/pacientes/verificar_dni` |
| `POST /api/disponibilidad` | AppointmentService | `POST /api/citas/disponibilidad` |
| `GET /api/citas` | AppointmentService | `GET /api/citas` |
| `GET /api/citas/<id>` | AppointmentService | `GET /api/citas/<id>` |
| `POST /api/citas` | AppointmentService | `POST /api/citas` |
| `PUT /api/citas/<id>` | AppointmentService | `PUT /api/citas/<id>` |
| `DELETE /api/citas/<id>` | AppointmentService | `DELETE /api/citas/<id>` |
| `GET /api/terapeutas` | TherapistService | `GET /api/terapeutas` |

---

## Variables de Entorno por Servicio

```env
# Comunes
DB_HOST=mysql
SECRET_KEY=...

# AuthService
AUTH_DB=moova_auth
AUTH_PORT=5001

# PatientService
PATIENT_DB=moova_patients
PATIENT_PORT=5002
APIPERU_TOKEN=...
APIPERU_URL=...

# AppointmentService
APPOINTMENT_DB=moova_appointments
APPOINTMENT_PORT=5003
API_KEY=...

# NotificationService
NOTIFICATION_DB=moova_notifications
NOTIFICATION_PORT=5004
TEXTBEE_API_KEY=...
TEXTBEE_DEVICE_ID=...
TEXTBEE_URL=...
OTP_EXPIRA_MIN=10
OTP_MAX_INTENTOS=3

# TherapistService
THERAPIST_DB=moova_therapists
THERAPIST_PORT=5005
```

---

## Estrategia de Sincronizacion

| Tipo | Metodo | Frecuencia |
|---|---|---|
| pacientes_ref | Cron job o trigger en PatientService | Cada 5 min |
| terapeutas_ref | Cron job o trigger en TherapistService | Cada 5 min |
| citas_diarias_ref | Evento cuando se crea/modifica cita | Tiempo real |
| Notas de sesion | Evento cuando se guarda descripcion | Tiempo real |

---

## Consideraciones

1. **No romper el frontend existente:** Las rutas web se mantienen identicas via reescrituras de nginx
2. **API REST conserva formato:** Las respuestas JSON no cambian
3. **Respaldo:** Si un servicio esta caido, usar patron de circuito de seguridad
4. **Monitoreo:** Agregar verificaciones de salud en cada servicio
5. **Registros:** Centralizar registros con pila ELK o similar
