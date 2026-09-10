"""Seed masivo robusto para la base de datos.

Inserta datos en el orden correcto para respetar FK y constraints.
Ejecutar: python scripts/seed_masivo.py
"""
import random
import string
from datetime import date, timedelta

from app import create_app
from app.extensions import db
from app.models import (
    Libro, Estudiante, Prestamo, Devolucion, Autor, CategoriaLibro,
    Editorial, Pais, Facultad, Carrera
)

app = create_app()
app.config['WTF_CSRF_ENABLED'] = False
app.app_context().push()


def generar_isbn13():
    """Genera un ISBN-13 válido con dígito de control."""
    # Base: 978 + 9 dígitos aleatorios
    base = "978" + "".join(random.choices(string.digits, k=9))
    # Calcular dígito de control
    suma = sum(int(base[i]) * (1 if i % 2 == 0 else 3) for i in range(12))
    resto = suma % 10
    control = 10 - resto if resto != 0 else 0
    return base + str(control)


def random_date_in_range(start_date, end_date):
    """Fecha aleatoria entre dos fechas."""
    delta = end_date - start_date
    int_delta = (delta.days * 24 * 60 * 60)
    random_seconds = random.randint(0, int_delta)
    return start_date + timedelta(seconds=random_seconds)


def seed_paises_y_carreras():
    """Asegura que paises, facultades y carreras existan."""
    print("Insertando paises, facultades y carreras...")
    
    # Paises
    paises_nom = ['Ecuador', 'España', 'Estados Unidos', 'Colombia', 'México', 'Argentina']
    for p in paises_nom:
        if not Pais.query.filter_by(nombre=p).first():
            db.session.add(Pais(nombre=p))
    
    # Carreras (una por cada país aproximadamente)
    carreras_nom = [
        'Ingeniería en Sistemas', 'Administración de Empresas', 'Derecho',
        'Medicina', 'Ingeniería Civil', 'Arquitectura', 'Psicología'
    ]
    for c in carreras_nom:
        if not Carrera.query.filter_by(nombre=c).first():
            db.session.add(Carrera(nombre=c))
    
    db.session.commit()
    print("Paises y carreras listos.")


def seed_editoriales_y_categorias():
    """Inserta editoriales y categorías."""
    print("Insertando editoriales y categorías...")
    
    editoriales_nom = [
        'Alfaguara', 'Planeta', 'Santillana', 'Editorial Norma',
        'Penguin Random House', 'HarperCollins', 'Blume', 'Anaya'
    ]
    for e in editoriales_nom:
        if not Editorial.query.filter_by(nombre=e).first():
            db.session.add(Editorial(nombre=e))
    
    categorias_nom = [
        'Literatura', 'Ciencias', 'Tecnología', 'Historia', 'Matemáticas',
        'Narrativa', 'Ensayo', 'Poesía', 'Infantil', 'Ciencias Sociales'
    ]
    for c in categorias_nom:
        if not CategoriaLibro.query.filter_by(nombre=c).first():
            db.session.add(CategoriaLibro(nombre=c))
    
    db.session.commit()
    print("Editoriales y categorías listos.")


def seed_autores():
    """Inserta 25 autores aleatorios."""
    print("Insertando autores...")
    apellidos = [
        'García Márquez', 'Cervantes', 'Hemingway', 'Orwell', 'Camus',
        'Fernando', 'Rivera', 'López', 'Pérez', 'Gómez',
        'Martínez', 'Sánchez', 'Rodríguez', 'González', 'Díaz',
        'Torres', 'Jiménez', 'Ruiz', 'Alvarez', 'Vargas'
    ]
    nombres = [
        'Gabriel', 'Jorge', 'Mario', 'Luis', 'Carlos',
        'Fernando', 'Roberto', 'Miguel', 'Daniel', 'Arturo',
        'Sonia', 'Patricia', 'Martín', 'Daniela', 'Andrés',
        'Beatriz', 'Rafael', 'Francisco', 'Alejandro'
    ]
    
    for _ in range(25):
        nm = random.choice(nombres)
        ap = random.choice(apellidos)
        # Verificar si existe
        exist = Autor.query.filter_by(nombres=nm, apellidos=ap).first()
        if not exist:
            # Asignar país aleatorio
            pais_id = random.randint(1, 6)
            autor = Autor(nombres=nm, apellidos=ap, nacionalidad_id=pais_id)
            db.session.add(autor)
    
    db.session.commit()
    print(f"Autores insertados: {Autor.query.count()}")


