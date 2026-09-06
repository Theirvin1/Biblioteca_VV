-- ============================================
-- ÍNDICES
-- ============================================

-- Búsquedas frecuentes
CREATE INDEX idx_estudiantes_cedula         ON estudiantes(cedula);
CREATE INDEX idx_estudiantes_apellidos      ON estudiantes(apellidos);
CREATE INDEX idx_libros_isbn                ON libros(isbn);
CREATE INDEX idx_libros_titulo               ON libros(titulo);
CREATE INDEX idx_libros_categoria_id        ON libros(categoria_id);
CREATE INDEX idx_ejemplares_libro_id        ON ejemplares(libro_id);
CREATE INDEX idx_ejemplares_estado          ON ejemplares(estado);

-- Filtros en préstamos y devoluciones
CREATE INDEX idx_prestamos_estudiante_id    ON prestamos(estudiante_id);
CREATE INDEX idx_prestamos_estado           ON prestamos(estado);
CREATE INDEX idx_prestamos_fecha_limite     ON prestamos(fecha_limite);
CREATE INDEX idx_prestamos_bibliotecario    ON prestamos(bibliotecario_id);
CREATE INDEX idx_devoluciones_prestamo_id   ON devoluciones(prestamo_id);
CREATE INDEX idx_devoluciones_multa_pagada  ON devoluciones(multa_pagada);

-- Auditoría
CREATE INDEX idx_auditoria_fecha_hora       ON auditoria(fecha_hora);
CREATE INDEX idx_auditoria_tabla            ON auditoria(tabla_afectada);
CREATE INDEX idx_sesiones_usuario_id        ON sesiones(usuario_id);



-- ============================================
-- FUNCIONES ALMACENADAS
-- ============================================

CREATE OR REPLACE FUNCTION calcular_multa(p_prestamo_id INTEGER)
RETURNS NUMERIC(8,2) AS $$
DECLARE
v_fecha_limite DATE;
    v_dias_retraso INTEGER;
    v_multa_diaria NUMERIC(8,2);
    v_multa NUMERIC(8,2);
BEGIN
SELECT fecha_limite INTO v_fecha_limite
FROM prestamos
WHERE id = p_prestamo_id;

v_dias_retraso := CURRENT_DATE - v_fecha_limite;

    IF v_dias_retraso <= 0 THEN
        RETURN 0;
END IF;

SELECT valor::NUMERIC INTO v_multa_diaria
FROM configuracion_sistema
WHERE clave = 'multa_diaria';

v_multa := v_dias_retraso * v_multa_diaria;

RETURN v_multa;
END;
$$ LANGUAGE plpgsql;


   --VALIDAR_PRESTAMOS(CEDULA,ISBN)

   CREATE OR REPLACE FUNCTION validar_prestamo(p_cedula VARCHAR, p_isbn VARCHAR)
RETURNS TABLE(codigo_resultado INTEGER, mensaje TEXT) AS $$
DECLARE
v_estudiante_id INTEGER;
    v_estado_estudiante VARCHAR(15);
    v_prestamos_vencidos INTEGER;
    v_libro_id INTEGER;
    v_libro_activo BOOLEAN;
    v_stock_disponible INTEGER;
BEGIN
    -- Verifica que el estudiante exista
SELECT id, estado INTO v_estudiante_id, v_estado_estudiante
FROM estudiantes
WHERE cedula = p_cedula;

IF v_estudiante_id IS NULL THEN
        RETURN QUERY SELECT 1, 'Estudiante no registrado'::TEXT;
RETURN;
END IF;

    IF v_estado_estudiante != 'activo' THEN
        RETURN QUERY SELECT 2, 'El estudiante no está activo'::TEXT;
RETURN;
END IF;

    -- Verifica préstamos vencidos
SELECT COUNT(*) INTO v_prestamos_vencidos
FROM prestamos
WHERE estudiante_id = v_estudiante_id AND estado = 'vencido';

IF v_prestamos_vencidos > 0 THEN
        RETURN QUERY SELECT 3, 'El estudiante tiene préstamos pendientes'::TEXT;
RETURN;
END IF;

    -- Verifica que el libro exista y esté activo
SELECT id, activo, stock_disponible INTO v_libro_id, v_libro_activo, v_stock_disponible
FROM libros
WHERE isbn = p_isbn;

