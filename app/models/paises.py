from app.extensions import db


class Pais(db.Model):
    __tablename__ = 'paises'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)

    def __repr__(self):
        return f'<Pais {self.nombre}>'