from app.extensions import db


class Editorial(db.Model):
    __tablename__ = 'editoriales'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    pais_id = db.Column(db.Integer, db.ForeignKey('paises.id'), nullable=True)
    pais = db.relationship('Pais', backref='editoriales', lazy=True)

    def __repr__(self):
        return f'<Editorial {self.nombre}>'