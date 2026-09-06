from app.extensions import db


class PlantillaNotificacion(db.Model):
    __tablename__ = 'plantillas_notificacion'

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(30), nullable=False, unique=True)
    asunto = db.Column(db.String(200), nullable=False)
    cuerpo_mensaje = db.Column(db.Text, nullable=False)
    activa = db.Column(db.Boolean, nullable=False, server_default=db.true())

    def __repr__(self):
        return f'<PlantillaNotificacion {self.tipo}>'