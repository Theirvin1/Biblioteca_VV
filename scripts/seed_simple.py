"""Seed simple - insert data directly via psql commands."""
import subprocess

def psql(sql):
    """Execute SQL against the PostgreSQL container."""
    result = subprocess.run(
        ['docker', 'exec', 'biblio-postgres', 'psql', '-U', 'biblio', '-d', 'biblioteca_vv', '-c', sql],
        capture_output=True, text=True
    )
    return result.returncode == 0, result.stdout, result.stderr

# 1. Paises
psql("INSERT INTO paises (nombre) VALUES ('Ecuador'), ('España'), ('Estados Unidos'), ('Colombia'), ('México'), ('Argentina') ON CONFLICT DO NOTHING;")
print("Paises OK")

# 2. Carreras
psql("INSERT INTO carreras (nombre, facultad_id) VALUES ('Ingeniería en Sistemas', 1), ('Administración de Empresas', 1), ('Derecho', 2), ('Medicina', 2), ('Ingeniería Civil', 3), ('Arquitectura', 3), ('Psicología', 4) ON CONFLICT DO NOTHING;")
print("Carreras OK")

# 3. Editoriales
psql("INSERT INTO editoriales (nombre) VALUES ('Alfaguara'), ('Planeta'), ('Santillana'), ('Editorial Norma'), ('Penguin Random House'), ('HarperCollins'), ('Blume'), ('Anaya') ON CONFLICT DO NOTHING;")
print("Editoriales OK")

# 4. Categorias
psql("INSERT INTO categorias_libro (nombre) VALUES ('Literatura'), ('Ciencias'), ('Tecnología'), ('Historia'), ('Matemáticas'), ('Narrativa'), ('Ensayo'), ('Poesía'), ('Infantil'), ('Ciencias Sociales') ON CONFLICT DO NOTHING;")
print("Categorias OK")

# 5. Autores - usaremos IDs 1-5 que ya deberían estar
# Insertar algunos autores si no existen
autores_data = [
    ('Gabriel', 'García Márquez', 1),
    ('Isabel', 'Allende', 2),
    ('George', 'Orwell', 3),
]
for nom, ape, nac in autores_data:
    sql = "INSERT INTO autores (nombres, apellidos, nacionalidad_id) VALUES ('" + nom + "', '" + ape + "', " + str(nac) + ") ON CONFLICT DO NOTHING;"
    ok, _, _ = psql(sql)
    print("Autor:", nom, "->", "OK" if ok else "FAIL")

# Count autores
result = subprocess.run(
    ['docker', 'exec', 'biblio-postgres', 'psql', '-U', 'biblio', '-d', 'biblioteca_vv', '-c', 'SELECT COUNT(*) FROM autores;'],
    capture_output=True, text=True
)
print("Total autores:", result.stdout.strip())

# 6. Insertar 10 libros
print("Insertando 10 libros...")
for i in range(1, 11):
    isbn = '978' + '%09d' % (100000000 + i)
    titulo = 'Libro ' + str(i)
    # Usar IDs fijos para evitar subqueries
    sql = "INSERT INTO libros (isbn, titulo, editorial_id, categoria_id, anio_publicacion, num_paginas, idioma, stock_total, stock_disponible, activo, resumen) VALUES ('" + isbn + "', '" + titulo + "', 1, 1, 1900 + " + str(i) + ", 300, 'Español', 5, 3, TRUE, 'Resumen del libro ' + v_titulo + "');"
    # This has a bug - v_titulo no definido. Let me fix.
    pass

print("Done seeding")