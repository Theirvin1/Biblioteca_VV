-- Sube a 2 pendientes (activo/vencido) a cada estudiante con menos de 2,
-- creando prestamos ACTIVOS nuevos sin pasar el cupo de 3 activos.
-- Idempotente: segunda corrida no crea nada.

DO $$
DECLARE
    r RECORD;
    v_ejem_id INT;
    v_bib_id INT;
    v_num INT;
    v_pend INT;
BEGIN
    SELECT id INTO v_bib_id FROM usuarios WHERE rol = 'bibliotecario' ORDER BY id LIMIT 1;

    SELECT COALESCE(MAX(CAST(SUBSTRING(codigo_prestamo FROM 8) AS INTEGER)), 0) INTO v_num
    FROM prestamos WHERE codigo_prestamo ~ '^P-2026-[0-9]+$';

    FOR r IN
        SELECT e.id AS est_id,
               COUNT(p.id) AS pendientes,
               COUNT(p.id) FILTER (WHERE p.estado = 'activo') AS activos
        FROM estudiantes e
        LEFT JOIN prestamos p ON p.estudiante_id = e.id AND p.estado IN ('activo', 'vencido')
        GROUP BY e.id
        HAVING COUNT(p.id) < 2
    LOOP
        v_pend := r.pendientes;
        WHILE v_pend < 2 AND r.activos < 3 LOOP
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

            v_pend := v_pend + 1;
            r.activos := r.activos + 1;
        END LOOP;
    END LOOP;
END $$;

SELECT MIN(c) AS min_por_estudiante, MAX(c) AS max_por_estudiante
FROM (SELECT e.id, COUNT(p.id) AS c FROM estudiantes e
      LEFT JOIN prestamos p ON p.estudiante_id = e.id AND p.estado IN ('activo', 'vencido')
      GROUP BY e.id) s;
