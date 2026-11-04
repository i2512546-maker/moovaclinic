# SQL legado

Estos archivos se conservan solo como referencia histórica. No forman parte
del despliegue normal de MOOVA Clinic.

- `01_procedures_legacy.sql`: procedimientos de una fase anterior; no contiene
  el conjunto completo que requiere el runtime actual.
- `02_reset_dev_split.sql`: script destructivo que elimina datos y reinicia
  contadores en siete esquemas antiguos. **No ejecutarlo en producción ni
  contra la base unificada actual.**

La fuente vigente de procedimientos está en
`database/moovaclinic_unificada.sql`; las actualizaciones incrementales
están en `db_split/migraciones/`.
