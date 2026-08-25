# MOOVA Clinic - Identificacion de Microservicios

## Contexto Actual

El proyecto MOOVA Clinic es un **monolito Flask** (app.py, 1210 lineas) que concentra toda la logica en un solo archivo: rutas, autenticacion, negocio, SMS, OTP, scheduler y acceso a BD. La base de datos unica `medicos_disponibles` contiene 8 tablas.

---

## Base de Datos Original (8 Tablas)

| # | Tabla | Descripcion |
|---|---|---|
| 1 | `admins` | Credenciales de administradores |
| 2 | `terapeutas` | Datos de terapeutas (medicos) |
| 3 | `personas` | Pacientes que agendan citas |
| 4 | `historial_citas` | Registro de todas las citas |
| 5 | `otp_verificaciones` | Codigos SMS para modificar/cancelar |
| 6 | `especialidades` | Catalogo de especialidades medicas |
| 7 | `pagos` | Control de pagos por cada cita |
| 8 | `bitacora_auditoria` | Registro de todas las acciones del sistema |

---

## Microservicios Identificados

### 1. AuthService (Autenticacion y Seguridad)

**Responsabilidad:** Gestionar login, sesiones, registro de usuarios, proteccion por IP y auditoria del sistema.

| Componente | Detalle |
|---|---|
| Tablas propias | `admins`, `terapeutas_auth`, `login_attempts`, `bitacora_auditoria` |
| Tablas compartidas (solo lectura) | - |
| Rutas | `POST /login`, `GET /logout` |
| Funciones internas | `obtener_ip()`, `ip_esta_bloqueada()`, `registrar_intento_fallido()`, `limpiar_intentos()` |
| Decoradores | `@login_required`, `@admin_required` |
| Externo | Bcrypt para hashing de contrasenas |
| Puerto | 5001 |

**Justificacion:** La autenticacion es un dominio transversal que puede escalar independientemente. La bitacora de auditoria se centraliza aqui porque es responsabilidad de seguridad.

---

### 2. PatientService (Gestion de Pacientes)

**Responsabilidad:** CRUD de pacientes, consulta de DNI via APISperu, datos demograficos.

| Componente | Detalle |
|---|---|
| Tablas propias | `pacientes`, `dni_lookups` |
| Rutas | `POST /api/pacientes`, `GET /api/pacientes/<id>`, `POST /api/pacientes/verificar_dni` |
| Funciones internas | `consultar_dni_apiperu()` |
| Externo | APISperu API (dniruc.apisperu.com) |
| Puerto | 5002 |

**Justificacion:** Los pacientes son una entidad de dominio propia. La integracion con APISperu es un servicio externo puntual que no afecta otros microservicios.

---

### 3. AppointmentService (Gestion de Citas y Pagos)

**Responsabilidad:** Crear, modificar, cancelar y consultar citas. Verificar disponibilidad del medico. Gestionar pagos asociados.

| Componente | Detalle |
|---|---|
| Tablas propias | `citas`, `cita_eventos`, `pagos` |
| Tablas compartidas (solo lectura) | `pacientes_ref` (desde PatientService), `terapeutas_ref` (desde TherapistService) |
| Rutas web | `GET/POST /citas`, `GET/POST /citas/modificar`, `GET/POST /citas/cancelar`, `GET /retorno` |
| Rutas API REST | `GET /api/citas`, `GET /api/citas/<id>`, `POST /api/citas`, `PUT /api/citas/<id>`, `DELETE /api/citas/<id>`, `GET /api/terapeutas` |
| Funciones internas | `medico_disponible()` |
| Eventos que emite | `cita_creada`, `cita_modificada`, `cita_cancelada` |
| Externo | API_KEY para autenticacion REST |
| Puerto | 5003 |

**Justificacion:** El dominio de citas es el nucleo del negocio. Concentra la regla de negocio principal (1 cita por medico por dia) y expone tanto interface web como API REST. Los pagos se asocian directamente a las citas.

