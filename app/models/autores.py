from app.extensions import db


class Autor(db.Model):
    __tablename__ = 'autores'

    id = db.Column(db.Integer, primary_key=True)
    nombres = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    nacionalidad_id = db.Column(db.Integer, db.ForeignKey('paises.id'), nullable=True)

    nacionalidad = db.relationship('Pais', backref='autores', lazy=True)

    def __repr__(self):
        return f'<Autor {self.nombres} {self.apellidos}>'