def seed_estudiantes():
    """Inserta 30 estudiantes con emails únicos."""
    print("Insertando 30 estudiantes...")
    hoy = date.today()
    fecha_min = date(1995, 1, 1)
    fecha_max = date(2005, 12, 31)
    
    carreras_ids = [1, 2, 3, 4, 5, 6, 7]
    usados = set()
    
    for i in range(30):
        # Email único
        while True:
            carrera_id = random.choice(carreras_ids)
            email = f"est{i % 10}@uteq.edu.ec"  # Patrones únicos
            if email not in usados:
                usados.add(email)
                break
        
        nombre = random.choice(['Juan', 'María', 'Carlos', 'Laura', 'Pedro', 'Ana', 'José', 'Isabel'])
        apellido = random.choice(['García', 'López', 'Martínez', 'Rodríguez', 'Sánchez'])
        telefono = f"09{random.randint(1000000, 9999999)}"
        fn = random_date_in_range(fecha_min, fecha_max)
        genero = random.choice(['M', 'F', 'O'])
        
        estudiante = Estudiante(
            cedula=str(random.randint(1000000000, 9999999999)),
            nombres=nombre,
            apellidos=apellido,
            correo=email,
            telefono=telefono,
            carrera_id=carrera_id,
            fecha_nacimiento=fn,
            genero=genero,
            estado='activo'
        )
        db.session.add(estudiante)
    
    db.session.commit()
    print(f"Estudiantes insertados: {Estudiante.query.count()}")


def seed_libros():
    """Inserta 50 libros con datos consistentes."""
    print("Insertando 50 libros...")
    titulos = [
        'Cien años de soledad', 'Don Quijote de la Mancha', 'Fahrenheit 451',
        '1984', 'Matar un ruiseñor', 'El principito', 'El alquimista',
        'Rayuela', 'Crónica de una muerte anunciada', 'Harry Potter y la piedra filosofal',
        'El señor de los anillos', 'Harry Potter y la cámara secreta',
        'La sombra del viento', 'Crónicas marcianas', 'Orgullo y prejuicio',
        'Moby Dick', 'El extranjero', 'El name of the wind', 'Cien sombras',
    ]
    autores_data = [
        ('Gabriel García Márquez', 'Colombia'),
        ('Isabel Allende', 'Chile'),
        ('George Orwell', 'Reino Unido'),
        ('Aldous Huxley', 'Reino Unido'),
        ('John Steinbeck', 'Estados Unidos'),
        ('Harper Lee', 'Estados Unidos'),
        ('Ernest Hemingway', 'Estados Unidos'),
        ('Mario Vargas Llosa', 'Perú'),
        ('Julio Cortázar', 'Argentina'),
        ('Pablo Neruda', 'Chile'),
    ]
    categorias = ['Literatura', 'Ciencias', 'Tecnología', 'Historia', 'Matemáticas']
    
    inserted = 0
    for i in range(50):
        titulo = titulos[i % len(titulos)]
        # Evitar duplicados exactos
        if Libro.query.filter_by(titulo=titulo).first():
            continue
        
        autor_nom, autor_pais = autores_data[i % len(autores_data)]
        # Buscar autor
        autor = Autor.query.filter(nombres=autor_nom.split()[0]).first()
        if not autor:
            autor = Autor(nombres=autor_nom.split()[0], apellidos=autor_nom,
                         nacionalidad_id=random.randint(1, 6))
            db.session.add(autor)
            db.session.flush()
        
        # ISBN-13 válido
        isbn = generar_isbn13()
        
        # Año 1800-2024
        anio = random.randint(1800, 2024)
        
        # Categoría
        cat_nom = categorias[i % len(categorias)]
        cat = CategoriaLibro.query.filter_by(nombre=cat_nom).first()
        if not cat:
            cat = CategoriaLibro(nombre=cat_nom)
            db.session.add(cat)
        
        # Editorial
        edit_nom = ['Alfaguara', 'Planeta', 'Santillana', 'Editorial Norma'][i % 4]
        edit = Editorial.query.filter_by(nombre=edit_nom).first()
        if not edit:
            edit = Editorial(nombre=edit_nom, pais_id=random.randint(1, 6))
            db.session.add(edit)
            db.session.flush()
        
        stock_total = random.randint(1, 25)
        stock_disp = random.randint(0, stock_total)
        num_paginas = random.randint(200, 600)
        
        libro = Libro(
            isbn=isbn,
            titulo=titulo,
            subtitulo=None,
            editorial_id=edit.id,
            categoria_id=cat.id,
            anio_publicacion=anio,
            edicion=None,
            num_paginas=num_paginas,
            idioma=random.choice(['Español', 'Inglés']),
            stock_total=stock_total,
            stock_disponible=stock_disp,
            activo=True,
            resumen=f"Resumen de {titulo}. Obra literaria clásica.",
        )
        db.session.add(libro)
        inserted += 1
    
    db.session.commit()
    print(f"Libros insertados: {inserted}")


def seed_autores_libros():
    """Relaciona libros con autores (muchos a muchos)."""
    print("Relacionando libros con autores...")
    libros = Libro.query.limit(30).all()
    autores = Autor.query.limit(20).all()
    
    for libro in libros:
        # Cada libro tiene 1-2 autores
        num_autores = random.randint(1, 2)
        seleccionados = random.sample(autores, min(num_autores, len(autores)))
        for autor in seleccionados:
            exist = LibroAutor.query.filter_by(libro_id=libro.id, autor_id=autor.id).first()
            if not exist:
                db.session.add(LibroAutor(libro_id=libro.id, autor_id=autor.id))
    
    db.session.commit()
    print("Relaciones libro-autor insertadas.")