IF v_libro_id IS NULL OR v_libro_activo = FALSE THEN
        RETURN QUERY SELECT 4, 'Libro no registrado'::TEXT;
RETURN;
END IF;

    IF v_stock_disponible <= 0 THEN
        RETURN QUERY SELECT 5, 'Libro no disponible'::TEXT;
RETURN;
END IF;

RETURN QUERY SELECT 0, 'OK'::TEXT;
END;
$$ LANGUAGE plpgsql;



   --RESUMEN_ESTUDIANTE(CEDULA)

   CREATE OR REPLACE FUNCTION resumen_estudiante(p_cedula VARCHAR)
RETURNS TABLE(
    prestamos_activos INTEGER,
    total_historial INTEGER,
    multas_pendientes NUMERIC,
    estado_cuenta VARCHAR
) AS $$
DECLARE
v_estudiante_id INTEGER;
BEGIN
SELECT id INTO v_estudiante_id FROM estudiantes WHERE cedula = p_cedula;

RETURN QUERY
SELECT
    (SELECT COUNT(*)::INTEGER FROM prestamos WHERE estudiante_id = v_estudiante_id AND estado = 'activo'),
    (SELECT COUNT(*)::INTEGER FROM prestamos WHERE estudiante_id = v_estudiante_id),
    (SELECT COALESCE(SUM(d.multa_generada), 0) FROM devoluciones d
                                                        JOIN prestamos p ON p.id = d.prestamo_id
     WHERE p.estudiante_id = v_estudiante_id AND d.multa_pagada = FALSE),
    (SELECT estado FROM estudiantes WHERE id = v_estudiante_id);
END;
$$ LANGUAGE plpgsql;


   --OBTENER_INDICADORES_DASHBOARD()

   CREATE OR REPLACE FUNCTION obtener_indicadores_dashboard()
RETURNS TABLE(
    total_libros INTEGER,
    prestamos_activos INTEGER,
    devoluciones_con_multa INTEGER,
    estudiantes_con_vencidos INTEGER
) AS $$
BEGIN
RETURN QUERY
SELECT
    (SELECT COUNT(*)::INTEGER FROM libros WHERE activo = TRUE),
    (SELECT COUNT(*)::INTEGER FROM prestamos WHERE estado = 'activo'),
    (SELECT COUNT(*)::INTEGER FROM devoluciones WHERE multa_generada > 0),
    (SELECT COUNT(DISTINCT estudiante_id)::INTEGER FROM prestamos WHERE estado = 'vencido');
END;
$$ LANGUAGE plpgsql;


   --GENERAR_CODIGO_PRESTAMO()

   CREATE OR REPLACE FUNCTION generar_codigo_prestamo()
RETURNS VARCHAR AS $$
DECLARE
v_anio VARCHAR(4);
    v_siguiente INTEGER;
    v_codigo VARCHAR(20);
BEGIN
    v_anio := EXTRACT(YEAR FROM CURRENT_DATE)::VARCHAR;

-- Serializa la generacion del codigo: sin esto dos transacciones simultaneas
-- podrian leer el mismo MAX y proponer el mismo codigo (violacion de la
-- restriccion unica). Es un lock TRANSACCIONAL: se libera solo al COMMIT o
-- ROLLBACK, sin necesidad de liberarlo a mano. La clave no es un numero
-- arbitrario: se deriva del nombre de la funcion (hashtext) y del anio, que
-- es justamente el ambito de la numeracion.
    PERFORM pg_advisory_xact_lock(hashtext('generar_codigo_prestamo'), v_anio::INTEGER);

-- La parte numerica arranca justo despues del prefijo 'P-<anio>-' (posicion 8
-- con anios de 4 digitos). Antes se usaba FROM 10, que solo leia los dos
-- ultimos digitos: con 'P-2026-0100' devolvia '00', el MAX se quedaba en 99 y
-- se regeneraba un codigo ya existente (duplicate key). Se calcula el corte
-- desde el largo real del prefijo para no depender de una posicion magica.
-- El filtro por expresion regular evita que un codigo con sufijo no numerico
-- rompa el CAST.
SELECT COALESCE(MAX(CAST(SUBSTRING(codigo_prestamo FROM LENGTH('P-' || v_anio || '-') + 1) AS INTEGER)), 0) + 1
INTO v_siguiente
FROM prestamos
WHERE codigo_prestamo LIKE 'P-' || v_anio || '-%'
  AND codigo_prestamo ~ ('^P-' || v_anio || '-[0-9]+$');

