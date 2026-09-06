from app.extensions import db


class Notificacion(db.Model):
    __tablename__ = 'notificaciones'

    id = db.Column(db.Integer, primary_key=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False)
    prestamo_id = db.Column(db.Integer, db.ForeignKey('prestamos.id'), nullable=True)
    plantilla_id = db.Column(db.Integer, db.ForeignKey('plantillas_notificacion.id'), nullable=False)
    mensaje = db.Column(db.Text, nullable=False)
    fecha_programada = db.Column(db.DateTime, nullable=False)
    fecha_enviada = db.Column(db.DateTime, nullable=True)
    estado = db.Column(db.String(10), nullable=False, server_default='pendiente')
    canal = db.Column(db.String(10), nullable=False)
    leida = db.Column(db.Boolean, nullable=False, server_default=db.false())
    fecha_lectura = db.Column(db.DateTime, nullable=True)

    estudiante = db.relationship('Estudiante', backref='notificaciones', lazy=True)
    prestamo = db.relationship('Prestamo', backref='notificaciones', lazy=True)
    plantilla = db.relationship('PlantillaNotificacion', backref='notificaciones', lazy=True)

    __table_args__ = (
        db.CheckConstraint("estado IN ('pendiente', 'enviada', 'fallida')", name='chk_notificaciones_estado'),
        db.CheckConstraint("canal IN ('sistema', 'correo')", name='chk_notificaciones_canal'),
    )

    def __repr__(self):
        return f'<Notificacion estudiante_id={self.estudiante_id} estado={self.estado}>'