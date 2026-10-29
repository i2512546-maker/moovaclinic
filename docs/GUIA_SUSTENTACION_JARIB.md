# MOOVA Clinic — Guía total para la sustentación de Jarib

**Base:** README y código de la rama main del repositorio, contrastados con el Word de exposición entregado. Si hay diferencias entre ambos, esta guía las señala. Esta guía no afirma que las pruebas se hayan ejecutado en esta sesión.

## 0. Lo primero que debes memorizar

Estudia en este orden: **arquitectura → reserva → pagos → seguridad → pruebas → MoovaTrack → limitaciones**.

- Problema: centralizar citas y seguimiento y ayudar a detectar señales de abandono.
- Arquitectura: monolito modular Flask, seis módulos de dominio y siete esquemas MySQL.
- Reserva: validar datos, comprobar disponibilidad, buscar/crear paciente, crear cita, auditar y generar pago pendiente.
- Pago: el servidor no confía en el navegador; valida referencia y monto con la pasarela.
- Identidad: el paciente no tiene login tradicional; DNI y OTP por SMS protegen operaciones sensibles.
- Seguridad: bcrypt, CSRF, sesión firmada, clave interna, límites de intentos, roles y auditoría.
- Calidad: GitHub Actions comprueba lint, tests, dependencias, procedimientos SQL, Swagger y compilación React.
- MoovaTrack: panel y conteo con datos simulados; hardware todavía no conectado.
- Limitaciones: pagos dependen de configuración, una cita por especialista/día, inasistencias no automatizadas desde la interfaz, bloqueo en memoria y una limitación documentada de autorización en pago/retorno.

Para explicar cualquier función debes poder contestar: **qué recibe, qué valida, qué llama, qué guarda, qué devuelve y qué hace si falla**.

## 1. Guion oral completo

### Apertura

“Buenos días. Presentamos MOOVA Clinic, un sistema web para gestionar las citas y apoyar el seguimiento de pacientes de una clínica de fisioterapia en Huancayo. La solución reúne la reserva, el seguimiento clínico y los reportes administrativos. Primero explicaré los objetivos y la arquitectura; después, un aporte adicional llamado MoovaTrack, las medidas de seguridad y las pruebas. Finalmente mostraré los indicadores, el reporte de riesgo, la auditoría y la documentación de la API.”

### Objetivos

“El objetivo general es automatizar la reserva de citas y apoyar el seguimiento del paciente. Tenemos tres objetivos específicos: permitir que el paciente reserve sin tener que llamar; facilitar al terapeuta el registro de la evolución y la consulta de la ficha clínica; y dar a la administración indicadores para revisar el funcionamiento y detectar pacientes con señales de posible abandono. Estos objetivos se demuestran en el flujo de citas, las notas y ficha clínica, y el panel de KPIs con el reporte de riesgo.”

No prometas funciones que no estén operativas en la versión desplegada.

### Arquitectura

“MOOVA Clinic usa una arquitectura de monolito modular. Una aplicación Flask, llamada gateway, recibe las peticiones y reúne los módulos de autenticación, pacientes, citas, pagos, notas clínicas y auditoría. Además hay un esquema separado para KPIs, por eso son siete esquemas MySQL. Los módulos conservan responsabilidades distintas, pero se ejecutan en el mismo proceso; no son seis servidores independientes en la versión actual. Esta organización reduce la complejidad de despliegue y mantiene separada la lógica por responsabilidades.”

“Las páginas HTML se renderizan con Jinja y Bootstrap; hay dos paneles de React. El backend Python llama a procedimientos almacenados de MySQL mediante funciones comunes. No usamos ORM.”

### MoovaTrack

