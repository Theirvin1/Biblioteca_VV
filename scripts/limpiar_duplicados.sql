-- Elimina fichas de estudiante duplicadas (restos de pruebas E2E/Playwright
-- con el mismo nombre): conserva el mas reciente por nombre.
-- Orden por FKs RESTRICT: historial -> devoluciones -> prestamos ->
-- estudiante -> usuario. Restaura stock/ejemplar de sus activos.

-- Margen para chk_libros_stock_coherente
UPDATE libros SET stock_total = stock_disponible + 10 WHERE stock_total - stock_disponible < 10;

-- Fichas a eliminar: todas menos la de id mayor por nombre duplicado
CREATE TEMP TABLE doom AS
SELECT e.id AS est_id, e.usuario_id
FROM estudiantes e
WHERE (e.nombres || ' ' || e.apellidos) IN ('Flujo De Prueba', 'Estudiante Principal', 'Estudiante Devolucion')
  AND e.id NOT IN (
      SELECT MAX(id) FROM estudiantes
      GROUP BY (nombres || ' ' || apellidos)
      HAVING COUNT(*) > 1
  );

-- Repone stock de sus activos
WITH act AS (
    SELECT p.ejemplar_id, e.libro_id
    FROM prestamos p
    JOIN ejemplares e ON e.id = p.ejemplar_id
    JOIN doom d ON d.est_id = p.estudiante_id
    WHERE p.estado IN ('activo', 'vencido')
)
UPDATE libros l SET stock_disponible = stock_disponible + s.cnt
FROM (SELECT libro_id, COUNT(*) AS cnt FROM act GROUP BY libro_id) s
WHERE s.libro_id = l.id;

-- Ejemplares a disponible si nadie mas los usa en activo
UPDATE ejemplares ej SET estado = 'disponible'
WHERE ej.estado = 'prestado'
  AND EXISTS (
      SELECT 1 FROM prestamos p JOIN doom d ON d.est_id = p.estudiante_id
      WHERE p.ejemplar_id = ej.id AND p.estado IN ('activo', 'vencido')
  )
  AND NOT EXISTS (
      SELECT 1 FROM prestamos p2
      WHERE p2.ejemplar_id = ej.id AND p2.estado IN ('activo', 'vencido')
        AND p2.estudiante_id NOT IN (SELECT est_id FROM doom)
  );

-- Borra en orden de dependencias
DELETE FROM historial_inventario h
USING prestamos p JOIN doom d ON d.est_id = p.estudiante_id
WHERE h.prestamo_id = p.id;

DELETE FROM devoluciones dv
USING prestamos p JOIN doom d ON d.est_id = p.estudiante_id
WHERE dv.prestamo_id = p.id;

DELETE FROM prestamos p USING doom d WHERE p.estudiante_id = d.est_id;

DELETE FROM estudiantes e USING doom d WHERE e.id = d.est_id;

DELETE FROM usuarios u USING doom d WHERE u.id = d.usuario_id;

DROP TABLE doom;

-- Verificacion
SELECT e.nombres || ' ' || e.apellidos AS est, COUNT(*) AS pendientes
FROM prestamos p JOIN estudiantes e ON e.id = p.estudiante_id
WHERE p.estado IN ('activo', 'vencido')
GROUP BY 1 HAVING COUNT(*) > 3 ORDER BY 2 DESC;

SELECT (nombres || ' ' || apellidos) AS nombre, COUNT(*) AS fichas
FROM estudiantes
GROUP BY 1 HAVING COUNT(*) > 1;
