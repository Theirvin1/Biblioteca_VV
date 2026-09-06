from app.extensions import db


class CategoriaLibro(db.Model):
    __tablename__ = 'categorias_libro'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)
    descripcion = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<CategoriaLibro {self.nombre}>'