v_codigo := 'P-' || v_anio || '-' || LPAD(v_siguiente::TEXT, 4, '0');

RETURN v_codigo;
END;
$$ LANGUAGE plpgsql;






-- ============================================
-- TRIGGERS
-- ============================================

-- 1. Calcular fecha límite automáticamente antes de insertar un préstamo
CREATE OR REPLACE FUNCTION fn_calcular_fecha_limite()
RETURNS TRIGGER AS $$
DECLARE
v_plazo INTEGER;
BEGIN
SELECT valor::INTEGER INTO v_plazo
FROM configuracion_sistema
WHERE clave = 'plazo_prestamo_dias';

NEW.fecha_limite := (NEW.fecha_prestamo::DATE + v_plazo);
RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_calcular_fecha_limite
    BEFORE INSERT ON prestamos
    FOR EACH ROW
    EXECUTE FUNCTION fn_calcular_fecha_limite();


-- 2. Bloquear préstamo si no hay stock (se ejecuta antes de descontar)
CREATE OR REPLACE FUNCTION fn_bloquear_stock_negativo()
RETURNS TRIGGER AS $$
DECLARE
v_stock INTEGER;
BEGIN
SELECT stock_disponible INTO v_stock
FROM libros l
         JOIN ejemplares e ON e.libro_id = l.id
WHERE e.id = NEW.ejemplar_id;

IF v_stock <= 0 THEN
        RAISE EXCEPTION 'No hay ejemplares disponibles para este libro';
END IF;

RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_bloquear_stock_negativo
    BEFORE INSERT ON prestamos
    FOR EACH ROW
    EXECUTE FUNCTION fn_bloquear_stock_negativo();


-- 3. Actualizar stock y estado del ejemplar tras registrar un préstamo
CREATE OR REPLACE FUNCTION fn_actualizar_stock_prestamo()
RETURNS TRIGGER AS $$
DECLARE
v_libro_id INTEGER;
    v_estado_anterior VARCHAR(15);
BEGIN
SELECT libro_id, estado INTO v_libro_id, v_estado_anterior
FROM ejemplares WHERE id = NEW.ejemplar_id;

UPDATE libros SET stock_disponible = stock_disponible - 1 WHERE id = v_libro_id;
UPDATE ejemplares SET estado = 'prestado' WHERE id = NEW.ejemplar_id;

INSERT INTO historial_inventario (ejemplar_id, tipo_movimiento, estado_anterior, estado_nuevo, usuario_id, prestamo_id)
VALUES (NEW.ejemplar_id, 'prestamo', v_estado_anterior, 'prestado', NEW.bibliotecario_id, NEW.id);

RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_actualizar_stock_prestamo
    AFTER INSERT ON prestamos
    FOR EACH ROW
    EXECUTE FUNCTION fn_actualizar_stock_prestamo();


-- 4. Actualizar stock y estado del ejemplar tras registrar una devolución
CREATE OR REPLACE FUNCTION fn_actualizar_stock_devolucion()
RETURNS TRIGGER AS $$
DECLARE
v_ejemplar_id INTEGER;
    v_libro_id INTEGER;
BEGIN
SELECT e.id, e.libro_id INTO v_ejemplar_id, v_libro_id
FROM prestamos p
         JOIN ejemplares e ON e.id = p.ejemplar_id
WHERE p.id = NEW.prestamo_id;

UPDATE libros SET stock_disponible = stock_disponible + 1 WHERE id = v_libro_id;
UPDATE ejemplares SET estado = 'disponible' WHERE id = v_ejemplar_id;
UPDATE prestamos SET estado = 'devuelto' WHERE id = NEW.prestamo_id;

INSERT INTO historial_inventario (ejemplar_id, tipo_movimiento, estado_anterior, estado_nuevo, usuario_id, prestamo_id)
VALUES (v_ejemplar_id, 'devolucion', 'prestado', 'disponible', NEW.bibliotecario_id, NEW.prestamo_id);

RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_actualizar_stock_devolucion
    AFTER INSERT ON devoluciones
    FOR EACH ROW
    EXECUTE FUNCTION fn_actualizar_stock_devolucion();


