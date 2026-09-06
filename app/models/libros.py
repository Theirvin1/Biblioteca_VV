from app.extensions import db


class Libro(db.Model):
    __tablename__ = 'libros'

    id = db.Column(db.Integer, primary_key=True)
    isbn = db.Column(db.String(13), nullable=False, unique=True)
    titulo = db.Column(db.String(255), nullable=False)
    subtitulo = db.Column(db.String(255), nullable=True)
    editorial_id = db.Column(db.Integer, db.ForeignKey('editoriales.id'), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias_libro.id'), nullable=False)
    anio_publicacion = db.Column(db.Integer, nullable=True)
    edicion = db.Column(db.String(20), nullable=True)
    num_paginas = db.Column(db.Integer, nullable=True)
    idioma = db.Column(db.String(30), nullable=False, server_default='Español')
    stock_total = db.Column(db.Integer, nullable=False, server_default='0')
    stock_disponible = db.Column(db.Integer, nullable=False, server_default='0')
    fecha_registro = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    activo = db.Column(db.Boolean, nullable=False, server_default=db.true())
    # Ruta relativa a app/static/ (ej. 'uploads/portadas/<uuid>.jpg'). Opcional:
    # los libros sin portada (incluidos los ya existentes) usan un placeholder.
    portada_archivo = db.Column(db.String(255), nullable=True)
    # Resumen/sinopsis opcional. Text (no VARCHAR) para admitir textos largos;
    # se muestra en un modal, nunca dentro de una tabla. Los libros existentes
    # quedan en NULL y siguen funcionando igual (ver url_portada/plantillas).
    resumen = db.Column(db.Text, nullable=True)

    editorial = db.relationship('Editorial', backref='libros', lazy=True)
    categoria = db.relationship('CategoriaLibro', backref='libros', lazy=True)

    __table_args__ = (
        db.CheckConstraint('LENGTH(isbn) = 13', name='chk_libros_isbn_longitud'),
        db.CheckConstraint('stock_disponible >= 0', name='chk_libros_stock_disponible_positivo'),
        db.CheckConstraint('stock_total >= 0', name='chk_libros_stock_total_positivo'),
        db.CheckConstraint('stock_disponible <= stock_total', name='chk_libros_stock_coherente'),
        db.CheckConstraint('num_paginas > 0', name='chk_libros_num_paginas'),
        db.CheckConstraint(
            'anio_publicacion BETWEEN 1800 AND EXTRACT(YEAR FROM NOW())',
            name='chk_libros_anio_publicacion'
        ),
    )

    def __repr__(self):
        return f'<Libro {self.titulo} ({self.isbn})>'