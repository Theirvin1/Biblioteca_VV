from app.extensions import db


class Ejemplar(db.Model):
    __tablename__ = 'ejemplares'

    id = db.Column(db.Integer, primary_key=True)
    libro_id = db.Column(db.Integer, db.ForeignKey('libros.id'), nullable=False)
    codigo_ejemplar = db.Column(db.String(20), nullable=False, unique=True)
    estado = db.Column(db.String(15), nullable=False, server_default='disponible')
    fecha_adquisicion = db.Column(db.Date, nullable=False)
    observaciones = db.Column(db.Text, nullable=True)

    libro = db.relationship('Libro', backref='ejemplares', lazy=True)

    __table_args__ = (
        db.CheckConstraint(
            "estado IN ('disponible', 'prestado', 'dañado', 'baja')",
            name='chk_ejemplares_estado'
        ),
    )

    def __repr__(self):
        return f'<Ejemplar {self.codigo_ejemplar} ({self.estado})>'