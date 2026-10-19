-- ============================================================
-- MIGRACION: telefono de usuarios (aviso al terapeuta, FASE 3)
-- Fecha:    2026-10-18
-- Base:     moovacloud_auth   <-- EN ESTA BASE, NO EN CITAS
--
-- ORDEN DE EJECUCION
--   1. Correr este archivo en moovacloud_auth (siempre).
--   2. Desplegar el codigo.
--   El orden 1->2 y 2->1 es indiferente para el flujo existente:
--   sp_actualizar_telefono_usuario es un procedimiento NUEVO y no
--   reemplaza a sp_actualizar_usuario. Si el codigo llega primero,
--   editar usuarios sin telefono sigue funcionando (la llamada al
--   SP nuevo solo ocurre cuando viene "telefono" en el cuerpo del
--   PUT), y solo ese caso nuevo fallaria hasta correr este archivo.
--
-- IMPORTANTE: este archivo solo define procedimientos, NO toca
-- tablas ni inserta datos. Always Data ya tiene datos reales y no
-- se puede reimportar db_split/auth_db.sql completo. Tampoco hace
-- falta ALTER TABLE: la columna usuarios.telefono ya existe
-- (varchar(20) DEFAULT NULL) desde el esquema inicial.
--
-- La version para instalaciones nuevas esta en db_split/auth_db.sql.
-- ============================================================

DELIMITER $$

--
-- sp_listar_usuarios
--   Antes no devolia u.telefono, por eso GET /api/auth/usuarios
--   (y en cascada GET /api/terapeutas, que copia ese campo a
--   "Telefono") siempre devolvia NULL. Sin este cambio
--   citas_service no tiene a quien mandarle el SMS de aviso.
--
DROP PROCEDURE IF EXISTS `sp_listar_usuarios`$$
CREATE PROCEDURE `sp_listar_usuarios`()
BEGIN
    SELECT u.id, u.nombre, u.correo, u.telefono, r.nombre AS rol, u.activo, u.ultimo_acceso
    FROM usuarios u
    JOIN roles r ON u.rol_id = r.id
    ORDER BY r.nombre, u.nombre;
END$$

--
-- sp_actualizar_telefono_usuario  (PROCEDIMIENTO NUEVO)
--   Solo toca la columna telefono. Se dejo aparte de
--   sp_actualizar_usuario a proposito: cambiar la firma de un
--   procedimiento ya existente haria fallar por numero de
--   parametros si el codigo y la migracion llegan a produccion en
--   momentos distintos, y eso romperia editar usuarios.
--
--   NULLIF(p_telefono, ''): "" o NULL limpia el telefono (borrar),
--   cualquier otro valor lo sobrescribe. El formato lo valida el
--   codigo antes de llegar aqui (^9\d{8}$).
--
DROP PROCEDURE IF EXISTS `sp_actualizar_telefono_usuario`$$
CREATE PROCEDURE `sp_actualizar_telefono_usuario`(
    IN p_usuario_id INT, IN p_telefono VARCHAR(20)
)
BEGIN
    UPDATE usuarios
    SET telefono = NULLIF(p_telefono, '')
    WHERE id = p_usuario_id;
    SELECT ROW_COUNT() AS actualizados;
END$$

DELIMITER ;

-- ============================================================
-- FIN 2026-10-18_telefono_usuarios.sql
-- ============================================================
