-- Crea una cuenta de login por cada estudiante sin usuario enlazado,
-- igual que lo hace la app (username = cedula, rol = 'estudiante').
-- Clave temporal para TODAS las cuentas: Estudiante123*
-- (debe_cambiar_password = true, como en el flujo normal).
-- Re-ejecutable: solo toca estudiantes con usuario_id IS NULL.

-- 1) Crear usuarios faltantes
INSERT INTO usuarios (username, password_hash, rol, activo, intentos_fallidos,
                      bloqueado, debe_cambiar_password, fecha_creacion)
SELECT e.cedula,
       'scrypt:32768:8:1$pjYYjMTXSNtuHkBd$0d3a911d9f9dd35c6eb82e5114bb3931b1d81ac56fe3bd1a15efd47f6befe6d9ab4057e3f91138d6d15c1e25e3f98d738357bc567f1723e314e3319b50e4aa25',
       'estudiante', TRUE, 0, FALSE, TRUE, NOW()
FROM estudiantes e
WHERE e.usuario_id IS NULL
  AND NOT EXISTS (SELECT 1 FROM usuarios u WHERE u.username = e.cedula);

-- 2) Enlazar estudiante <-> usuario
UPDATE estudiantes e
SET usuario_id = u.id
FROM usuarios u
WHERE u.username = e.cedula
  AND e.usuario_id IS NULL;

-- Resumen
SELECT 'usuarios_estudiante' AS grupo, COUNT(*) FROM usuarios WHERE rol = 'estudiante'
UNION ALL
SELECT 'estudiantes_enlazados', COUNT(*) FROM estudiantes WHERE usuario_id IS NOT NULL
UNION ALL
SELECT 'estudiantes_sin_enlazar', COUNT(*) FROM estudiantes WHERE usuario_id IS NULL;

-- Instrucciones:
-- docker cp scripts/seed_usuarios.sql biblio-postgres:/tmp/seed_usuarios.sql
-- docker exec biblio-postgres psql -U biblio -d biblioteca_vv -f /tmp/seed_usuarios.sql
