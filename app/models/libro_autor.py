from app.extensions import db


class LibroAutor(db.Model):
    __tablename__ = 'libro_autor'

    libro_id = db.Column(db.Integer, db.ForeignKey('libros.id'), primary_key=True)
    autor_id = db.Column(db.Integer, db.ForeignKey('autores.id'), primary_key=True)

    libro = db.relationship('Libro', backref='libro_autor', lazy=True)
    autor = db.relationship('Autor', backref='libro_autor', lazy=True)

    def __repr__(self):
        return f'<LibroAutor libro_id={self.libro_id} autor_id={self.autor_id}>'