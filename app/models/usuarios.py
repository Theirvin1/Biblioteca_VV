from datetime import datetime
from flask_login import UserMixin
from app.extensions import db


class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), nullable=False)
    activo = db.Column(db.Boolean, nullable=False, server_default=db.true())
    intentos_fallidos = db.Column(db.Integer, nullable=False, server_default='0')
    bloqueado = db.Column(db.Boolean, nullable=False, server_default=db.false())
    fecha_bloqueo = db.Column(db.DateTime, nullable=True)
    debe_cambiar_password = db.Column(db.Boolean, nullable=False, server_default=db.false())
    fecha_creacion = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    ultimo_acceso = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.CheckConstraint(
            "rol IN ('bibliotecario', 'estudiante', 'gerente')",
            name='chk_usuarios_rol'
        ),
    )

    def __repr__(self):
        return f'<Usuario {self.username} ({self.rol})>'