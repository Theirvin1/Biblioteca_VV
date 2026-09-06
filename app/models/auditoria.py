from sqlalchemy.dialects.postgresql import JSONB
from app.extensions import db


class Auditoria(db.Model):
    __tablename__ = 'auditoria'

    id = db.Column(db.Integer, primary_key=True)
    tabla_afectada = db.Column(db.String(50), nullable=False)
    operacion = db.Column(db.String(10), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    fecha_hora = db.Column(db.DateTime(timezone=True), nullable=False, server_default=db.func.now())
    datos_anteriores = db.Column(JSONB, nullable=True)
    datos_nuevos = db.Column(JSONB, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    modulo = db.Column(db.String(30), nullable=True)

    usuario = db.relationship('Usuario', backref='registros_auditoria', lazy=True)

    __table_args__ = (
        db.CheckConstraint("operacion IN ('INSERT', 'UPDATE', 'DELETE')", name='chk_auditoria_operacion'),
    )

    def __repr__(self):
        return f'<Auditoria {self.tabla_afectada} {self.operacion}>'