“MoovaTrack es un aporte adicional para observar el movimiento durante la rehabilitación. La interfaz React presenta lecturas, repeticiones y alertas. En esta entrega, los datos se generan de forma simulada; el Arduino y los sensores son la integración prevista, no hardware conectado en vivo. El contador detecta una repetición cuando el ángulo supera 120 grados y luego cae por debajo de 60 grados. Usar dos umbrales, llamado histéresis, reduce el doble conteo causado por fluctuaciones. Se alerta si el ángulo sale de 20 a 160 grados o si la fuerza supera 45 N.”

### Seguridad y calidad

“Aplicamos seguridad por capas: contraseñas con bcrypt, protección CSRF en formularios POST, sesiones firmadas, clave para las rutas internas, validación de datos, límites de intentos, verificación OTP por SMS para operaciones sensibles, control de roles y auditoría. Para los pagos verificamos referencia y monto antes de confirmar. En calidad usamos pruebas automáticas y GitHub Actions: lint, pytest, auditoría de dependencias, revisión de procedimientos SQL, sincronización de Swagger y compilación de React.”

“También identificamos límites que no debemos ocultar: el contador de intentos se guarda en memoria y se reinicia con el servicio; los pagos dependen de la configuración y credenciales del comercio; y el repositorio documenta una limitación de autorización en las páginas de pago y retorno que requiere corregirse.”

### Cierre

“En resumen, MOOVA Clinic integra la reserva, el seguimiento clínico y los indicadores administrativos en una sola aplicación modular. Se añadieron controles de seguridad, auditoría y automatización de tareas. Entre las mejoras pendientes están los bloques horarios, completar la integración real de pagos, registrar las inasistencias desde la interfaz, persistir los bloqueos y reforzar la autorización de las páginas de pago. Gracias; quedo atento a sus preguntas.”

## 2. Arquitectura y archivos importantes

