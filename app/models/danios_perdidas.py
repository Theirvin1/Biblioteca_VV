from app.extensions import db


class DanioPerdida(db.Model):
    __tablename__ = 'danios_perdidas'

    id = db.Column(db.Integer, primary_key=True)
    devolucion_id = db.Column(db.Integer, db.ForeignKey('devoluciones.id'), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    costo_estimado = db.Column(db.Numeric(8, 2), nullable=True)
    reportado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha_reporte = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    resuelto = db.Column(db.Boolean, nullable=False, server_default=db.false())

    devolucion = db.relationship('Devolucion', backref='danios_perdidas', lazy=True)
    reportante = db.relationship('Usuario', backref='reportes_danios', lazy=True)

    __table_args__ = (
        db.CheckConstraint("tipo IN ('danio', 'perdida')", name='chk_danios_perdidas_tipo'),
        db.CheckConstraint('costo_estimado >= 0', name='chk_danios_perdidas_costo_positivo'),
    )

    def __repr__(self):
        return f'<DanioPerdida {self.tipo} devolucion_id={self.devolucion_id}>'