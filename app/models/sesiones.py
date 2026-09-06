from app.extensions import db


class Sesion(db.Model):
    __tablename__ = 'sesiones'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha_inicio = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    fecha_fin = db.Column(db.DateTime(timezone=True), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    dispositivo = db.Column(db.String(200), nullable=True)
    resultado = db.Column(db.String(10), nullable=False)
    motivo_cierre = db.Column(db.String(20), nullable=True)

    usuario = db.relationship('Usuario', backref='sesiones', lazy=True)

    __table_args__ = (
        db.CheckConstraint("resultado IN ('exitoso', 'fallido')", name='chk_sesiones_resultado'),
        db.CheckConstraint(
            "motivo_cierre IN ('logout', 'expiracion', 'forzado')",
            name='chk_sesiones_motivo_cierre'
        ),
    )

    def __repr__(self):
        return f'<Sesion usuario_id={self.usuario_id} resultado={self.resultado}>'