| Archivo o carpeta | Función | Cómo explicarlo |
|---|---|---|
| run.py | Arranque | Inicia la aplicación Flask. |
| gateway/app.py | Rutas públicas, páginas, sesión, CSRF, permisos y coordinación | Es la puerta de entrada y coordina acciones del usuario. |
| services/auth_service/ | Login, usuarios y roles | Comprueba identidad y permisos. |
| services/pacientes_service/ | Pacientes, terapeutas, servicios y consulta de DNI | Gestiona datos de personas y catálogo clínico. |
| services/citas_service/ | Disponibilidad, citas, OTP, recordatorios y riesgo | Aplica reglas del ciclo de citas. |
| services/pagos_service/ | Pagos, proveedores, referencias, webhook y vencimientos | Aísla la lógica de cobro y confirmación. |
| services/notas_service/ | Notas clínicas | Conserva el seguimiento documentado por terapeuta. |
| services/audit_service/ | Bitácora | Registra acciones relevantes. |
| shared/service_client.py | Cliente entre módulos | Invoca rutas internas dentro del mismo proceso. |
| shared/proc.py | Ejecución de procedimientos almacenados | Centraliza llamadas SQL y lectura de resultados. |
| shared/db.py | Conexión MySQL | Abre conexión al esquema apropiado. |
| shared/config.py | Configuración | Lee variables de entorno y secretos. |
| shared/service_auth.py | Protección de rutas internas | Valida la clave de X-Api-Key. |
| shared/rate_limit.py | Límites de intentos | Reduce intentos automatizados. |
| shared/audit.py | Registro común | Deja trazabilidad de acciones. |
| gateway/ficha_pdf.py | Ficha clínica PDF | Separa la generación del PDF de las rutas. |
| templates/ | Plantillas Jinja | HTML renderizado por Flask. |
| frontend/ | Paneles React | Interfaz de KPIs y MoovaTrack. |
| db_split/*.sql | Siete esquemas y procedimientos | Define estructuras y reglas SQL. |
| swagger.yaml | Contrato documentado de API | Describe rutas, parámetros y respuestas. |
| tests/ | Pruebas automáticas | Comprueba comportamientos cubiertos. |
| .github/workflows/ci.yml | Integración continua | Ejecuta controles en push y pull request. |

### Conceptos que debes dominar

- **Gateway:** entrada principal del sistema; atiende páginas y coordina módulos.
- **Blueprint Flask:** agrupación de rutas relacionadas que se registra en una aplicación.
- **Monolito modular:** una aplicación desplegable con módulos separados por responsabilidad.
- **Microservicios:** servicios desplegados por separado y comunicados normalmente por red. Es una versión previa, no la arquitectura actual.
- **Esquema por módulo:** separa el almacenamiento por dominio. El proyecto tiene siete esquemas.
- **Procedimiento almacenado (SP):** programa SQL guardado en MySQL. El backend le pasa parámetros en vez de concatenar entradas en consultas SQL.
- **ORM:** herramienta que mapea objetos del lenguaje a tablas. Este proyecto no usa ORM; invoca SP.
- **API interna:** rutas de módulos bajo /_internal protegidas con una clave.
- **Auditoría:** registro de quién hizo qué y cuándo; no reemplaza las copias de seguridad.
- **CI:** automatización que ejecuta verificaciones cuando se envían cambios.

**Seis módulos y siete esquemas:** los seis módulos de dominio son auth, pacientes, citas, pagos, notas y auditoría. KPIs tiene un esquema adicional; no digas que hay siete microservicios.

## 3. Agendamiento de una cita, paso a paso

1. **DNI:** el navegador pide verificar el DNI. La integración con APIPERU devuelve los nombres mínimos para autocompletar. El servidor limita solicitudes por IP.
2. **Tratamiento:** el paciente selecciona el servicio y el terapeuta.
3. **Disponibilidad:** la interfaz pide las fechas ocupadas. El calendario ayuda, pero no es la autoridad final.
4. **POST de reserva:** el servidor limita intentos, valida nombre, DNI, teléfono y fecha y comprueba que la fecha no sea pasada.
5. **Regla de disponibilidad:** el backend llama a la regla almacenada. Si el especialista ya tiene una cita ese día, responde HTTP 409, que significa conflicto.
6. **Paciente:** busca el DNI; si no hay registro, crea al paciente.
7. **Cita y auditoría:** ejecuta el procedimiento de creación y registra la acción.
8. **Pago pendiente:** si el especialista tiene precio, calcula un anticipo del 50% y crea el registro pendiente.
9. **Sesión:** conserva la cita recién creada para asociar el flujo de pago a esa reserva.

**Guion corto:** “El paciente introduce su DNI, elige tratamiento y especialista, consulta fechas disponibles y confirma. El servidor valida otra vez, comprueba que no exista una cita incompatible, busca o crea al paciente, registra la cita y deja el anticipo pendiente.”

**Si dos personas reservan a la vez:** “El calendario puede quedar desactualizado, por eso el servidor y la regla de base de datos vuelven a comprobar disponibilidad. La segunda solicitud puede recibir un 409 y debe elegir otra fecha.”

**Limitación:** la versión descrita permite una cita por especialista por día; todavía no hay selector de bloques horarios.

## 4. Pagos: flujo, validaciones y límites

1. Al agendar se crea un pago pendiente por el anticipo.
2. El paciente selecciona Yape, Plin o Niubiz según la configuración.
3. El backend inicia o consulta el cobro y conserva una referencia.
4. Al consultar el estado, el backend usa la referencia guardada; no confía en un ID arbitrario del navegador.
5. Compara la referencia con la cita y el monto con el pendiente.
6. Solo tras validar la respuesta llama al procedimiento de confirmación y registra la acción.
7. El webhook permite que el proveedor notifique un evento por separado; exige un token.
8. Un job periódico vence pagos pendientes antiguos y cancela las citas programadas asociadas.

**Qué es webhook:** una notificación que un sistema externo envía a una URL cuando ocurre un evento. Debe autenticarse para que una petición falsa no marque una cita como pagada.

**¿Los pagos son reales?** Comprueba la configuración desplegada. El README dice que los clientes de proveedores consultan APIs reales y, si faltan credenciales, responden “proveedor no configurado”; el Word indica que la demo de sustentación se hará con PAGOS_MODO_DEMO=1. No afirmes que hubo cobros reales sin credenciales y prueba del flujo real.

**Si el proveedor cobra pero la página no se entera:** “El webhook permite que el proveedor notifique al servidor por separado. El servidor valida el token, la referencia y el monto para confirmar el pago sin depender solo de la respuesta del navegador.”

**Vencimiento:** el job revisa pagos pendientes de más de 24 horas (umbral configurable), marca el pago vencido y cancela la cita programada asociada. Si una pasarela confirma un pago después del vencimiento, el procedimiento permite confirmarlo para no dejar un cobro real sin cita. Confirma que job y migraciones estén configurados en la demo.

**Limitación importante:** el README de main documenta que /pago y /retorno no verifican completamente que la cita pertenezca al usuario de la sesión. Una sesión puede distinguir si un identificador existe y ver algunos datos de esa cita. No digas que la autorización es perfecta. La mejora es comprobar el propietario y filtrar las citas pagables de la sesión.

## 5. DNI y código OTP por SMS

- OTP significa código de un solo uso.
- TextBee envía el código al teléfono registrado.
- Según el Word, el código vence en 10 minutos y permite tres intentos.
- Tras validarlo, la sesión conserva la verificación para una acción por 15 minutos.
- La verificación se separa por acción: validar una cancelación no debe autorizar automáticamente una modificación o un tratamiento.
- El backend comprueba que el DNI y la acción coincidan y que la verificación siga vigente.

**Di:** “El DNI identifica el registro; el código SMS comprueba que la persona tiene acceso al teléfono registrado. La autorización caduca y está vinculada a la acción.”

No digas que el SMS prueba por sí solo la identidad legal: comprueba acceso al teléfono registrado.

## 6. MoovaTrack por dentro

**Hardware previsto:** Arduino, MPU-6050 para movimiento/ángulo, FSR 402 para fuerza, Flex Sensor y HC-05 para Bluetooth.

**Estado actual:** la ruta /api/moovatrack/lectura genera lecturas sintéticas con ruido; no vienen del hardware. Requiere sesión. El panel React grafica lecturas con Recharts.

**Histéresis:** una repetición se cuenta cuando la señal pasa por encima de 120° y luego cae por debajo de 60°. Dos umbrales reducen el doble conteo que el ruido puede provocar cerca de un solo límite.

**Alertas:** ángulo fuera de 20°–160° o fuerza superior a 45 N. Son umbrales de la aplicación, no un diagnóstico médico validado.

**Si preguntan por qué simulado:** “El hardware no estaba conectado en esta entrega. La interfaz, el conteo y las alertas se pueden probar con datos simulados; el siguiente paso es integrar las lecturas reales en el mismo punto de entrada.”

## 7. Seguridad: medida y propósito

| Control | Propósito | Cómo explicarlo |
|---|---|---|
| bcrypt | Guarda hashes de contraseña | No almacena la contraseña legible. |
| CSRF | Protege formularios POST | Ayuda a rechazar envíos falsificados desde otros sitios. |
| Sesión firmada | Detecta alteración de cookie | Dificulta que el usuario modifique datos de sesión. |
| SECRET_KEY | Firma la sesión | Es obligatoria; no debe cambiar aleatoriamente en cada arranque. |
| X-Api-Key | Protege rutas internas | Impide invocar módulos internos sin la clave. |
| Validación de servidor | Comprueba entradas | La validación del navegador no basta porque puede manipularse. |
| Rate limit | Limita frecuencia | Reduce intentos automatizados de reserva y login. |
| OTP | Comprueba acceso al teléfono | Tiene caducidad y se vincula al DNI y a la acción. |
| Roles | Limita acciones | Cada rol solo debe acceder a funciones permitidas. |
| Auditoría | Registra eventos | Permite rastrear acciones sensibles. |
| SP con parámetros | Reduce riesgo de inyección SQL | No se construye SQL concatenando texto del usuario. |
| Token webhook | Autentica aviso externo | Rechaza notificaciones sin token válido. |
| Protección /apidocs | Restringe documentación publicada | Solo administradores acceden desde el gateway. |
| Cabeceras HTTP | Añade defensas del navegador | Incluye nosniff, SAMEORIGIN y política de referrer. |

### Limitaciones de seguridad que debes reconocer

1. El contador de login está en memoria: se reinicia al reiniciar y cada worker tiene su contador.
2. El README documenta un oráculo de existencia de citas en /pago y /retorno; falta reforzar la autorización por propietario.
3. El README indica que falta definir una política CSP estricta.
4. La base de datos debería usar credenciales con privilegios mínimos; el Word plantea limitar permisos de auditoría.
5. La seguridad es por capas, no una garantía de que el sistema sea imposible de atacar.

## 8. Pruebas y calidad: cómo demostrar que se verificó el código

### Pipeline de GitHub Actions

1. **Ruff:** lint; detecta problemas de estilo y algunos errores estáticos.
2. **pytest:** ejecuta pruebas automáticas del backend.
3. **pip-audit:** busca vulnerabilidades conocidas en dependencias Python.
4. **Auditoría SQL:** compara procedimientos definidos con los invocados.
5. **Swagger:** comprueba que las rutas documentadas coincidan con las reales.
6. **Frontend:** instala dependencias con npm ci, compila React y comprueba que los bundles no estén vacíos.

### Comandos locales (PowerShell)

    $env:SECRET_KEY="clave-local-de-pruebas"
    $env:API_KEY="clave-interna-local"
    pytest -v
    ruff check .
    python scripts/auditar_procs.py
    python scripts/verificar_swagger.py
    cd frontend
    npm ci
    npm run build

Las claves son ejemplos solo para pruebas locales, nunca para producción.

### ¿Los tests necesitan MySQL?

El README dice que los tests parchean las llamadas a procedimientos, así que no requieren conectarse a MySQL real. Eso comprueba los comportamientos cubiertos, pero no reemplaza una prueba de integración con una base real.

### Número de tests: discrepancia que debes resolver

El Word dice **338 pruebas** y propone ejecutar py -3.12 -m pytest --collect-only -q. El README actual de main dice **27 tests**. Las cifras no coinciden; no repitas una como segura. Ejecuta pytest --collect-only -q en el checkout exacto que se desplegará y revisa el último workflow. Esta guía no afirma que haya ejecutado todas las pruebas en esta sesión.

**Qué significa que CI pase:** los controles configurados terminaron correctamente para ese commit; no significa que todos los escenarios posibles estén libres de defectos ni que las pasarelas reales estén configuradas.

## 9. Demostración: orden y qué decir

### KPIs
“Este panel resume la actividad: citas, estados, ingresos y carga por terapeuta. Los datos vienen del backend y de procedimientos almacenados.”

KPI significa indicador clave de rendimiento; ayuda a observar volumen y comportamiento operativo.

### Reporte de riesgo
“Este reporte señala pacientes que podrían abandonar el tratamiento. Se considera si no tienen cita futura y ha pasado el umbral de días, o si acumulan tres inasistencias registradas.”

El umbral por defecto documentado es 30 días. Nivel alto: tres o más inasistencias o más del doble del umbral. La inasistencia debe estar registrada; si no hay botón en la interfaz, dilo.

### MoovaTrack
“Inicio la simulación. Cuando el ángulo supera 120° y después cae por debajo de 60°, se registra una repetición. Si sale del rango, aparece una alerta. Las lecturas son simuladas.”

### Auditoría
“Esta bitácora permite revisar quién realizó una acción, cuál fue y cuándo ocurrió. Es útil para trazabilidad de citas, pagos y administración.”

### Swagger
“Esta documentación describe rutas, parámetros y respuestas de la API. En el sistema desplegado el acceso está restringido al administrador.”

### Plan B
“Para no interrumpir la sustentación, mostraré la captura de este paso y continuaré.” Lleva capturas actuales; no afirmes que algo funcionó si no lo comprobaste.

## 10. Preguntas probables del jurado

**¿Por qué monolito modular?**  
“Los módulos mantienen responsabilidades separadas, pero se ejecutan en una sola aplicación. Para el alcance actual reduce la complejidad de despliegue sin perder separación lógica.”

**¿Por qué seis módulos y siete esquemas?**  
“Hay seis módulos de dominio y un esquema adicional para KPIs. Por eso son siete esquemas, no siete servicios.”

**¿Por qué no ORM?**  
“La lógica de datos está centralizada en procedimientos almacenados que reciben parámetros. Es una decisión de diseño y requiere mantener sincronizados SQL y backend.”

**¿Qué evita la inyección SQL?**  
“Las entradas se pasan como parámetros y no se concatenan directamente en SQL. También hay validación del lado servidor.”

**¿Cómo evitan una doble reserva?**  
“El backend vuelve a comprobar disponibilidad y la regla de datos impide repetir especialista y día. La segunda petición recibe conflicto.”

**¿Por qué no basta el calendario?**  
“El navegador puede estar desactualizado o manipularse. La decisión final la toma el backend y la base de datos.”

**¿Cómo comprueban el pago?**  
“Se consulta al proveedor y se comparan la referencia guardada y el monto esperado. Solo si coinciden se confirma.”

**¿Qué hace el webhook?**  
“Permite que el proveedor informe el resultado aunque el navegador no reciba la respuesta. Se autentica con el token configurado.”

**¿Los pagos son reales?**  
“Depende del entorno. Para la sustentación se ha previsto modo demo; los cobros reales requieren credenciales y validar el flujo con el proveedor. No presento una simulación como cobro real.”

**¿Qué pasa si el paciente no paga?**  
“El job vence el pago pendiente tras el umbral, cancela la cita programada asociada y libera disponibilidad. Debe estar configurado y desplegado.”

**¿Cómo se identifica al paciente sin cuenta?**  
“Se usa el DNI para localizar o completar datos. Para operaciones sensibles se verifica un código enviado al teléfono registrado.”

**¿Qué es CSRF?**  
“Un ataque que intenta provocar acciones usando una sesión abierta. El token CSRF ayuda a rechazar formularios falsificados.”

**¿bcrypt cifra la contraseña?**  
“Más precisamente, genera un hash con sal y coste de cálculo; no es cifrado reversible.”

**¿Qué es auditoría?**  
“Una bitácora de acciones importantes para rastrear eventos. Complementa los controles de acceso, no los reemplaza.”

**¿MoovaTrack está conectado al Arduino?**  
“No en esta entrega. Las lecturas se simulan para probar interfaz, conteo y alertas. La conexión real es trabajo futuro.”

**¿Cómo funciona la histéresis?**  
“Usa dos umbrales: uno para detectar que el movimiento subió y otro para confirmar que bajó. Reduce el doble conteo por ruido.”

**¿Cómo se detecta riesgo de abandono?**  
“Sin cita futura y superado el umbral de días desde la última cita, o con tres o más inasistencias registradas. El nivel alto usa tres faltas o el doble del umbral.”

**¿Es un diagnóstico clínico?**  
“No. Es una señal administrativa para priorizar el contacto; no demuestra por sí sola que el paciente abandonó.”

**¿Cuántas pruebas tiene?**  
“Hay una discrepancia entre la guía anterior, que decía 338, y el README actual, que menciona 27. Confirmaré el número con pytest en el commit exacto que se evalúa.”

**¿Pasar tests garantiza que no hay errores?**  
“No. Indica que los escenarios cubiertos pasan. Por eso también hay lint, auditoría de dependencias, comprobaciones SQL y Swagger, además de pruebas manuales.”

**¿Qué limitación de seguridad reconocen?**  
“El README documenta que /pago y /retorno necesitan reforzar que la cita pertenezca al usuario de la sesión. También se puede mejorar la persistencia de bloqueos y la política CSP.”

**¿Qué mejorarían primero?**  
“Reforzaría la autorización por propietario en pago/retorno; después persistiría bloqueos, completaría pagos reales, agregaría bloques horarios y permitiría registrar inasistencias desde la interfaz.”

## 11. Diferencias entre el Word y el repositorio

- **Pruebas:** Word dice 338; README de main dice 27. Ejecuta pytest --collect-only -q en el commit evaluado.
- **Despliegue:** Word menciona Railway; README actual describe Render y un servicio moova-gateway. Confirma qué entorno usarás.
- **Pagos:** Word describe demo para la sustentación; README explica que los clientes consultan proveedores reales y responden no configurado sin credenciales. Comprueba el entorno.
- **Autorización:** el Word afirma que solo la sesión dueña puede pagar, pero README documenta una limitación en /pago y /retorno. Reconócela en lugar de afirmar que está resuelta.
- **Bloqueo de login:** ambas fuentes indican que está en memoria; README añade que cada worker mantiene su contador.
- **MoovaTrack:** ambas coinciden en que las lecturas son simuladas y el hardware no está conectado.
- **Inasistencias:** el algoritmo usa el estado no_asistio, pero la guía dice que no hay botón para registrarlo. Comprueba la interfaz antes de decir que se automatiza.

## 12. Checklist antes de exponer

- [ ] Confirmar la rama/commit desplegado.
- [ ] Verificar login de administrador y permisos.
- [ ] Verificar conexión con las siete bases.
- [ ] Confirmar variables obligatorias sin mostrar secretos.
- [ ] Comprobar modo de pagos, credenciales y mensaje de demo.
- [ ] Probar SMS con un número de prueba autorizado.
- [ ] Comprobar job de vencimientos y migraciones.
- [ ] Revisar el último CI: Ruff, pytest, pip-audit, auditoría SQL, Swagger y build React.
- [ ] Confirmar el número real de tests con pytest --collect-only -q.
- [ ] Preparar capturas de KPIs, riesgo, MoovaTrack, auditoría y Swagger.
- [ ] Ensayar el guion y preguntas difíciles.
- [ ] No afirmar que el pago es real, el sensor está conectado o las pruebas pasaron sin comprobarlo.

## 13. Cómo explicar cualquier función del código

Usa esta plantilla:

1. **Propósito:** “Esta función sirve para…”
2. **Entrada:** “Recibe…”
3. **Validación:** “Comprueba…”
4. **Colaboradores:** “Llama a…”
5. **Persistencia:** “Guarda o consulta…”
6. **Salida:** “Devuelve…”
7. **Error:** “Si falla, responde…”
8. **Seguridad:** “No confía solo en el navegador; verifica…”
9. **Prueba:** “El comportamiento se comprueba en…”

Ejemplo de creación de cita: “Recibe los datos de reserva, valida formatos y fecha, consulta disponibilidad, localiza o crea al paciente, guarda la cita, registra auditoría y prepara el pago pendiente. Si el día ya está ocupado, devuelve conflicto; así la regla no depende solo del calendario del navegador.”

Si no recuerdas una línea exacta, explica el flujo y la responsabilidad. Si no has verificado una función, no inventes: di que confirmarás el detalle en el código.

## 14. Plan de estudio

1. Memoriza el guion oral de la sección 1.
2. Dibuja de memoria: navegador → gateway Flask → módulo → procedimiento almacenado → esquema MySQL.
3. Explica sin mirar los flujos de reserva, pago y OTP.
4. Practica seguridad y limitaciones; suelen generar preguntas de seguimiento.
5. Ensaya la demostración y prepara capturas.
6. Revisa las diferencias entre el Word y el README, especialmente pruebas, despliegue y autorización de pagos.
