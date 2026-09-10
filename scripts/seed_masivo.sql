-- Seed masivo con bucles: genera datos suficientes para graficos y reportes.
-- Uso: copiar al contenedor y ejecutar con psql -f (ver instrucciones al final).
-- Cantidades aproximadas: 60 libros + 120 ejemplares + 300 prestamos + ~150 devoluciones.
-- Todo usa NOT EXISTS para poder re-ejecutarse sin duplicar.
-- Los triggers de negocio (bloqueo por stock, descuento de stock) se desactivan
-- durante la carga y se reactivan al final: son datos historicos de prueba.

ALTER TABLE prestamos DISABLE TRIGGER ALL;
ALTER TABLE devoluciones DISABLE TRIGGER ALL;

DO $$
DECLARE
    NUM_LIBROS    CONSTANT INT := 60;
    NUM_PRESTAMOS CONSTANT INT := 300;
    i INT;
    v_editoriales INT[];
    v_categorias  INT[];
    v_libros      INT[];
    v_estudiantes INT[];
    v_ejemplares  INT[];
    v_usuarios    INT[];
    v_libro_id INT;
    v_isbn TEXT;
    v_titulo TEXT;
    v_est_id INT;
    v_ejem_id INT;
    v_bib_id INT;
    v_fec_prest TIMESTAMP;
    v_fec_lim DATE;
    v_estado TEXT;
    v_r FLOAT;
    v_seq INT;
