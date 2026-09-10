-- Deja maximo 3 pendientes (activo/vencido) por NOMBRE de estudiante,
-- devolviendo los mas antiguos con el flujo real: el trigger
-- fn_actualizar_stock_devolucion pone el prestamo en devuelto, repone
-- stock/ejemplar y escribe historial. Multa coherente con los dias de
-- retraso (0.50 por dia, como configuracion_sistema.multa_diaria).

WITH ranked AS (
    SELECT p.id,
           ROW_NUMBER() OVER (
               PARTITION BY (e.nombres || ' ' || e.apellidos)
               ORDER BY p.fecha_prestamo DESC, p.id DESC
           ) AS rn
    FROM prestamos p
    JOIN estudiantes e ON e.id = p.estudiante_id
    WHERE p.estado IN ('activo', 'vencido')
),
objetivo AS (
    SELECT id FROM ranked WHERE rn > 3
)
INSERT INTO devoluciones (prestamo_id, bibliotecario_id, fecha_devolucion,
                          estado_ejemplar, dias_retraso, multa_generada,
                          multa_pagada, observaciones)
SELECT p.id,
       p.bibliotecario_id,
       NOW(),
       'bueno',
       GREATEST(0, CURRENT_DATE - p.fecha_limite),
       ROUND((GREATEST(0, CURRENT_DATE - p.fecha_limite) * 0.50)::NUMERIC, 2),
       FALSE,
       'Devolucion de normalizacion: tope de 3 pendientes por estudiante'
FROM prestamos p
JOIN objetivo o ON o.id = p.id
WHERE NOT EXISTS (SELECT 1 FROM devoluciones d WHERE d.prestamo_id = p.id);

-- Verificacion: nadie con mas de 3 pendientes
SELECT e.nombres || ' ' || e.apellidos AS est, COUNT(*) AS pendientes
FROM prestamos p JOIN estudiantes e ON e.id = p.estudiante_id
WHERE p.estado IN ('activo', 'vencido')
GROUP BY 1 HAVING COUNT(*) > 3 ORDER BY 2 DESC;

SELECT COUNT(*) AS pendientes_totales FROM prestamos WHERE estado IN ('activo', 'vencido');
