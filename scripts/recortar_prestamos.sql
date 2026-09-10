-- Recorte: conservar como maximo los 3 activos mas recientes por estudiante.
DELETE FROM prestamos p
USING (
    SELECT id, ROW_NUMBER() OVER (
        PARTITION BY estudiante_id ORDER BY fecha_prestamo DESC, id DESC
    ) AS rn
    FROM prestamos WHERE estado = 'activo'
) s
WHERE p.id = s.id AND s.rn > 3
  AND NOT EXISTS (SELECT 1 FROM devoluciones d WHERE d.prestamo_id = p.id);

SELECT e.nombres || ' ' || e.apellidos AS estudiante, COUNT(*) AS activos
FROM prestamos p JOIN estudiantes e ON e.id = p.estudiante_id
WHERE p.estado = 'activo'
GROUP BY 1 ORDER BY 2 DESC, 1;
