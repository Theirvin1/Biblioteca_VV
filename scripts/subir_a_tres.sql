-- Sube a 3 pendientes a los 7 estudiantes indicados (todos tienen 2
-- activos, cupo maximo 3): Flujo De Prueba, Maria Gomez, Diana Reyes,
-- Diego Ramirez, Estudiante Devolucion, Andres Vargas y Prueba Modal.
-- (Estudiante Principal se omite a pedido.)

DO $$
DECLARE
    v_ids INT[] := ARRAY[111, 65, 102, 86, 117, 76, 109];
    v_est INT;
    v_ejem_id INT;
    v_bib_id INT;
    v_num INT;
    v_activos INT;
BEGIN
    SELECT id INTO v_bib_id FROM usuarios WHERE rol = 'bibliotecario' ORDER BY id LIMIT 1;

    SELECT COALESCE(MAX(CAST(SUBSTRING(codigo_prestamo FROM 8) AS INTEGER)), 0) INTO v_num
    FROM prestamos WHERE codigo_prestamo ~ '^P-2026-[0-9]+$';

    FOREACH v_est IN ARRAY v_ids LOOP
        SELECT COUNT(*) INTO v_activos FROM prestamos
        WHERE estudiante_id = v_est AND estado = 'activo';

        IF v_activos >= 3 THEN
            RAISE NOTICE 'estudiante % ya tiene % activos, se omite', v_est, v_activos;
            CONTINUE;
        END IF;

        SELECT ej.id INTO v_ejem_id
        FROM ejemplares ej
        JOIN libros l ON l.id = ej.libro_id
        WHERE l.stock_disponible > 0
        ORDER BY l.stock_disponible DESC, ej.id
        LIMIT 1;

        IF v_ejem_id IS NULL THEN
            RAISE EXCEPTION 'Sin stock disponible';
        END IF;

        v_num := v_num + 1;
        INSERT INTO prestamos (codigo_prestamo, estudiante_id, ejemplar_id,
                               bibliotecario_id, fecha_prestamo, fecha_limite,
                               estado, renovaciones)
        VALUES ('P-2026-' || lpad(v_num::TEXT, 4, '0'), v_est, v_ejem_id,
                v_bib_id, NOW(), (NOW() + INTERVAL '7 days')::DATE,
                'activo', 0);
    END LOOP;
END $$;

SELECT e.nombres || ' ' || e.apellidos AS est, COUNT(*) AS pendientes
FROM prestamos p JOIN estudiantes e ON e.id = p.estudiante_id
WHERE p.estado IN ('activo', 'vencido') AND e.id IN (111, 65, 102, 86, 117, 76, 109)
GROUP BY 1 ORDER BY 1;
