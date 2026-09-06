from app.extensions import db


class Prestamo(db.Model):
    __tablename__ = 'prestamos'

    id = db.Column(db.Integer, primary_key=True)
    codigo_prestamo = db.Column(db.String(20), nullable=False, unique=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False)
    ejemplar_id = db.Column(db.Integer, db.ForeignKey('ejemplares.id'), nullable=False)
    bibliotecario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha_prestamo = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    fecha_limite = db.Column(db.Date, nullable=False)
    estado = db.Column(db.String(10), nullable=False, server_default='activo')
    renovaciones = db.Column(db.Integer, nullable=False, server_default='0')
    observaciones = db.Column(db.Text, nullable=True)
    # Codigo de la OPERACION en la que se registro el prestamo (ej. 'GRP-2026-0001').
    # Varios prestamos creados en un mismo registro comparten este codigo, pero cada
    # uno sigue siendo un prestamo individual (fechas, multa y devolucion propias).
    # Es NULL en los prestamos anteriores a esta funcionalidad: en ese caso se tratan
    # como una operacion de un solo libro.
    grupo_prestamo = db.Column(db.String(20), nullable=True)

    estudiante = db.relationship('Estudiante', backref='prestamos', lazy=True)
    ejemplar = db.relationship('Ejemplar', backref='prestamos', lazy=True)
    bibliotecario = db.relationship('Usuario', backref='prestamos_registrados', lazy=True)

    __table_args__ = (
        db.CheckConstraint("estado IN ('activo', 'devuelto', 'vencido')", name='chk_prestamos_estado'),
        db.CheckConstraint('fecha_limite > fecha_prestamo::DATE', name='chk_prestamos_fecha_limite'),
        db.CheckConstraint('renovaciones >= 0', name='chk_prestamos_renovaciones'),
    )

    def __repr__(self):
        return f'<Prestamo {self.codigo_prestamo} ({self.estado})>'