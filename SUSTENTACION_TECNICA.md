# Guía de sustentación técnica — MOOVA Clinic

## 1. Arquitectura utilizada

**MOOVA Clinic utiliza una arquitectura de monolito modular con Flask.** La aplicación se despliega en un único proceso web. Los módulos de autenticación, pacientes, citas, pagos, notas clínicas y auditoría mantienen sus responsabilidades separadas, pero se ejecutan dentro de la misma aplicación.

Las llamadas entre módulos se despachan dentro del proceso, sin hacer una llamada de red entre microservicios. El proyecto conserva esquemas de base de datos separados por dominio; eso no convierte la aplicación en una arquitectura de microservicios porque los módulos no se despliegan como servicios independientes.

### ¿Por qué es conveniente para el proyecto?

- La clínica necesita un sistema integrado de tamaño acotado, no servicios independientes con despliegues y monitoreo separados.
- Simplifica el despliegue, las pruebas, el diagnóstico de errores y el mantenimiento.
- Reduce la latencia y los fallos asociados a llamadas HTTP entre servicios.
- Permite conservar límites claros entre dominios sin pagar el coste operativo de microservicios.

### Desventajas y cómo mitigarlas

| Desventaja del monolito | Mitigación aplicada o recomendada |
|---|---|
| Un fallo crítico puede afectar a toda la aplicación. | Validación de entradas, manejo de errores, logs, pruebas automatizadas y copias de seguridad. |
| No se escala cada módulo por separado. | Optimizar consultas e índices primero; escalar el proceso completo si la carga lo requiere. |
| El código puede acoplarse si no se respetan los límites. | Mantener módulos separados, blueprints, funciones de dominio y contratos de API internos. |
| Un despliegue actualiza todos los módulos. | Automatizar pruebas en CI y desplegar cambios pequeños con migraciones documentadas. |
| Los esquemas de datos separados requieren coordinación. | Mantener migraciones versionadas y validar que las referencias entre dominios sean consistentes. |

**Respuesta breve para el jurado:**

> “Elegimos un monolito modular porque el alcance y el tamaño de MOOVA Clinic no justificaban la complejidad operativa de los microservicios. Mantuvimos los módulos separados por responsabilidad, pero dentro de un solo proceso, lo que simplifica el despliegue y reduce la latencia entre módulos. Sus principales riesgos son el acoplamiento y que un fallo pueda afectar a toda la aplicación; los mitigamos con modularidad, validaciones, pruebas, logs y migraciones controladas.”

## 2. Tecnologías y función

| Tecnología | Uso en MOOVA Clinic |
|---|---|
| Python | Lenguaje principal del backend. |
| Flask | Framework web: rutas, solicitudes, respuestas y aplicación principal. |
| Jinja2 | Plantillas HTML dinámicas renderizadas desde Flask. |
| HTML, CSS y JavaScript | Estructura, estilos e interacciones de las páginas. |
| Bootstrap | Componentes visuales y diseño adaptable. |
| React | Paneles interactivos concretos, como los indicadores (KPIs) y MoovaTrack. No es necesario afirmar que toda la interfaz usa React. |
| MySQL | Persistencia de usuarios, pacientes, citas, pagos, notas y auditoría en los esquemas configurados. |
| Flask-Bcrypt | Hash de contraseñas. |
| Flask-WTF / CSRFProtect | Protección de formularios contra solicitudes CSRF. |
| Flasgger / Swagger | Documentación de endpoints de la API. |
| APScheduler | Programación de recordatorios y tareas automáticas habilitadas. |
| Gunicorn | Servidor de aplicación para ejecutar Flask en despliegue. |
| TextBee | Envío de SMS, por ejemplo, avisos y códigos de verificación cuando está configurado. |
| APIsPerú | Consulta de datos por DNI, cuando el proveedor responde correctamente. |

## 3. Aportes técnicos del proyecto

Para responder “¿qué aportó técnicamente?”, explica el problema, la solución y cómo se comprueba:

- **Gestión de citas:** validación de datos, consulta de disponibilidad, asignación de terapeuta y control del flujo de reserva.
- **Seguridad:** contraseñas con hash, validación de sesiones y roles, protección CSRF y verificación OTP para operaciones sensibles.
- **Seguimiento clínico:** historial por paciente y notas vinculadas a sus citas.
- **Automatización:** recordatorios y avisos por SMS cuando los servicios externos están configurados.
- **Indicadores y reportes:** KPIs por rango de fechas, resumen por terapeuta y exportación de resultados.
- **Mantenibilidad:** módulos separados por dominio, procedimientos almacenados, migraciones y pruebas automatizadas.

Menciona solo las funciones que estén activas y que puedas demostrar durante la sustentación. No afirmes mejoras porcentuales sin mediciones antes/después.

## 4. Roles y aportes individuales del equipo

Completar esta tabla con los nombres y las tareas reales del equipo. No atribuir código o responsabilidades que una persona no haya realizado.

| Integrante | Responsabilidad principal | Aporte verificable |
|---|---|---|
| [Nombre 1] | [Análisis / coordinación / documentación] | [Entregable o sección realizada] |
| [Nombre 2] | [Backend / base de datos] | [Rutas, procedimientos o validaciones realizadas] |
| [Nombre 3] | [Frontend / experiencia de usuario] | [Pantallas o componentes realizados] |
| [Nombre 4, si aplica] | [Pruebas / integración] | [Casos de prueba, integración o despliegue] |

Si una persona asumió varias tareas, indícalas. Si una tarea fue compartida, describe qué hizo cada integrante concretamente.

## 5. Cómo explicar los KPI

> “Los KPI son indicadores clave de desempeño. Se utilizan para evaluar si los procesos que el sistema busca mejorar están cumpliendo sus objetivos. En MOOVA Clinic permiten revisar el volumen y estado de las citas, las tasas de completadas y canceladas, los ingresos y la actividad por terapeuta. Para demostrar una mejora real, debemos comparar mediciones obtenidas antes y después de implementar el sistema.”

Distingue entre **indicador calculado**, **meta propuesta** y **resultado medido**. No son equivalentes.

## 6. Si preguntan por qué el sistema estaba lento

> “En una arquitectura modular, el tiempo de respuesta también depende de las consultas a la base de datos y de cuántas veces se solicitan datos repetidos. Por eso, estamos reduciendo las llamadas repetitivas, evitando consultas por cada paciente cuando una consulta agrupada es suficiente y revisando los procedimientos SQL. La mejora final debe comprobarse midiendo los tiempos de respuesta antes y después.”

## 7. Demostración recomendada

1. Iniciar sesión con un usuario de cada rol.
2. Registrar una cita y comprobar que solo aparece como programada después de completar el pago requerido.
3. Entrar como terapeuta y verificar que ve las citas y pacientes asignados a su perfil.
4. Abrir el historial de un paciente y mostrar las notas clínicas.
5. Abrir Reportes, filtrar por fechas y exportar el CSV.
6. Mostrar el formato fijo de impresión de la ficha y el reporte.
