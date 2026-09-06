"""
Script de datos semilla (seed) para el sistema de biblioteca.
Ejecutar una sola vez después de correr las migraciones y el setup.sql.

Uso:
    python -m database.seed
"""

from werkzeug.security import generate_password_hash
from app import create_app
from app.extensions import db
from app.models import (
    Pais, Facultad, Carrera, CategoriaLibro,
    Usuario, Estudiante, ConfiguracionSistema
)

app = create_app()


def seed_configuracion():
    valores = [
        ('plazo_prestamo_dias', '7', 'Días de plazo para devolver un préstamo'),
        ('multa_diaria', '0.50', 'Monto de multa por cada día de retraso'),
        ('max_renovaciones', '2', 'Cantidad máxima de renovaciones por préstamo'),
        ('max_prestamos_activos', '3', 'Cantidad máxima de préstamos activos por estudiante'),
        ('intervalo_verificacion_horas', '24', 'Cada cuántas horas se revisan préstamos vencidos'),
    ]
    for clave, valor, descripcion in valores:
        existe = ConfiguracionSistema.query.filter_by(clave=clave).first()
        if not existe:
            db.session.add(ConfiguracionSistema(clave=clave, valor=valor, descripcion=descripcion))
    print("Configuración del sistema cargada.")


def seed_paises():
    nombres = ['Ecuador', 'España', 'Estados Unidos', 'Colombia', 'México', 'Argentina']
    for nombre in nombres:
        if not Pais.query.filter_by(nombre=nombre).first():
            db.session.add(Pais(nombre=nombre))
    print("Países cargados.")


def seed_facultades_y_carreras():
    estructura = {
        'Facultad de Ingeniería': ['Ingeniería en Sistemas', 'Ingeniería Civil', 'Ingeniería Industrial'],
        'Facultad de Ciencias Administrativas': ['Administración de Empresas', 'Contabilidad y Auditoría'],
        'Facultad de Ciencias de la Salud': ['Medicina', 'Enfermería'],
    }
    for nombre_facultad, carreras in estructura.items():
        facultad = Facultad.query.filter_by(nombre=nombre_facultad).first()
        if not facultad:
            facultad = Facultad(nombre=nombre_facultad)
            db.session.add(facultad)
            db.session.flush()  # para obtener el id antes del commit

        for nombre_carrera in carreras:
            if not Carrera.query.filter_by(nombre=nombre_carrera, facultad_id=facultad.id).first():
                db.session.add(Carrera(nombre=nombre_carrera, facultad_id=facultad.id))
    print("Facultades y carreras cargadas.")


def seed_categorias():
    categorias = [
        ('Literatura', 'Novelas, cuentos y poesía'),
        ('Ciencias', 'Física, química, biología y afines'),
        ('Tecnología', 'Programación, redes y sistemas'),
        ('Historia', 'Historia universal y local'),
        ('Matemáticas', 'Álgebra, cálculo y estadística'),
        ('Derecho', 'Leyes y ciencias jurídicas'),
    ]
    for nombre, descripcion in categorias:
        if not CategoriaLibro.query.filter_by(nombre=nombre).first():
            db.session.add(CategoriaLibro(nombre=nombre, descripcion=descripcion))
    print("Categorías de libros cargadas.")


def seed_usuarios():
    usuarios = [
        ('gerente', 'Gerente', 'gerente'),
        ('bibliotecario', 'Biblio', 'bibliotecario'),
    ]
    for username, password, rol in usuarios:
        if not Usuario.query.filter_by(username=username).first():
            db.session.add(Usuario(
                username=username,
                password_hash=generate_password_hash(password),
                rol=rol
            ))

    seed_estudiante_demo()
    print("Usuarios iniciales (gerente, bibliotecario y estudiante) cargados.")


def seed_estudiante_demo():
    """Crea el usuario de demo 'estudiante' y su Estudiante vinculado.

    Si el usuario ya existía de una siembra anterior sin Estudiante
    vinculado (bug ya corregido), este paso lo repara al re-ejecutarse.
    """
    usuario = Usuario.query.filter_by(username='estudiante').first()
    if usuario is None:
        usuario = Usuario(
            username='estudiante',
            password_hash=generate_password_hash('Estudiante'),
            rol='estudiante',
        )
        db.session.add(usuario)
        db.session.flush()

    if usuario.estudiante is None:
        carrera = Carrera.query.order_by(Carrera.id).first()
        if carrera is None:
            print("No se pudo vincular el estudiante demo: no hay carreras cargadas todavía.")
            return

        db.session.add(Estudiante(
            cedula='1234567890',
            nombres='Estudiante',
            apellidos='Demo',
            correo='estudiante.demo@uteq.edu.ec',
            carrera_id=carrera.id,
            usuario_id=usuario.id,
        ))
        print("Estudiante demo vinculado al usuario 'estudiante'.")


def run_seed():
    with app.app_context():
        seed_configuracion()
        seed_paises()
        seed_facultades_y_carreras()
        seed_categorias()
        seed_usuarios()
        db.session.commit()
        print("\nSeed completado exitosamente.")


if __name__ == '__main__':
    run_seed()