-- 5. Auditoría de préstamos
CREATE OR REPLACE FUNCTION fn_auditoria_prestamos()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO auditoria (tabla_afectada, operacion, usuario_id, datos_nuevos, modulo)
        VALUES ('prestamos', 'INSERT', NEW.bibliotecario_id, row_to_json(NEW), 'prestamos');
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO auditoria (tabla_afectada, operacion, usuario_id, datos_anteriores, datos_nuevos, modulo)
        VALUES ('prestamos', 'UPDATE', NEW.bibliotecario_id, row_to_json(OLD), row_to_json(NEW), 'prestamos');
END IF;
RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_auditoria_prestamos
    AFTER INSERT OR UPDATE ON prestamos
                        FOR EACH ROW
                        EXECUTE FUNCTION fn_auditoria_prestamos();


-- 6. Auditoría de devoluciones
CREATE OR REPLACE FUNCTION fn_auditoria_devoluciones()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO auditoria (tabla_afectada, operacion, usuario_id, datos_nuevos, modulo)
        VALUES ('devoluciones', 'INSERT', NEW.bibliotecario_id, row_to_json(NEW), 'devoluciones');
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO auditoria (tabla_afectada, operacion, usuario_id, datos_anteriores, datos_nuevos, modulo)
        VALUES ('devoluciones', 'UPDATE', NEW.bibliotecario_id, row_to_json(OLD), row_to_json(NEW), 'devoluciones');
END IF;
RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_auditoria_devoluciones
    AFTER INSERT OR UPDATE ON devoluciones
                        FOR EACH ROW
                        EXECUTE FUNCTION fn_auditoria_devoluciones();


-- 7. Auditoría de libros (incluye DELETE)
CREATE OR REPLACE FUNCTION fn_auditoria_libros()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO auditoria (tabla_afectada, operacion, datos_nuevos, modulo)
        VALUES ('libros', 'INSERT', row_to_json(NEW), 'libros');
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO auditoria (tabla_afectada, operacion, datos_anteriores, datos_nuevos, modulo)
        VALUES ('libros', 'UPDATE', row_to_json(OLD), row_to_json(NEW), 'libros');
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO auditoria (tabla_afectada, operacion, datos_anteriores, modulo)
        VALUES ('libros', 'DELETE', row_to_json(OLD), 'libros');
END IF;
RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_auditoria_libros
    AFTER INSERT OR UPDATE OR DELETE ON libros
    FOR EACH ROW
    EXECUTE FUNCTION fn_auditoria_libros();


-- 8. Marcar préstamos vencidos (se ejecuta manualmente o programado, no por evento de fila)
CREATE OR REPLACE FUNCTION fn_actualizar_estado_vencido()
RETURNS VOID AS $$
BEGIN
UPDATE prestamos
SET estado = 'vencido'
WHERE estado = 'activo' AND fecha_limite < CURRENT_DATE;
END;
$$ LANGUAGE plpgsql;



   -- ============================================
-- VISTAS
-- ============================================

-- 1. Préstamos activos
CREATE OR REPLACE VIEW vista_prestamos_activos AS
SELECT
    p.id,
    p.codigo_prestamo,
    (e.nombres || ' ' || e.apellidos) AS nombre_estudiante,
    l.titulo AS titulo_libro,
    ej.codigo_ejemplar,
    p.fecha_prestamo,
    p.fecha_limite
FROM prestamos p
         JOIN estudiantes e ON e.id = p.estudiante_id
         JOIN ejemplares ej ON ej.id = p.ejemplar_id
         JOIN libros l ON l.id = ej.libro_id
WHERE p.estado = 'activo';


-- 2. Préstamos vencidos
CREATE OR REPLACE VIEW vista_prestamos_vencidos AS
SELECT
    p.id,
    p.codigo_prestamo,
    (e.nombres || ' ' || e.apellidos) AS nombre_estudiante,
    l.titulo AS titulo_libro,
    p.fecha_limite,
    (CURRENT_DATE - p.fecha_limite) AS dias_retraso
FROM prestamos p
         JOIN estudiantes e ON e.id = p.estudiante_id
         JOIN ejemplares ej ON ej.id = p.ejemplar_id
         JOIN libros l ON l.id = ej.libro_id