BEGIN
    SELECT COALESCE(array_agg(id), '{}') INTO v_editoriales FROM editoriales;
    SELECT COALESCE(array_agg(id), '{}') INTO v_categorias FROM categorias_libro;
    SELECT COALESCE(array_agg(id), '{}') INTO v_estudiantes FROM estudiantes;
    SELECT COALESCE(array_agg(id), '{}') INTO v_usuarios FROM usuarios;

    IF array_length(v_editoriales, 1) IS NULL THEN
        RAISE EXCEPTION 'No hay editoriales: puebla editoriales primero';
    END IF;
    IF array_length(v_categorias, 1) IS NULL THEN
        RAISE EXCEPTION 'No hay categorias_libro: pueblalas primero';
    END IF;
    IF array_length(v_estudiantes, 1) IS NULL THEN
        RAISE EXCEPTION 'No hay estudiantes: pueblalos primero';
    END IF;
    IF array_length(v_usuarios, 1) IS NULL THEN
        RAISE EXCEPTION 'No hay usuarios (bibliotecario): pueblalos primero';
    END IF;

    -- 1) LIBROS: ISBN 978 + 10 digitos (13 chars), titulo unico con secuencia
    SELECT COALESCE(MAX(id), 0) INTO v_seq FROM libros;
    FOR i IN 1..NUM_LIBROS LOOP
        v_isbn := '978' || lpad((1000000000 + v_seq + i)::TEXT, 10, '0');
        v_titulo := 'Libro demo ' || (v_seq + i)::TEXT;
        IF NOT EXISTS (SELECT 1 FROM libros WHERE isbn = v_isbn OR titulo = v_titulo) THEN
            INSERT INTO libros (isbn, titulo, editorial_id, categoria_id, anio_publicacion,
                                num_paginas, idioma, stock_total, stock_disponible, activo, resumen)
            VALUES (v_isbn, v_titulo,
                    v_editoriales[1 + floor(random() * array_length(v_editoriales, 1))::INT],
                    v_categorias[1 + floor(random() * array_length(v_categorias, 1))::INT],
                    1950 + floor(random() * 75)::INT,
                    100 + floor(random() * 500)::INT,
                    (ARRAY['Español','Inglés'])[1 + floor(random() * 2)::INT],
                    2, 2, TRUE,
                    'Libro generado automaticamente para graficos y reportes.');
        END IF;
    END LOOP;

    SELECT array_agg(id) INTO v_libros FROM libros;
    RAISE NOTICE 'libros: %', array_length(v_libros, 1);

    -- 2) EJEMPLARES: 2 por cada libro que tenga menos de 2 (hasta ~120 nuevos)
    FOR v_libro_id IN SELECT id FROM libros ORDER BY id LOOP
        IF (SELECT COUNT(*) FROM ejemplares WHERE libro_id = v_libro_id) < 2 THEN
            FOR i IN 1..2 LOOP
                v_isbn := 'EJ-M' || lpad(v_libro_id::TEXT, 4, '0') || '-' || i::TEXT;
                IF NOT EXISTS (SELECT 1 FROM ejemplares WHERE codigo_ejemplar = v_isbn) THEN
                    INSERT INTO ejemplares (libro_id, codigo_ejemplar, estado, fecha_adquisicion)
                    VALUES (v_libro_id, v_isbn, 'disponible', CURRENT_DATE - (floor(random() * 365)::INT));
                END IF;
            END LOOP;
        END IF;
    END LOOP;

    SELECT array_agg(id) INTO v_ejemplares FROM ejemplares;
    RAISE NOTICE 'ejemplares: %', array_length(v_ejemplares, 1);

    -- Actualiza stock segun ejemplares reales (amplio para que los
    -- prestamos historicos no choquen con el trigger de stock)
    UPDATE libros l SET stock_total = s.cnt + 100, stock_disponible = s.cnt + 100
    FROM (SELECT libro_id, COUNT(*) AS cnt FROM ejemplares GROUP BY libro_id) s
    WHERE s.libro_id = l.id;

    -- 3) PRESTAMOS: ~300 repartidos en los ultimos 12 meses
    FOR i IN 1..NUM_PRESTAMOS LOOP
        v_est_id := v_estudiantes[1 + floor(random() * array_length(v_estudiantes, 1))::INT];
        v_ejem_id := v_ejemplares[1 + floor(random() * array_length(v_ejemplares, 1))::INT];
        v_bib_id := v_usuarios[1 + floor(random() * array_length(v_usuarios, 1))::INT];
        v_fec_prest := NOW() - (floor(random() * 365)::INT || ' days')::INTERVAL
                               - (floor(random() * 86400)::INT || ' seconds')::INTERVAL;
        v_fec_lim := (v_fec_prest + (7 + floor(random() * 9)::INT || ' days')::INTERVAL)::DATE;
        v_r := random();
        v_estado := CASE WHEN v_r < 0.55 THEN 'activo'
                         WHEN v_r < 0.85 THEN 'devuelto'
                         ELSE 'vencido' END;
        v_isbn := 'PR-M' || TO_CHAR(NOW(), 'YYMMDD') || '-' || lpad(i::TEXT, 4, '0')
                  || '-' || lpad(floor(random() * 999)::INT::TEXT, 3, '0');
        IF NOT EXISTS (SELECT 1 FROM prestamos WHERE codigo_prestamo = v_isbn) THEN
            INSERT INTO prestamos (codigo_prestamo, estudiante_id, ejemplar_id, bibliotecario_id,
                                   fecha_prestamo, fecha_limite, estado, renovaciones, observaciones)
            VALUES (v_isbn, v_est_id, v_ejem_id, v_bib_id,
                    v_fec_prest, v_fec_lim, v_estado, floor(random() * 3)::INT,
                    CASE WHEN random() < 0.3 THEN 'Prestamo historico de prueba' ELSE NULL END);
        END IF;
    END LOOP;

    -- 4) DEVOLUCIONES: una por cada prestamo devuelto/vencido sin devolucion
    INSERT INTO devoluciones (prestamo_id, bibliotecario_id, fecha_devolucion,
                              estado_ejemplar, dias_retraso, multa_generada, multa_pagada, observaciones)
    SELECT p.id,
           p.bibliotecario_id,
           CASE WHEN random() < 0.6 THEN (p.fecha_limite + (1 + floor(random() * 15)::INT || ' days')::INTERVAL)::TIMESTAMP
                ELSE (p.fecha_limite - (floor(random() * 3)::INT || ' days')::INTERVAL)::TIMESTAMP END,
           (ARRAY['bueno','bueno','bueno','dañado'])[1 + floor(random() * 4)::INT],
           CASE WHEN random() < 0.6 THEN 1 + floor(random() * 15)::INT ELSE 0 END,
           CASE WHEN random() < 0.6 THEN ROUND((random() * 15)::NUMERIC, 2) ELSE 0 END,
           random() < 0.6,
           'Devolucion generada automaticamente'
    FROM prestamos p
    WHERE p.estado IN ('devuelto', 'vencido')
      AND NOT EXISTS (SELECT 1 FROM devoluciones d WHERE d.prestamo_id = p.id)
    LIMIT 200;

    RAISE NOTICE 'prestamos: %, devoluciones: %',
        (SELECT COUNT(*) FROM prestamos), (SELECT COUNT(*) FROM devoluciones);
END $$;

ALTER TABLE prestamos ENABLE TRIGGER ALL;
ALTER TABLE devoluciones ENABLE TRIGGER ALL;

-- Resumen final
SELECT 'libros' AS tabla, COUNT(*) FROM libros
UNION ALL SELECT 'ejemplares', COUNT(*) FROM ejemplares
UNION ALL SELECT 'prestamos', COUNT(*) FROM prestamos
UNION ALL SELECT 'devoluciones', COUNT(*) FROM devoluciones;

-- Instrucciones:
-- docker cp scripts/seed_masivo.sql biblio-postgres:/tmp/seed_masivo.sql
-- docker exec biblio-postgres psql -U biblio -d biblioteca_vv -f /tmp/seed_masivo.sql
