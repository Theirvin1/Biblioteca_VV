from app.extensions import db


class RenovacionPrestamo(db.Model):
    __tablename__ = 'renovaciones_prestamo'

    id = db.Column(db.Integer, primary_key=True)
    prestamo_id = db.Column(db.Integer, db.ForeignKey('prestamos.id'), nullable=False)
    bibliotecario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha_renovacion = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    fecha_limite_anterior = db.Column(db.Date, nullable=False)
    fecha_limite_nueva = db.Column(db.Date, nullable=False)
    motivo = db.Column(db.Text, nullable=True)

    prestamo = db.relationship('Prestamo', backref='historial_renovaciones', lazy=True)
    bibliotecario = db.relationship('Usuario', backref='renovaciones_autorizadas', lazy=True)

    def __repr__(self):
        return f'<RenovacionPrestamo prestamo_id={self.prestamo_id}>'