---

### 4. NotificationService (Notificaciones y OTP)

**Responsabilidad:** Envio de SMS, generacion y verificacion de OTP, recordatorios programados.

| Componente | Detalle |
|---|---|
| Tablas propias | `otp_verificaciones`, `sms_log`, `notificacion_cola` |
| Rutas | `POST /api/otp/generar`, `POST /api/otp/verificar` |
| Funciones internas | `generar_otp()`, `enviar_sms_otp()`, `guardar_otp()`, `verificar_otp()`, `_enviar_sms()`, `enviar_sms_confirmacion_paciente()`, `enviar_sms_notificacion_medico()`, `enviar_recordatorios_24h()`, `_normalizar_telefono()` |
| Scheduler | APScheduler cada 1 hora para recordatorios 24h |
| Externo | TextBee SMS API (textbee.dev) |
| Puerto | 5004 |

**Justificacion:** Las notificaciones y el sistema OTP son un dominio tecnico aislado. El scheduler de recordatorios puede ejecutarse independientemente. TextBee es el unico proveedor externo critico.

---

### 5. TherapistService (Gestion de Terapeutas, Especialidades y Panel)

**Responsabilidad:** Dashboard del terapeuta, notas de sesion, registro/eliminacion de terapeutas, catalogo de especialidades, panel admin.

| Componente | Detalle |
|---|---|
| Tablas propias | `terapeutas`, `especialidades`, `citas_diarias_ref`, `notas_sesion` |
| Tablas compartidas (solo lectura) | `citas` (via API del AppointmentService) |
| Rutas | `GET /interfaz`, `POST /guardar_descripcion`, `GET/POST /panel_admin`, `POST /panel_admin/cancelar_cita/<id>` |
| Funciones internas | Consultas de pacientes del dia, registro de terapeutas, cambio de contrasenas, CRUD especialidades |
| Externo | - |
| Puerto | 5005 |

**Justificacion:** El dashboard del terapeuta y el panel admin son caras internas de la plataforma. La gestion de terapeutas y el catalogo de especialidades son dominios administrativos separados del negocio de citas.

---

## Matriz de Dependencias

```
AuthService ──────────────────────────────┐
                                          │
PatientService ────────┐                  │
                       │                  │
                       ▼                  ▼
              AppointmentService ──► NotificationService
                       │
                       ▼
              TherapistService
```

| Servicio | Dependencias |
|---|---|
| AuthService | Ninguna (independiente) |
| PatientService | Ninguna (independiente) |
| AppointmentService | PatientService (datos paciente), TherapistService (datos terapeuta), AuthService (API key) |
| NotificationService | AppointmentService (eventos de cita), PatientService (telefono paciente) |
| TherapistService | AppointmentService (citas del dia) |

---

## Comunicacion entre Servicios

| Tipo | Uso |
|---|---|
| **HTTP REST** | AppointmentService consulta PatientService y TherapistService para obtener datos |
| **Eventos/Cola** | AppointmentService emite eventos `cita_creada`/`cita_modificada`/`cita_cancelada` que NotificationService consume |
| **Sincrono (respaldo)** | Si la cola no esta disponible, AppointmentService llama directamente a NotificationService |

---

## Tabla Resumen

| # | Microservicio | Puerto | Tablas BD | Externo |
|---|---|---|---|---|
| 1 | AuthService | 5001 | admins, terapeutas_auth, login_attempts, bitacora_auditoria | Bcrypt |
| 2 | PatientService | 5002 | pacientes, dni_lookups | APISperu |
| 3 | AppointmentService | 5003 | citas, cita_eventos, pagos | API_KEY auth |
| 4 | NotificationService | 5004 | otp_verificaciones, sms_log, notificacion_cola | TextBee SMS |
| 5 | TherapistService | 5005 | terapeutas, especialidades, citas_diarias_ref, notas_sesion | - |
