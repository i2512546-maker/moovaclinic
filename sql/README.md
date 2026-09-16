# SQL del proyecto

Esta carpeta centraliza los scripts SQL operativos del proyecto.

## Estructura

- `core/` — scripts válidos y necesarios para el funcionamiento de la aplicación.
- `legacy/` — scripts históricos, de migración o no activos; conservar solo como referencia.

## Regla recomendada

- Usar `core/` para entorno de desarrollo y producción.
- Revisar `legacy/` solo si se necesita diagnosticar una migración antigua.
- Evitar mezclar los scripts antiguos con la lógica viva de la app.
