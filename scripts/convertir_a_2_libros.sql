-- 1) Revertir los 7 prestamos individuales creados por subir_a_tres.sql
-- (codigos P-2026-0053 a 0059): restaura stock/ejemplar y borra el rastro.

-- Margen para los ajustes de stock
UPDATE libros SET stock_total = stock_disponible + 10 WHERE stock_total - stock_disponible < 10;

-- Repone stock de los 7
WITH mias AS (
    SELECT p.id, e.libro_id
    FROM prestamos p JOIN ejemplares e ON e.id = p.ejemplar_id
    WHERE p.codigo_prestamo IN ('P-2026-0053','P-2026-0054','P-2026-0055',
        'P-2026-0056','P-2026-0057','P-2026-0058','P-2026-0059')
      AND p.estado = 'activo'
)
UPDATE libros l SET stock_disponible = stock_disponible + s.cnt
FROM (SELECT libro_id, COUNT(*) AS cnt FROM mias GROUP BY libro_id) s
WHERE s.libro_id = l.id;

-- Ejemplares a disponible si nadie mas los usa en activo/vencido
UPDATE ejemplares ej SET estado = 'disponible'
WHERE ej.id IN (
    SELECT p.ejemplar_id FROM prestamos p
    WHERE p.codigo_prestamo IN ('P-2026-0053','P-2026-0054','P-2026-0055',
        'P-2026-0056','P-2026-0057','P-2026-0058','P-2026-0059')
)
AND NOT EXISTS (
    SELECT 1 FROM prestamos p2
    WHERE p2.ejemplar_id = ej.id AND p2.estado IN ('activo', 'vencido')
      AND p2.codigo_prestamo NOT IN ('P-2026-0053','P-2026-0054','P-2026-0055',
        'P-2026-0056','P-2026-0057','P-2026-0058','P-2026-0059')
);

-- Borra historial + prestamos
DELETE FROM historial_inventario WHERE prestamo_id IN (
    SELECT id FROM prestamos WHERE codigo_prestamo IN ('P-2026-0053','P-2026-0054',
    'P-2026-0055','P-2026-0056','P-2026-0057','P-2026-0058','P-2026-0059'));

DELETE FROM prestamos WHERE codigo_prestamo IN ('P-2026-0053','P-2026-0054',
    'P-2026-0055','P-2026-0056','P-2026-0057','P-2026-0058','P-2026-0059')
    AND estado = 'activo'
    AND NOT EXISTS (SELECT 1 FROM devoluciones d WHERE d.prestamo_id = prestamos.id);

-- 2) Convertir las 9 operaciones individuales en operaciones de 2 libros:
-- se les asigna grupo y se agrega el segundo libro (otro titulo con stock).
DO $$
DECLARE
    v_codigos TEXT[] := ARRAY['P-2026-0052','P-2026-0051','P-2026-0049',
        'P-2026-0047','P-2026-0045','P-2026-0044',
        'P-2026-0040','P-2026-0038','P-2026-0036'];
    v_cod TEXT;
    v_p RECORD;
    v_ejem_id INT;
    v_num INT;
    v_grp INT;
BEGIN
    SELECT COALESCE(MAX(CAST(SUBSTRING(codigo_prestamo FROM 8) AS INTEGER)), 0) INTO v_num
    FROM prestamos WHERE codigo_prestamo ~ '^P-2026-[0-9]+$';

    SELECT COALESCE(MAX(CAST(SUBSTRING(grupo_prestamo FROM 10) AS INTEGER)), 0) INTO v_grp
    FROM prestamos WHERE grupo_prestamo ~ '^GRP-2026-[0-9]+$';

    FOREACH v_cod IN ARRAY v_codigos LOOP
        SELECT * INTO v_p FROM prestamos WHERE codigo_prestamo = v_cod;

        IF NOT FOUND THEN
            RAISE NOTICE 'no existe %, se omite', v_cod;
            CONTINUE;
        END IF;
        IF v_p.grupo_prestamo IS NOT NULL THEN
            RAISE NOTICE '% ya tiene grupo, se omite', v_cod;
            CONTINUE;
        END IF;

        -- segundo libro: otro titulo con stock
        SELECT ej.id INTO v_ejem_id
        FROM ejemplares ej
        JOIN libros l ON l.id = ej.libro_id
        WHERE l.stock_disponible > 0 AND l.id <> (
            SELECT libro_id FROM ejemplares WHERE id = v_p.ejemplar_id
        )
        ORDER BY l.stock_disponible DESC, ej.id
        LIMIT 1;

        IF v_ejem_id IS NULL THEN
            RAISE EXCEPTION 'Sin stock para el segundo libro de %', v_cod;
        END IF;

        v_num := v_num + 1;
        v_grp := v_grp + 1;

        UPDATE prestamos SET grupo_prestamo = 'GRP-2026-' || lpad(v_grp::TEXT, 4, '0')
        WHERE id = v_p.id;

        INSERT INTO prestamos (codigo_prestamo, estudiante_id, ejemplar_id,
                               bibliotecario_id, fecha_prestamo, fecha_limite,
                               estado, renovaciones, grupo_prestamo)
        VALUES ('P-2026-' || lpad(v_num::TEXT, 4, '0'), v_p.estudiante_id, v_ejem_id,
                v_p.bibliotecario_id, v_p.fecha_prestamo, v_p.fecha_limite,
                'activo', 0, 'GRP-2026-' || lpad(v_grp::TEXT, 4, '0'));
    END LOOP;
END $$;

-- 3) Verificacion: las 9 operaciones con 2 libros pendientes
SELECT COALESCE(p.grupo_prestamo, p.codigo_prestamo) AS operacion,
       (e.nombres || ' ' || e.apellidos) AS est,
       COUNT(*) AS libros,
       COUNT(*) FILTER (WHERE p.estado IN ('activo','vencido')) AS pendientes
FROM prestamos p JOIN estudiantes e ON e.id = p.estudiante_id
WHERE p.grupo_prestamo IN (
    SELECT grupo_prestamo FROM prestamos
    WHERE codigo_prestamo IN ('P-2026-0052','P-2026-0051','P-2026-0049',
        'P-2026-0047','P-2026-0045','P-2026-0044',
        'P-2026-0040','P-2026-0038','P-2026-0036')
)
GROUP BY 1, 2 ORDER BY 1;
