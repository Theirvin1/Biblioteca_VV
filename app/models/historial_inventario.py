from app.extensions import db


class HistorialInventario(db.Model):
    __tablename__ = 'historial_inventario'

    id = db.Column(db.Integer, primary_key=True)
    ejemplar_id = db.Column(db.Integer, db.ForeignKey('ejemplares.id'), nullable=False)
    tipo_movimiento = db.Column(db.String(15), nullable=False)
    estado_anterior = db.Column(db.String(15), nullable=True)
    estado_nuevo = db.Column(db.String(15), nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    prestamo_id = db.Column(db.Integer, db.ForeignKey('prestamos.id'), nullable=True)
    fecha_hora = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    observaciones = db.Column(db.Text, nullable=True)

    ejemplar = db.relationship('Ejemplar', backref='historial_inventario', lazy=True)
    usuario = db.relationship('Usuario', backref='movimientos_inventario', lazy=True)
    prestamo = db.relationship('Prestamo', backref='movimientos_inventario', lazy=True)

    __table_args__ = (
        db.CheckConstraint(
            "tipo_movimiento IN ('adquisicion', 'prestamo', 'devolucion', 'baja', 'danio')",
            name='chk_historial_inventario_tipo'
        ),
    )

    def __repr__(self):
        return f'<HistorialInventario {self.tipo_movimiento} ejemplar_id={self.ejemplar_id}>'