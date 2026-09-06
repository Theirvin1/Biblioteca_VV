from app.extensions import db


class Carrera(db.Model):
    __tablename__ = 'carreras'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    facultad_id = db.Column(db.Integer, db.ForeignKey('facultades.id'), nullable=False)

    facultad = db.relationship('Facultad', backref='carreras', lazy=True)

    def __repr__(self):
        return f'<Carrera {self.nombre}>'