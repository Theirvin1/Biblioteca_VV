from app.extensions import db


class Estudiante(db.Model):
    __tablename__ = 'estudiantes'

    id = db.Column(db.Integer, primary_key=True)
    cedula = db.Column(db.String(10), nullable=False, unique=True)
    nombres = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    correo = db.Column(db.String(150), nullable=False, unique=True)
    telefono = db.Column(db.String(15), nullable=True)
    carrera_id = db.Column(db.Integer, db.ForeignKey('carreras.id'), nullable=False)
    fecha_nacimiento = db.Column(db.Date, nullable=True)
    genero = db.Column(db.String(1), nullable=True)
    fecha_registro = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    estado = db.Column(db.String(15), nullable=False, server_default='activo')
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True, unique=True)

    carrera = db.relationship('Carrera', backref='estudiantes', lazy=True)
    usuario = db.relationship('Usuario', backref=db.backref('estudiante', uselist=False), lazy=True)

    __table_args__ = (
        db.CheckConstraint(r"cedula ~ '^[0-9]{10}$'", name='chk_estudiantes_cedula'),
        db.CheckConstraint(r"correo ~ '^[^@]+@[^@]+\.[^@]+$'", name='chk_estudiantes_correo'),
        db.CheckConstraint("estado IN ('activo', 'suspendido')", name='chk_estudiantes_estado'),
        db.CheckConstraint("genero IN ('M', 'F', 'O')", name='chk_estudiantes_genero'),
    )

    def __repr__(self):
        return f'<Estudiante {self.nombres} {self.apellidos} ({self.cedula})>'