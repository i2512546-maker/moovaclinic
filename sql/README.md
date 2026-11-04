# Organización de SQL en MOOVA Clinic

## Fuentes vigentes

- `database/moovaclinic_unificada.sql`: definiciones de procedimientos para el esquema MySQL unificado. No crea tablas ni importa datos.
- `db_split/migraciones/`: migraciones incrementales. Antes de ejecutarlas, confirma que la base destino coincide con la configuración `DB_NAME` y que el esquema ya contiene las tablas requeridas.
- `db_split/*.sql`: scripts de bootstrap del diseño histórico de siete esquemas. No importarlos en la instalación unificada actual.

## Historial

Los scripts antiguos o destructivos se conservan en `legacy/` únicamente para
consulta y recuperación de instalaciones anteriores. No son parte del flujo
normal de despliegue.
