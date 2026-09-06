from app.extensions import db


class ConfiguracionSistema(db.Model):
    __tablename__ = 'configuracion_sistema'

    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(50), nullable=False, unique=True)
    valor = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    modificado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    fecha_modificacion = db.Column(db.DateTime, nullable=True, server_default=db.func.now())

    modificador = db.relationship('Usuario', backref='configuraciones_modificadas', lazy=True)

    def __repr__(self):
        return f'<ConfiguracionSistema {self.clave}={self.valor}>'