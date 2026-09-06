from app.extensions import db


class Devolucion(db.Model):
    __tablename__ = 'devoluciones'

    id = db.Column(db.Integer, primary_key=True)
    prestamo_id = db.Column(db.Integer, db.ForeignKey('prestamos.id'), nullable=False, unique=True)
    bibliotecario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha_devolucion = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    estado_ejemplar = db.Column(db.String(15), nullable=False)
    dias_retraso = db.Column(db.Integer, nullable=False, server_default='0')
    multa_generada = db.Column(db.Numeric(8, 2), nullable=False, server_default='0')
    multa_pagada = db.Column(db.Boolean, nullable=False, server_default=db.false())
    fecha_pago_multa = db.Column(db.Date, nullable=True)
    observaciones = db.Column(db.Text, nullable=True)

    prestamo = db.relationship('Prestamo', backref=db.backref('devolucion', uselist=False), lazy=True)
    bibliotecario = db.relationship('Usuario', backref='devoluciones_registradas', lazy=True)

    __table_args__ = (
        db.CheckConstraint("estado_ejemplar IN ('bueno', 'dañado', 'perdido')", name='chk_devoluciones_estado_ejemplar'),
        db.CheckConstraint('dias_retraso >= 0', name='chk_devoluciones_dias_retraso'),
        db.CheckConstraint('multa_generada >= 0', name='chk_devoluciones_multa_positiva'),
    )

    def __repr__(self):
        return f'<Devolucion prestamo_id={self.prestamo_id} multa={self.multa_generada}>'