from app.extensions import db


class Facultad(db.Model):
    __tablename__ = 'facultades'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False, unique=True)

    def __repr__(self):
        return f'<Facultad {self.nombre}>'