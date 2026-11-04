-- Optimiza los filtros por fecha de pago para que MySQL pueda usar idx_fecha.
-- Ejecutar en la base configurada por DB_NAME (por defecto moovacloud_database).
DELIMITER //
DROP PROCEDURE IF EXISTS `sp_kpis_resumen`//
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
      FROM historial_citas
     WHERE fecha_cita BETWEEN p_desde AND p_hasta;

    SELECT v_total AS total_citas,
           v_completadas AS citas_completadas,
           v_canceladas AS citas_canceladas,
           v_programadas AS citas_programadas,
           ROUND(100 * v_completadas / NULLIF(v_total, 0), 2) AS tasa_completadas,
           ROUND(100 * v_canceladas / NULLIF(v_total, 0), 2) AS tasa_cancelacion,
           COALESCE((
               SELECT SUM(monto) FROM pagos
                WHERE estado_pago = 'pagado'
                  AND fecha_pago >= p_desde AND fecha_pago < DATE_ADD(p_hasta, INTERVAL 1 DAY)
           ), 0) AS ingresos_confirmados,
           COALESCE((
               SELECT SUM(monto) FROM pagos
                WHERE estado_pago = 'pendiente'
           ), 0) AS ingresos_pendientes,
           (SELECT COUNT(*) FROM paquetes_sesiones
             WHERE fecha_compra BETWEEN p_desde AND p_hasta) AS paquetes_vendidos,
           COALESCE((
               SELECT SUM(sesiones_usadas) FROM paquetes_sesiones
                WHERE estado = 'activo'
                  AND fecha_compra BETWEEN p_desde AND p_hasta
           ), 0) AS sesiones_consumidas;
END//

-- --------------------------------------------------------
-- KPIs por terapeuta en un rango de fechas.
-- Incluye terapeutas sin actividad (totales en 0) para que el
-- panel muestre todo el equipo. El nombre sale de usuarios (auth).
-- Los ingresos se atribuyen al terapeuta via la cita del pago.
-- --------------------------------------------------------
DROP PROCEDURE IF EXISTS `sp_kpis_por_terapeuta`//
CREATE PROCEDURE `sp_kpis_por_terapeuta`(IN p_desde DATE, IN p_hasta DATE)
BEGIN
    SELECT t.id AS terapeuta_id,
           COALESCE(u.nombre, CONCAT('Terapeuta #', t.id)) AS terapeuta_nombre,
           COALESCE(v.total_citas, 0) AS total_citas,
           COALESCE(v.completadas, 0) AS citas_completadas,
           COALESCE(ROUND(100 * v.completadas / NULLIF(v.total_citas, 0), 2), 0) AS tasa_completadas,
           COALESCE(v.ingresos, 0) AS ingresos
      FROM terapeutas t
      LEFT JOIN usuarios u ON u.id = t.usuario_id
      LEFT JOIN (
            SELECT h.terapeuta_id,
                   COUNT(*) AS total_citas,
                   COALESCE(SUM(h.estado = 'completada'), 0) AS completadas,
                   COALESCE((
                       SELECT SUM(pg.monto)
                         FROM pagos pg
                         JOIN historial_citas hc ON hc.id = pg.cita_id
                        WHERE pg.estado_pago = 'pagado'
                          AND pg.fecha_pago >= p_desde AND pg.fecha_pago < DATE_ADD(p_hasta, INTERVAL 1 DAY)
                          AND hc.terapeuta_id = h.terapeuta_id
                   ), 0) AS ingresos
              FROM historial_citas h
             WHERE h.fecha_cita BETWEEN p_desde AND p_hasta
               AND h.estado <> 'pendiente_pago'
             GROUP BY h.terapeuta_id
      ) v ON v.terapeuta_id = t.id
     ORDER BY v.ingresos DESC, v.total_citas DESC;
END//
DELIMITER ;
