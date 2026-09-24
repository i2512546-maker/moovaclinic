-- ============================================================
-- kpis_db.sql
-- Base de datos de REPORTES / KPIs (panel admin)
--
-- Las tablas fuente viven en las BBDD de dominio (split FASE 1/2):
--   historial_citas  -> moovacloud_citas
--   pagos, paquetes_sesiones -> moovacloud_pagos
--   terapeutas       -> moovacloud_pacientes
--   servicios        -> moovacloud_pacientes
--   usuarios         -> moovacloud_auth (nombre del terapeuta)
--
-- Estos procedimientos SON de solo lectura (CROSS-DB) y se ejecutan
-- desde un solo servidor MySQL/MariaDB con privilegios sobre todas
-- las bases moovacloud_*. Los consume citas_service via el endpoint
-- GET /api/kpis (shared/proc.call_proc con db_name="moovacloud_kpis").
-- ============================================================

CREATE DATABASE IF NOT EXISTS `moovacloud_kpis` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE `moovacloud_kpis`;

DELIMITER $$

-- --------------------------------------------------------
-- Resumen general de KPIs en un rango de fechas.
-- Las fechas se interpretan en hora de Peru (America/Lima);
-- las columnas de fecha (date/datetime) se almacenan en hora local.
-- Devuelve UNA fila (todas las metricas del panel).
-- --------------------------------------------------------
DROP PROCEDURE IF EXISTS `sp_kpis_resumen`$$
CREATE PROCEDURE `sp_kpis_resumen`(IN p_desde DATE, IN p_hasta DATE)
BEGIN
    DECLARE v_total INT DEFAULT 0;
    DECLARE v_completadas INT DEFAULT 0;
    DECLARE v_canceladas INT DEFAULT 0;
    DECLARE v_programadas INT DEFAULT 0;

    SELECT COUNT(*),
           COALESCE(SUM(estado = 'completada'), 0),
           COALESCE(SUM(estado = 'cancelada'), 0),
           COALESCE(SUM(estado IN ('programada', 'confirmada')), 0)
      INTO v_total, v_completadas, v_canceladas, v_programadas
      FROM moovacloud_citas.historial_citas
     WHERE fecha_cita BETWEEN p_desde AND p_hasta;

    SELECT v_total AS total_citas,
           v_completadas AS citas_completadas,
           v_canceladas AS citas_canceladas,
           v_programadas AS citas_programadas,
           ROUND(100 * v_completadas / NULLIF(v_total, 0), 2) AS tasa_completadas,
           ROUND(100 * v_canceladas / NULLIF(v_total, 0), 2) AS tasa_cancelacion,
           COALESCE((
               SELECT SUM(monto) FROM moovacloud_pagos.pagos
                WHERE estado_pago = 'pagado'
                  AND DATE(fecha_pago) BETWEEN p_desde AND p_hasta
           ), 0) AS ingresos_confirmados,
           COALESCE((
               SELECT SUM(monto) FROM moovacloud_pagos.pagos
                WHERE estado_pago = 'pendiente'
           ), 0) AS ingresos_pendientes,
           (SELECT COUNT(*) FROM moovacloud_pagos.paquetes_sesiones
             WHERE fecha_compra BETWEEN p_desde AND p_hasta) AS paquetes_vendidos,
           COALESCE((
               SELECT SUM(sesiones_usadas) FROM moovacloud_pagos.paquetes_sesiones
                WHERE estado = 'activo'
                  AND fecha_compra BETWEEN p_desde AND p_hasta
           ), 0) AS sesiones_consumidas;
END$$

-- --------------------------------------------------------
-- KPIs por terapeuta en un rango de fechas.
-- Incluye terapeutas sin actividad (totales en 0) para que el
-- panel muestre todo el equipo. El nombre sale de usuarios (auth).
-- Los ingresos se atribuyen al terapeuta via la cita del pago.
-- --------------------------------------------------------
DROP PROCEDURE IF EXISTS `sp_kpis_por_terapeuta`$$
CREATE PROCEDURE `sp_kpis_por_terapeuta`(IN p_desde DATE, IN p_hasta DATE)
BEGIN
    SELECT t.id AS terapeuta_id,
           COALESCE(u.nombre, CONCAT('Terapeuta #', t.id)) AS terapeuta_nombre,
           COALESCE(v.total_citas, 0) AS total_citas,
           COALESCE(v.completadas, 0) AS citas_completadas,
           COALESCE(ROUND(100 * v.completadas / NULLIF(v.total_citas, 0), 2), 0) AS tasa_completadas,
           COALESCE(v.ingresos, 0) AS ingresos
      FROM moovacloud_pacientes.terapeutas t
      LEFT JOIN moovacloud_auth.usuarios u ON u.id = t.usuario_id
      LEFT JOIN (
            SELECT h.terapeuta_id,
                   COUNT(*) AS total_citas,
                   COALESCE(SUM(h.estado = 'completada'), 0) AS completadas,
                   COALESCE((
                       SELECT SUM(pg.monto)
                         FROM moovacloud_pagos.pagos pg
                         JOIN moovacloud_citas.historial_citas hc ON hc.id = pg.cita_id
                        WHERE pg.estado_pago = 'pagado'
                          AND DATE(pg.fecha_pago) BETWEEN p_desde AND p_hasta
                          AND hc.terapeuta_id = h.terapeuta_id
                   ), 0) AS ingresos
              FROM moovacloud_citas.historial_citas h
             WHERE h.fecha_cita BETWEEN p_desde AND p_hasta
             GROUP BY h.terapeuta_id
      ) v ON v.terapeuta_id = t.id
     ORDER BY v.ingresos DESC, v.total_citas DESC;
END$$

DELIMITER ;