-- Elimina fichas duplicadas (ids 110,112,113,114,115) con TODAS sus
-- dependencias. Segunda parte de limpiar_duplicados.sql (la primera ya
-- borro historial y repuso stock/ejemplares).

-- 1) danios_perdidas ligados a sus devoluciones
DELETE FROM danios_perdidas dp
USING devoluciones dv JOIN prestamos p ON p.id = dv.prestamo_id
WHERE dv.id = dp.devolucion_id AND p.estudiante_id IN (110,112,113,114,115);

-- 2) devoluciones de sus prestamos
DELETE FROM devoluciones dv
USING prestamos p
WHERE dv.prestamo_id = p.id AND p.estudiante_id IN (110,112,113,114,115);

-- 3) sesiones de sus usuarios
DELETE FROM sesiones s
USING estudiantes e
WHERE s.usuario_id = e.usuario_id AND e.id IN (110,112,113,114,115);

-- 4) prestamos
DELETE FROM prestamos WHERE estudiante_id IN (110,112,113,114,115);

-- 5) estudiantes
DELETE FROM estudiantes WHERE id IN (110,112,113,114,115);

-- 6) usuarios huerfanos de esas fichas (cedulas 1710034073, 0358897031,
-- 0222544579, 1057910547, 1926780089)
DELETE FROM usuarios u
WHERE u.username IN ('1710034073','0358897031','0222544579','1057910547','1926780089')
  AND NOT EXISTS (SELECT 1 FROM estudiantes e WHERE e.usuario_id = u.id)
  AND NOT EXISTS (SELECT 1 FROM prestamos p WHERE p.bibliotecario_id = u.id)
  AND NOT EXISTS (SELECT 1 FROM devoluciones dv WHERE dv.bibliotecario_id = u.id);

-- Verificacion
SELECT (nombres || ' ' || apellidos) AS est, COUNT(*) AS pendientes
FROM prestamos p JOIN estudiantes e ON e.id = p.estudiante_id
WHERE p.estado IN ('activo', 'vencido')
GROUP BY 1 ORDER BY 2 DESC LIMIT 8;

SELECT (nombres || ' ' || apellidos) AS nombre, COUNT(*) AS fichas
FROM estudiantes GROUP BY 1 HAVING COUNT(*) > 1;
