-- Normaliza prestamos ACTIVOS a 2-3 por estudiante (cupo maximo: 3).
-- 1) Elimina activos excedentes (conserva los 3 mas recientes por estudiante).
-- 2) Completa con prestamos nuevos a quienes tienen menos de 2.
-- Re-ejecutable e idempotente en la practica (segunda corrida no cambia nada).

-- 1) Recortar excedentes (solo activos sin devolucion asociada)
DELETE FROM prestamos p
USING (
    SELECT id, ROW_NUMBER() OVER (
        PARTITION BY estudiante_id ORDER BY fecha_prestamo DESC, id DESC
    ) AS rn
    FROM prestamos WHERE estado = 'activo'
) s
WHERE p.id = s.id AND s.rn > 3
  AND NOT EXISTS (SELECT 1 FROM devoluciones d WHERE d.prestamo_id = p.id);

-- 2) Completar a quienes tienen menos de 2 activos (uno por uno)
DO $$
DECLARE
    r RECORD;
    v_ejem_id INT;
    v_bib_id INT;
    v_num INT;
BEGIN
    SELECT id INTO v_bib_id FROM usuarios WHERE rol = 'bibliotecario' ORDER BY id LIMIT 1;

    SELECT COALESCE(MAX(CAST(SUBSTRING(codigo_prestamo FROM 8) AS INTEGER)), 0) INTO v_num
    FROM prestamos WHERE codigo_prestamo ~ '^P-2026-[0-9]+$';

    FOR r IN
        SELECT e.id AS est_id, COUNT(p.id) AS activos
        FROM estudiantes e
        LEFT JOIN prestamos p ON p.estudiante_id = e.id AND p.estado = 'activo'
        GROUP BY e.id
        HAVING COUNT(p.id) < 2
    LOOP
        WHILE r.activos < 2 LOOP
            -- ejemplar de un libro con stock disponible
            SELECT ej.id INTO v_ejem_id
            FROM ejemplares ej
            JOIN libros l ON l.id = ej.libro_id
            WHERE l.stock_disponible > 0
            ORDER BY l.stock_disponible DESC, ej.id
            LIMIT 1;

            IF v_ejem_id IS NULL THEN
                RAISE EXCEPTION 'Sin stock disponible para completar prestamos';
            END IF;

            v_num := v_num + 1;
            INSERT INTO prestamos (codigo_prestamo, estudiante_id, ejemplar_id,
                                   bibliotecario_id, fecha_prestamo, fecha_limite,
                                   estado, renovaciones)
            VALUES ('P-2026-' || lpad(v_num::TEXT, 4, '0'), r.est_id, v_ejem_id,
                    v_bib_id, NOW(), (NOW() + INTERVAL '7 days')::DATE,
                    'activo', 0);

            r.activos := r.activos + 1;
        END LOOP;
    END LOOP;
END $$;

-- 3) Verificacion
SELECT e.nombres || ' ' || e.apellidos AS estudiante, COUNT(*) AS activos
FROM prestamos p JOIN estudiantes e ON e.id = p.estudiante_id
WHERE p.estado = 'activo'
GROUP BY 1 ORDER BY 2, 1;
