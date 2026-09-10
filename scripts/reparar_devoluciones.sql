-- Repara prestamos activo/vencido que YA tienen devolucion (artefacto del
-- seed masivo, que cargo con triggers desactivados): aplica los efectos que
-- fn_actualizar_stock_devolucion habria hecho y los marca devueltos para
-- que salgan de Pendientes.

-- Margen para chk_libros_stock_coherente
UPDATE libros SET stock_total = stock_disponible + 10 WHERE stock_total - stock_disponible < 10;

-- Repone stock por libro
WITH dev AS (
    SELECT p.ejemplar_id, e.libro_id
    FROM devoluciones d
    JOIN prestamos p ON p.id = d.prestamo_id
    JOIN ejemplares e ON e.id = p.ejemplar_id
    WHERE p.estado IN ('activo', 'vencido')
)
UPDATE libros l SET stock_disponible = stock_disponible + s.cnt
FROM (SELECT libro_id, COUNT(*) AS cnt FROM dev GROUP BY libro_id) s
WHERE s.libro_id = l.id AND s.cnt > 0;

-- Ejemplares a disponible (solo los que siguen marcados prestado)
UPDATE ejemplares ej SET estado = 'disponible'
FROM devoluciones d
JOIN prestamos p ON p.id = d.prestamo_id
WHERE d.prestamo_id = p.id
  AND p.ejemplar_id = ej.id
  AND p.estado IN ('activo', 'vencido')
  AND ej.estado = 'prestado';

-- Historial (lo que el trigger habria escrito)
INSERT INTO historial_inventario (ejemplar_id, tipo_movimiento, estado_anterior, estado_nuevo, usuario_id, prestamo_id)
SELECT p.ejemplar_id, 'devolucion', 'prestado', 'disponible', d.bibliotecario_id, d.prestamo_id
FROM devoluciones d
JOIN prestamos p ON p.id = d.prestamo_id
WHERE p.estado IN ('activo', 'vencido')
  AND NOT EXISTS (
      SELECT 1 FROM historial_inventario h
      WHERE h.prestamo_id = d.prestamo_id AND h.tipo_movimiento = 'devolucion'
  );

-- Marca devueltos (dispara la auditoria normal de UPDATE de prestamos)
UPDATE prestamos p SET estado = 'devuelto'
FROM devoluciones d
WHERE d.prestamo_id = p.id AND p.estado IN ('activo', 'vencido');

SELECT COUNT(*) AS reparados_devueltos FROM prestamos p
JOIN devoluciones d ON d.prestamo_id = p.id WHERE p.estado = 'devuelto';
SELECT COUNT(*) AS pendientes_restantes FROM prestamos WHERE estado IN ('activo', 'vencido');
