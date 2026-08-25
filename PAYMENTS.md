# Integración real de pagos — MOOVA Clinic

Este proyecto integra **Yape Empresas**, **Plin Empresas** y **Niubiz (tarjetas)**.
**No se simula ningún pago**: la cita solo se marca como `pagado` cuando el proveedor
confirma el cobro (respuesta de su API o webhook). Si las credenciales no están
configuradas, la página muestra un error claro y la cita queda `pendiente`.

---

## 1. Qué contratar (dónde sacar las credenciales)

### Tarjeta de débito/crédito → Niubiz (VisaNet Perú)
| Dato | Variable en `.env` | Cómo se obtiene |
|---|---|---|
| Usuario de comercio | `NIUBIZ_USER` | Al contratar Niubiz (Visa/BCP), en el portal de comercio te dan usuario y clave de API. |
| Clave / contraseña | `NIUBIZ_PASSWORD` | Ídem. |
| Merchant ID | `NIUBIZ_MERCHANT_ID` | Portal de Niubiz (identificador de tu comercio). |
| Modo | `NIUBIZ_MODE` | `sandbox` (pruebas) o `live` (producción). |
| URL del SDK JS | `NIUBIZ_SDK_URL` | Archivo JS que entrega Niubiz para cifrar la tarjeta en el navegador. |
| Webhook | — | URL pública `https://TU-DOMINIO/webhook/pago` para recibir notificaciones. |

Requiere **cumplimiento PCI-DSS**: los datos de tarjeta se cifran en el navegador
con el SDK de Niubiz; **nunca** llegan a este servidor ni se guardan en la BD.

### Yape → Yape Empresas (BCP)
| Dato | Variable en `.env` | Cómo se obtiene |
|---|---|---|
| URL base API | `YAPE_API_URL` | La entrega BCP con el contrato. |
| Client ID | `YAPE_CLIENT_ID` | Contrato **Yape Empresas** (requiere cuenta BCP empresarial). |
| Client Secret | `YAPE_CLIENT_SECRET` | Ídem. |
| N° de negocio | `YAPE_MERCHANT_ID` | Número Yape Empresas asociado a tu negocio. |

El QR dinámico (con monto) lo genera la API de Yape Empresas; el cliente lo escanea
en su app Yape, paga y el backend consulta el estado real antes de confirmar.

### Plin → Plin Empresas (multi-banco)
| Dato | Variable en `.env` | Cómo se obtiene |
|---|---|---|
| URL base API | `PLIN_API_URL` | La define el banco con el que contratas (BCP, Interbank, BBVA, Scotiabank, BanBif…). |
| Client ID | `PLIN_CLIENT_ID` | Acuerdo **Plin Empresas**. |
| Client Secret | `PLIN_CLIENT_SECRET` | Ídem. |
| N° de negocio | `PLIN_MERCHANT_ID` | Identificador de negocio Plin. |

---

## 2. Flujo implementado

1. **Reserva provisional**: `/citas` crea la cita (`programada`) + un pago en
   estado `pendiente` (anticipo 50%) y redirige a `/pago?cita_id=X`.
2. **Pago** en `/pago` según el método elegido:
   - **Yape**: modal con QR dinámico (de la API de Yape Empresas). Botón
     "Ya realicé el pago" consulta el estado real (`/api/pago/yape/estado`).
   - **Plin**: igual con `/api/pago/plin/iniciar` y `/api/pago/plin/estado`.
   - **Tarjeta**: formulario profesional. El SDK de Niubiz cifra los datos en el
     navegador → token → `/api/pago/tarjeta/cobrar` autoriza con Niubiz.
3. **Confirmación**: solo si el proveedor confirma → `confirmar_pago_servicio()`
   marca `pagado`, envía los SMS (automatizaciones 2 y 3) y redirige a `/retorno`
   ("¡Tu cita ha sido agendada!").
4. **Webhooks**: `/webhook/pago` recibe confirmaciones asíncronas de los
   proveedores (configurar la URL pública en cada panel).

## 3. Endpoints de la API interna

| Endpoint | Método | Descripción |
|---|---|---|
| `/api/pago/yape/iniciar` | POST | Crea cobro Yape, devuelve QR (base64) + `cobro_id`. |
| `/api/pago/yape/estado` | POST | Consulta estado real; si está pagado, confirma la cita. |
| `/api/pago/plin/iniciar` | POST | Crea cobro Plin, devuelve QR (base64) + `cobro_id`. |
| `/api/pago/plin/estado` | POST | Consulta estado real; si está pagado, confirma la cita. |
| `/api/pago/tarjeta/iniciar` | POST | Devuelve `sessionKey` + `merchantId` para el SDK de Niubiz. |
| `/api/pago/tarjeta/cobrar` | POST | Autoriza con Niubiz el `cardToken` del navegador; confirma la cita. |
| `/webhook/pago` | POST | Confirmación asíncrona de los proveedores. |

## 4. Ajustes según lo que entregue cada proveedor

- Los **endpoints y el esquema de autenticación** exactos de Yape Empresas y
  Plin Empresas los define BCP/el banco al firmar el contrato. Están centralizados
  en `pagos_integracion.py` (`YapeClient`, `PlinClient`) para ajustarlos en un solo
  lugar. La estructura usa el estándar `client_credentials` + rutas `/api/v1/cobros`.
- El **nombre global del SDK de Niubiz** en el navegador está previsto como
  `window.Nbv3Tk`; si el SDK que te entreguen usa otro nombre, cámbialo en
  `templates/pago.html` (bloque `TARJETA`).
- El **código de aprobación** de Niubiz es `ACTION_CODE == "000"` (ver
  `NiubizClient.cobrar`).

## 5. Probar sin arriesgar dinero

Usa el modo `sandbox` de Niubiz con tarjetas de prueba (te las da el portal de
desarrollo de Niubiz). Para Yape/Plin pide a tu banco el entorno de pruebas.
Cuando tengas las credenciales, rellena `.env` (nunca subas este archivo a git;
está ignorado) y reinicia la app.