# API móvil MOOVA Clinic

**Base URL:** `https://<dominio-del-gateway>/api/movil`

La API comparte el proceso Flask del monolito y delega en los clientes
internos `auth_client`, `pacientes_client`, `citas_client`,
`pagos_client` y `notas_client`. No llama por HTTP a otro proceso ni
expone directamente las rutas `/_internal`.

## Contrato común

Todas las respuestas tienen este formato:

```json
{
  "status": 200,
  "codigo": "OK",
  "mensaje": "Operación realizada",
  "data": {}
}
```

Errores usan el mismo sobre y `data: null`. Códigos HTTP relevantes:
`400` datos inválidos, `401` token/OTP inválido o vencido,
`403` rol/propiedad/OTP no autorizado, `404` recurso no encontrado,
`429` límite de intentos, `502` servicio interno no disponible.

JSON: enviar `Content-Type: application/json`. La API móvil no acepta
cookies de sesión del navegador.

## Autenticación

### Personal (admin y terapeuta)

`POST /auth/login`

```json
{"correo":"usuario@clinica.pe","clave":"contraseña"}
```

Devuelve `data.access_token`, `token_type: Bearer` y
`expires_in: 28800`. Usar en llamadas posteriores:

```http
Authorization: Bearer <access_token>
```

JWT HS256 con `sub`, `rol`, `nombre`, `iat`, `exp`, `iss` y
`aud`. Emisor `moova-clinic`, audiencia `moova-mobile`, vigencia de
8 horas. En producción `JWT_SECRET` es obligatoria y distinta de
`SECRET_KEY`.

### Pacientes y acciones sensibles

1. `POST /auth/otp/solicitar` con `{"dni":"12345678","accion":"consultar"}`.
   Para un paciente nuevo que agenda, enviar también `telefono` y
   `accion: "agendar"`.
2. El SMS se envía al teléfono registrado cuando el DNI ya existe. Para
   DNI nuevo, el teléfono se valida con los validadores compartidos.
3. `POST /auth/otp/verificar` con DNI, OTP y la misma acción.
4. Enviar el valor devuelto en `data.verificacion` como
   `X-Verificacion: <valor>`.

La credencial `X-Verificacion` está ligada al DNI y a una acción
(`consultar`, `agendar`, `modificar` o `cancelar`) y vence en
15 minutos. No sustituye el JWT de personal para las operaciones de
personal. No se devuelve el OTP en la respuesta.

`GET /me` devuelve el sujeto y rol de la credencial presentada.

## Endpoints de negocio

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| GET | `/catalogo/servicios` | Admin, terapeuta, paciente | Catálogo de servicios |
| GET | `/catalogo/terapeutas` | Admin, terapeuta, paciente | Listado de terapeutas |
| GET | `/catalogo/terapeutas/{terapeuta_id}` | Admin, terapeuta, paciente | Detalle de terapeuta |
| GET | `/citas/ocupadas` | Admin, terapeuta, paciente | Horas ocupadas; filtros por query string del servicio |
| POST | `/citas/disponibilidad` | Admin, terapeuta, paciente | Verificar disponibilidad; reenvía JSON al servicio |
| GET | `/citas` | Admin, terapeuta | Listado; filtros `fecha`, `estado`, `dni`; terapeuta queda limitado a su ID |
| GET | `/citas/{cita_id}` | Admin, terapeuta | Detalle; terapeuta solo ve sus citas |
| POST | `/citas` | Admin, terapeuta, paciente | Crear cita; requiere `X-Verificacion` acción `agendar` |
| PUT | `/citas/{cita_id}` | Admin, terapeuta, paciente | Modificar cita; requiere OTP `modificar` ligado al paciente de la cita |
| DELETE | `/citas/{cita_id}` | Admin, terapeuta, paciente | Cancelar cita; requiere OTP `cancelar` ligado al paciente |
| GET | `/pacientes/{dni}` | Admin, terapeuta asignado, paciente propio | Ficha e historial |
| GET | `/pacientes/{dni}/citas` | Admin, terapeuta asignado, paciente propio | Historial de citas |
| GET | `/pacientes/{dni}/pagos` | Admin, terapeuta asignado, paciente propio | Historial de pagos |
| GET | `/pacientes/{dni}/paquetes` | Admin, terapeuta asignado, paciente propio | Paquetes del paciente |
| GET | `/pacientes/{dni}/evaluaciones` | Admin, terapeuta asignado, paciente propio | Evaluaciones |
| POST | `/pacientes/{dni}/evaluaciones` | Admin, terapeuta asignado | Registrar evaluación |
| GET | `/pagos/{cita_id}` | Admin, terapeuta asignado | Estado de pago |
| POST | `/pagos/anticipo` | Admin, terapeuta asignado | Registrar anticipo |
| GET | `/agenda` | Admin, terapeuta | Agenda; terapeuta solo ve sus citas |
| GET | `/estadisticas` | Admin | Estadísticas del módulo de citas |
| GET | `/notas/{cita_id}` | Admin, terapeuta asignado | Consultar notas |
| POST | `/notas/{cita_id}` | Admin, terapeuta asignado | Registrar nota |

Hay 22 operaciones de negocio, además de los tres endpoints de
autenticación/OTP y `GET /me`. Los parámetros de negocio y validaciones
son los mismos que los servicios internos existentes; no se duplican
procedimientos almacenados ni reglas de negocio.

## Ejemplos

### Consultar catálogo

```http
GET /api/movil/catalogo/servicios
Authorization: Bearer <JWT>
```

### Solicitar OTP de paciente

```http
POST /api/movil/auth/otp/solicitar
Content-Type: application/json

{"dni":"12345678","accion":"consultar"}
```

### Consultar el propio historial

```http
GET /api/movil/pacientes/12345678/citas
X-Verificacion: <credencial-OTP>
```

### Agendar con OTP

```http
POST /api/movil/auth/otp/solicitar
Content-Type: application/json

{"dni":"12345678","accion":"agendar","telefono":"987654321"}
```

Después de recibir y verificar el SMS con `accion: "agendar"`:

```http
POST /api/movil/citas
Content-Type: application/json
X-Verificacion: <credencial-OTP>

{
  "nombre":"Ana",
  "apellido":"Pérez",
  "dni":"12345678",
  "telefono":"987654321",
  "medico_id":1,
  "fecha_cita":"2026-11-10",
  "hora_cita":"10:00"
}
```

Para personal, añadir además `Authorization: Bearer <JWT>`.
El servicio de citas conserva la validación de campos, horarios, cupos,
teléfono y reglas de negocio.

## Pruebas

Desde la raíz del repositorio:

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -p "test_api_movil.py" -v
python -m unittest discover -s tests -p "test_otp_agendar.py" -v
ruff check gateway/movil.py gateway/app.py tests/test_api_movil.py tests/test_otp_agendar.py
```

Los tests cubren rechazo de cookie, ausencia de Bearer, JWT vencido,
rol incorrecto, OTP obligatorio, OTP ligado a acción, DNI propio y
contrato JSON. La ejecución debe realizarse en un entorno con las
dependencias instaladas; los tests no sustituyen pruebas integradas
contra SMS y base de datos reales.