WHERE p.estado = 'activo' AND p.fecha_limite < CURRENT_DATE;


-- 3. Inventario actual
CREATE OR REPLACE VIEW vista_inventario_actual AS
SELECT
    l.id,
    l.titulo,
    l.stock_total,
    l.stock_disponible,
    COUNT(ej.id) FILTER (WHERE ej.estado = 'disponible') AS ejemplares_disponibles,
    COUNT(ej.id) FILTER (WHERE ej.estado = 'prestado') AS ejemplares_prestados,
    COUNT(ej.id) FILTER (WHERE ej.estado = 'dañado') AS ejemplares_danados,
    COUNT(ej.id) FILTER (WHERE ej.estado = 'baja') AS ejemplares_baja
FROM libros l
         LEFT JOIN ejemplares ej ON ej.libro_id = l.id
GROUP BY l.id, l.titulo, l.stock_total, l.stock_disponible;


-- 4. Multas pendientes
CREATE OR REPLACE VIEW vista_multas_pendientes AS
SELECT
    e.id AS estudiante_id,
    (e.nombres || ' ' || e.apellidos) AS nombre_estudiante,
    SUM(d.multa_generada) AS monto_total
FROM devoluciones d
         JOIN prestamos p ON p.id = d.prestamo_id
         JOIN estudiantes e ON e.id = p.estudiante_id
WHERE d.multa_generada > 0 AND d.multa_pagada = FALSE
GROUP BY e.id, e.nombres, e.apellidos;


-- 5. Historial de movimientos (préstamos + devoluciones)
CREATE OR REPLACE VIEW vista_historial_movimientos AS
SELECT
    'prestamo' AS tipo_movimiento,
    (e.nombres || ' ' || e.apellidos) AS nombre_estudiante,
    l.titulo AS titulo_libro,
    p.fecha_prestamo AS fecha,
    p.estado AS resultado
FROM prestamos p
         JOIN estudiantes e ON e.id = p.estudiante_id
         JOIN ejemplares ej ON ej.id = p.ejemplar_id
         JOIN libros l ON l.id = ej.libro_id

UNION ALL

SELECT
    'devolucion' AS tipo_movimiento,
    (e.nombres || ' ' || e.apellidos) AS nombre_estudiante,
    l.titulo AS titulo_libro,
    d.fecha_devolucion AS fecha,
    d.estado_ejemplar AS resultado
FROM devoluciones d
         JOIN prestamos p ON p.id = d.prestamo_id
         JOIN estudiantes e ON e.id = p.estudiante_id
         JOIN ejemplares ej ON ej.id = p.ejemplar_id
         JOIN libros l ON l.id = ej.libro_id;


-- 6. Libros más prestados
CREATE OR REPLACE VIEW vista_libros_mas_prestados AS
SELECT
    l.id,
    l.titulo,
    COUNT(p.id) AS total_prestamos
FROM libros l
         JOIN ejemplares ej ON ej.libro_id = l.id
         JOIN prestamos p ON p.ejemplar_id = ej.id
GROUP BY l.id, l.titulo
ORDER BY total_prestamos DESC;


-- 7. Estudiantes con deuda
CREATE OR REPLACE VIEW vista_estudiantes_con_deuda AS
SELECT
    e.id AS estudiante_id,
    (e.nombres || ' ' || e.apellidos) AS nombre_estudiante,
    e.cedula,
    SUM(d.multa_generada) AS monto_adeudado
FROM devoluciones d
         JOIN prestamos p ON p.id = d.prestamo_id
         JOIN estudiantes e ON e.id = p.estudiante_id
WHERE d.multa_pagada = FALSE AND d.multa_generada > 0
GROUP BY e.id, e.nombres, e.apellidos, e.cedula;


-- 8. Dashboard de indicadores
CREATE OR REPLACE VIEW vista_dashboard_indicadores AS
SELECT
    (SELECT COUNT(*) FROM libros WHERE activo = TRUE) AS total_libros,
    (SELECT COUNT(*) FROM prestamos WHERE estado = 'activo') AS prestamos_activos,
    (SELECT COUNT(*) FROM devoluciones WHERE multa_generada > 0) AS devoluciones_con_multa,
    (SELECT COUNT(DISTINCT estudiante_id) FROM prestamos WHERE estado = 'vencido') AS estudiantes_con_vencidos;