def seed_ejemplares():
    """Inserta ejemplares para cada libro."""
    print("Insertando ejemplares...")
    libros = Libro.query.limit(30).all()
    
    for libro in libros:
        # 2-4 ejemplares por libro
        num_ej = random.randint(2, 4)
        for i in range(num_ej):
            codigo = f"EJ-{random.randint(1000, 9999):04d}"
            if not Ejemplar.query.filter_by(codigo_ejemplar=codigo).first():
                db.session.add(Ejemplar(
                    libro_id=libro.id,
                    codigo_ejemplar=codigo,
                    estado=random.choice(['disponible', 'prestado', 'dañado']),
                    fecha_adquisicion=date.today() - timedelta(days=random.randint(0, 365)),
                ))
    
    db.session.commit()
    print(f"Ejemplares insertados: {Ejemplar.query.count()}")


def seed_prestamos():
    """Inserta 200 préstamos históricos (últimos 6 meses)."""
    print("Insertando 200 préstamos históricos...")
    hoy = date.today()
    fecha_inicio = hoy - timedelta(days=180)
    
    estudiantes = Estudiante.query.limit(15).all()
    libros = Libro.query.limit(30).all()
    ejemplares = Ejemplar.query.limit(50).all()
    
    if not estudiantes or not libros or not ejemplares:
        print("Datos insuficientes para préstamos")
        return
    
    # Para asegurar buena distribución en gráficas:
    # - ~60% activos
    # - ~25% devueltos a tiempo  
    # - ~15% vencidos
    # - ~10% con multa por retraso
    
    estados_pesos = [0.6, 0.25, 0.15]
    estados = ['activo', 'devuelto', 'vencido']
    
    inserted = 0
    for _ in range(200):
        estudiante = random.choice(estudiantes)
        libro = random.choice(libros)
        ejemplar = random.choice(ejemplares)
        
        # Fecha de préstamo aleatoria en los últimos 6 meses
        dias_atras = random.randint(0, (hoy - fecha_inicio).days)
        fecha_prestamo = hoy - timedelta(days=dias_atras)
        
        # Fecha límite = 30 días después de préstamo
        fecha_limite = fecha_prestamo + timedelta(days=30)
        
        # Determinar estado con distribución ponderada
        estado = random.choices(estados, weights=estados_pesos)[0]
        
        codigo = f"PREST-{random.randint(1000, 9999)}"
        
        # Lógica de devolución
        tiene_devolucion = estado in ['devuelto', 'vencido']
        fecha_devolucion = None
        dias_retraso = 0
        monto_multa = 0
        
        if tiene_devolucion:
            # Fecha de devolución: a veces después del límite
            if random.random() > 0.6:
                # Devuelto después del límite
                dias_despues = random.randint(1, 20)
                fecha_devolucion = fecha_limite + timedelta(days=dias_despues)
                dias_retraso = random.randint(1, 15)
                monto_multa = round(dias_retraso * 0.50, 2)
            else:
                # Devuelto a tiempo
                fecha_devolucion = fecha_limite + timedelta(days=random.randint(0, 5))
                dias_retraso = 0
                monto_multa = 0
        
        prestamo = Prestamo(
            codigo_prestamo=f"PREST-{random.randint(1000, 9999)}",
            estudiante_id=estudiante.id,
            ejemplar_id=random.choice(ejemplares).id,
            bibliotecario_id=random.randint(1, 3),
            fecha_prestamo=fecha_prestamo,
            fecha_limite=fecha_limite,
            estado=estado,
            observaciones=f"Prestamo histórico N°{_}" if random.random() > 0.7 else None,
        )
        db.session.add(prestamo)
        inserted += 1
        
        # Si tiene devolución, crear registro
        if tiene_devolucion:
            multa = Devolucion(
                prestamo_id=prestamo.id,
                fecha_devolucion=fecha_devolucion if fecha_devolucion else date.today(),
                dias_retraso=dias_retraso,
                multa_generada=monto_multa,
                estado='pagada' if random.random() > 0.4 else 'pendiente',
            )
            db.session.add(multa)
    
    db.session.commit()
    print(f"Préstamos insertados: {inserted}")


def main():
    print("=== Iniciando seed masivo ===")
    
    seed_paises_y_carreras()
    seed_editoriales_y_categorias()
    seed_autores()
    seed_estudiantes()
    seed_libros()
    seed_ejemplares()
    seed_prestamos()
    
    db.session.commit()
    
    print(f"\n=== RESUMEN FINAL ===")
    print(f"Paises: {Pais.query.count()}")
    print(f"Carreras: {Carrera.query.count()}")
    print(f"Editoriales: {Editorial.query.count()}")
    print(f"Categorías: {CategoriaLibro.query.count()}")
    print(f"Autores: {Autor.query.count()}")
    print(f"Estudiantes: {Estudiante.query.count()}")
    print(f"Libros: {Libro.query.count()}")
    print(f"Ejemplares: {Ejemplar.query.count()}")
    print(f"Préstamos: {Prestamo.query.count()}")
    print(f"Devoluciones: {Devolucion.query.count()}")


if __name__ == '__main__':
    main()