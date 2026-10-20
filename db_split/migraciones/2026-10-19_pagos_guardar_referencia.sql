-- ============================================================
-- MIGRACION: sp_guardar_referencia solo actualiza pagos pendientes
--             (FASE S7, punto b)
-- Fecha:    2026-10-19
-- Base:     moovacloud_pagos   <-- EN ESTA BASE
--
-- ORDEN DE EJECUCION
--   1. Correr este archivo en moovacloud_pagos (siempre).
--   2. Desplegar el codigo.
--   El orden 1->2 es el correcto: si el codigo llega primero, el
--   /iniciar de Yape/Plin puede seguir pisando la referencia de un
--   pago ya pagado hasta que se corra este archivo. 2->1 no rompe
--   nada porque el cambio es solo una condicion extra en el UPDATE.
--
-- MOTIVO
--   El UPDATE no miraba estado_pago, asi que /api/pagos/{yape|plin}/
--   iniciar sobrescribia la referencia de un pago que ya estaba
--   pagado (o vencido). Al ser esa referencia con la que despues se
--   consulta al proveedor, se podia sustituir el cobro legitimo de
--   una cita por otro. La comprobacion de referencia y monto la hace
--   ahora el codigo (pagos_service.routes._cobro_valido_para_cita),
--   pero el dato que se guarda tiene que ser coherente desde aqui.
--
-- IMPORTANTE: este archivo solo define un procedimiento, NO toca
-- tablas ni inserta datos. Always Data ya tiene datos reales y no
-- se puede reimportar db_split/pagos_db.sql completo.
--
-- La version para instalaciones nuevas esta en db_split/pagos_db.sql.
-- ============================================================

DELIMITER $$

--
-- sp_guardar_referencia
--   Solo guarda la referencia mientras el pago sigue en 'pendiente'.
--   Si ya estaba pagado, el UPDATE afecta 0 filas y la referencia se
--   queda como esta: el cobro pagado no se puede reemplazar.
--
DROP PROCEDURE IF EXISTS `sp_guardar_referencia`$$
CREATE PROCEDURE `sp_guardar_referencia`(IN p_cita_id INT, IN p_cobro_id VARCHAR(100))
BEGIN
    -- Solo mientras el pago sigue pendiente. Sin esta condicion cualquier
    -- /iniciar pisaba la referencia de un pago ya pagado, y con ella
    -- pasaba a ser el cobro "valido" de la cita.
    UPDATE pagos
    SET referencia = p_cobro_id
    WHERE cita_id = p_cita_id AND estado_pago = 'pendiente';
END$$

DELIMITER ;

-- ============================================================
-- FIN 2026-10-19_pagos_guardar_referencia.sql
-- ============================================================
