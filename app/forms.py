from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileSize
from wtforms import (
    StringField, PasswordField, SubmitField, SelectField, IntegerField,
    DateField, TextAreaField, HiddenField
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional, Regexp, EqualTo

from app.portadas import EXTENSIONES_PERMITIDAS, MENSAJE_FORMATO_INVALIDO, MENSAJE_TAMANO_INVALIDO, TAMANO_MAXIMO_BYTES
from app.validators import (
    ANIO_MINIMO_PUBLICACION, EDAD_MAXIMA_ESTUDIANTE, EDAD_MINIMA_ESTUDIANTE,
    AnioValido, CedulaEcuatorianaValida, ContieneLetra, CorreoValido,
    EdadEntre, FechaNoFutura, Isbn13Valido, SoloLetras, TelefonoValido,
)


class LoginForm(FlaskForm):
    username = StringField('Usuario', validators=[DataRequired(message='El usuario es obligatorio')])
    password = PasswordField('Contraseña', validators=[DataRequired(message='La contraseña es obligatoria')])
    submit = SubmitField('Ingresar')


class CambiarPasswordForm(FlaskForm):
    password_actual = PasswordField('Contraseña actual', validators=[DataRequired()])
    password_nueva = PasswordField(
        'Nueva contraseña',
        validators=[DataRequired(), Length(min=6, message='Debe tener al menos 6 caracteres')]
    )
    password_confirmar = PasswordField(
        'Confirmar nueva contraseña',
        validators=[DataRequired(), EqualTo('password_nueva', message='Las contraseñas no coinciden')]
    )
    submit = SubmitField('Cambiar contraseña')


class LibroForm(FlaskForm):
    # ISBN: campo de CREACION de un libro nuevo -> validacion completa
    # (formato + digito verificador real de ISBN-13).
    isbn = StringField('ISBN', validators=[
        DataRequired(message='El ISBN es obligatorio.'),
        Isbn13Valido(),
    ])
    titulo = StringField('Título', validators=[
        DataRequired(message='El título es obligatorio.'),
        Length(min=2, max=255, message='El título debe tener entre 2 y 255 caracteres.'),
        ContieneLetra(message='El título no puede contener solo números o símbolos.'),
    ])
    subtitulo = StringField('Subtítulo', validators=[Optional(), Length(max=255)])
    editorial_nombre = StringField('Editorial', validators=[
        DataRequired(message='La editorial es obligatoria.'),
        Length(min=2, max=150, message='La editorial debe tener entre 2 y 150 caracteres.'),
        ContieneLetra(message='La editorial no puede contener solo números o símbolos.'),
    ])
    categoria_id = SelectField(
        'Categoría', coerce=int,
        validators=[NumberRange(min=1, message='Selecciona una categoría.')]
    )
    anio_publicacion = IntegerField('Año de publicación', validators=[
        Optional(),
        # El minimo lo fija ANIO_MINIMO_PUBLICACION (1800) para no aceptar aqui
        # anios que chk_libros_anio_publicacion rechazaria despues en la BD.
        AnioValido(
            minimo=ANIO_MINIMO_PUBLICACION,
            message=f'Ingresa un año de publicación válido (entre {ANIO_MINIMO_PUBLICACION} y el año actual).',
        ),
    ])
    edicion = StringField('Edición', validators=[Optional(), Length(max=20)])
    num_paginas = IntegerField('Número de páginas', validators=[
        Optional(),
        NumberRange(min=1, message='El número de páginas debe ser mayor a 0.'),
    ])
    idioma = StringField('Idioma', default='Español', validators=[
        DataRequired(message='El idioma es obligatorio.'),
        Length(max=30),
        SoloLetras(message='El idioma solo puede contener letras y espacios.'),
    ])
    stock_inicial = IntegerField(
        'Stock inicial (ejemplares)',
        validators=[
            DataRequired(message='El stock inicial es obligatorio.'),
            NumberRange(min=1, max=200, message='Ingresa una cantidad entre 1 y 200.'),
        ]
    )
    resumen = TextAreaField('Resumen / Sinopsis', validators=[
        Optional(),
        Length(max=5000, message='El resumen no puede superar los 5000 caracteres.'),
    ])
    autores_ids = HiddenField('Autores')
    portada = FileField('Portada del libro (opcional)', validators=[
        Optional(),
        FileAllowed(sorted(EXTENSIONES_PERMITIDAS), message=MENSAJE_FORMATO_INVALIDO),
        FileSize(max_size=TAMANO_MAXIMO_BYTES, message=MENSAJE_TAMANO_INVALIDO),
    ])
    submit = SubmitField('Registrar libro')


class EstudianteForm(FlaskForm):
    # Cedula: campo de CREACION de un estudiante nuevo -> validacion
    # completa (formato + digito verificador real).
    cedula = StringField('Cédula', validators=[
        DataRequired(message='La cédula es obligatoria.'),
        CedulaEcuatorianaValida(),
    ])
    nombres = StringField('Nombres', validators=[
        DataRequired(message='Los nombres son obligatorios.'),
        Length(min=2, max=100, message='Los nombres deben tener entre 2 y 100 caracteres.'),
        SoloLetras(message='Los nombres solo pueden contener letras y espacios.'),
    ])
    apellidos = StringField('Apellidos', validators=[
        DataRequired(message='Los apellidos son obligatorios.'),
        Length(min=2, max=100, message='Los apellidos deben tener entre 2 y 100 caracteres.'),
        SoloLetras(message='Los apellidos solo pueden contener letras y espacios.'),
    ])
    correo = StringField('Correo electrónico', validators=[
        DataRequired(message='El correo es obligatorio.'),
        CorreoValido(),
        Length(max=150),
    ])
    telefono = StringField('Teléfono', validators=[
        Optional(),
        TelefonoValido(),
    ])
    carrera_id = SelectField(
        'Carrera', coerce=int,
        validators=[NumberRange(min=1, message='Selecciona una carrera.')]
    )
    fecha_nacimiento = DateField('Fecha de nacimiento', validators=[
        DataRequired(message='La fecha de nacimiento es obligatoria.'),
        FechaNoFutura(message='La fecha de nacimiento no puede ser futura.'),
        EdadEntre(
            EDAD_MINIMA_ESTUDIANTE, EDAD_MAXIMA_ESTUDIANTE,
            message=f'El estudiante debe tener entre {EDAD_MINIMA_ESTUDIANTE} y {EDAD_MAXIMA_ESTUDIANTE} años.',
        ),
    ])
    genero = SelectField(
        'Género',
        choices=[('', 'Prefiero no decir'), ('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')],
        validators=[Optional()],
    )
    submit = SubmitField('Registrar estudiante')


class TelefonoForm(FlaskForm):
    """
    Autoservicio del estudiante sobre su propio perfil: el UNICO dato que
    puede tocar es su telefono. A proposito no lleva cedula, nombres,
    apellidos, carrera, correo ni estado: como esos campos no existen en este
    formulario, no hay nada que un POST manipulado pueda usar para cambiarlos
    por esta via (el controlador, ademas, toma el estudiante siempre de
    current_user, nunca de un id recibido por POST).

    Telefono es opcional (igual que en EstudianteForm/EditarEstudianteForm):
    dejar el campo vacio es valido y significa "quitar el telefono"; si trae
    contenido, TelefonoValido sigue exigiendo exactamente 10 digitos.
    """
    telefono = StringField('Teléfono', validators=[
        Optional(),
        TelefonoValido(),
    ])
    submit = SubmitField('Guardar teléfono')


class EditarEstudianteForm(FlaskForm):
    """
    Edicion administrativa del bibliotecario sobre un estudiante YA
    registrado: datos de contacto y academicos, reutilizando los mismos
    validadores que EstudianteForm (registro). A proposito NO incluye
    cedula (ver la nota de CedulaEcuatorianaValida/EstudianteForm: la cedula
    es Usuario.username y no se cambia desde la UI normal) ni fecha de
    nacimiento/genero, que no forman parte de esta edicion.
    """
    nombres = StringField('Nombres', validators=[
        DataRequired(message='Los nombres son obligatorios.'),
        Length(min=2, max=100, message='Los nombres deben tener entre 2 y 100 caracteres.'),
        SoloLetras(message='Los nombres solo pueden contener letras y espacios.'),
    ])
    apellidos = StringField('Apellidos', validators=[
        DataRequired(message='Los apellidos son obligatorios.'),
        Length(min=2, max=100, message='Los apellidos deben tener entre 2 y 100 caracteres.'),
        SoloLetras(message='Los apellidos solo pueden contener letras y espacios.'),
    ])
    correo = StringField('Correo electrónico', validators=[
        DataRequired(message='El correo es obligatorio.'),
        CorreoValido(),
        Length(max=150),
    ])
    telefono = StringField('Teléfono', validators=[
        Optional(),
        TelefonoValido(),
    ])
    carrera_id = SelectField(
        'Carrera', coerce=int,
        validators=[NumberRange(min=1, message='Selecciona una carrera.')]
    )
    submit = SubmitField('Guardar cambios')


class PrestamoForm(FlaskForm):
    # Cedula aqui es un campo de BUSQUEDA de un estudiante que ya debe existir
    # (no se crea aqui), por eso se valida solo el formato y no el digito
    # verificador: exigirlo bloquearia prestamos para estudiantes de
    # prueba/demo registrados antes de esa regla.
    cedula = StringField('Cédula del estudiante', validators=[
        DataRequired(message='La cédula es obligatoria.'),
        Regexp(r'^[0-9]{10}$', message='La cédula debe contener exactamente 10 dígitos.')
    ])
    # Lista de ISBN seleccionados para este prestamo, separados por coma. La
    # arma la pantalla al ir agregando libros; el contenido se revalida
    # completo en el servidor (existencia, stock, duplicados y cupos).
    isbns = HiddenField('Libros a prestar')
    observaciones = TextAreaField('Observaciones', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Registrar préstamo')


class DevolucionForm(FlaskForm):
    estado_ejemplar = SelectField(
        'Estado del ejemplar',
        choices=[('bueno', 'Bueno'), ('dañado', 'Dañado'), ('perdido', 'Perdido')],
        validators=[DataRequired(message='Selecciona el estado del ejemplar.')],
    )
    observaciones = TextAreaField('Observaciones', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Registrar devolución')


class AccionUsuarioForm(FlaskForm):
    """
    Acciones administrativas del gerente sobre una cuenta (activar/desactivar,
    restablecer contraseña, cambiar rol). Solo aporta el token CSRF: el destino
    va en la URL y el rol nuevo se lee de request.form contra una lista blanca.
    Todas se ejecutan por POST, nunca por GET.
    """
    submit = SubmitField('Confirmar')


class NuevoUsuarioForm(FlaskForm):
    """
    Creacion de cuentas desde el modal del gerente. Los datos de la ficha de
    estudiante solo son obligatorios cuando rol == 'estudiante': por eso van
    con Optional() a nivel de campo y se exigen en validate().
    Si el rol es estudiante, el username se ignora y se usa la cedula
    (misma convencion que el registro del bibliotecario).
    """
    username = StringField('Nombre de usuario', validators=[
        Optional(), Length(max=50, message='El usuario no puede superar 50 caracteres.'),
    ])
    rol = SelectField('Rol', choices=[
        ('estudiante', 'Estudiante'),
        ('bibliotecario', 'Bibliotecario'),
        ('gerente', 'Gerente'),
    ], validators=[DataRequired(message='Selecciona un rol.')])
    cedula = StringField('Cédula', validators=[Optional(), CedulaEcuatorianaValida()])
    nombres = StringField('Nombres', validators=[
        Optional(),
        Length(min=2, max=100, message='Los nombres deben tener entre 2 y 100 caracteres.'),
        SoloLetras(message='Los nombres solo pueden contener letras y espacios.'),
    ])
    apellidos = StringField('Apellidos', validators=[
        Optional(),
        Length(min=2, max=100, message='Los apellidos deben tener entre 2 y 100 caracteres.'),
        SoloLetras(message='Los apellidos solo pueden contener letras y espacios.'),
    ])
    correo = StringField('Correo electrónico', validators=[
        Optional(), CorreoValido(), Length(max=150),
    ])
    telefono = StringField('Teléfono', validators=[Optional(), TelefonoValido()])
    carrera_id = SelectField('Carrera', coerce=int, validators=[Optional()])
    fecha_nacimiento = DateField('Fecha de nacimiento', validators=[
        Optional(),
        FechaNoFutura(message='La fecha de nacimiento no puede ser futura.'),
        EdadEntre(
            EDAD_MINIMA_ESTUDIANTE, EDAD_MAXIMA_ESTUDIANTE,
            message=f'El estudiante debe tener entre {EDAD_MINIMA_ESTUDIANTE} y {EDAD_MAXIMA_ESTUDIANTE} años.',
        ),
    ])
    genero = SelectField(
        'Género',
        choices=[('', 'Prefiero no decir'), ('M', 'Masculino'), ('F', 'Femenino'), ('O', 'Otro')],
        validators=[Optional()],
    )
    submit = SubmitField('Crear usuario')

    CAMPOS_ESTUDIANTE_OBLIGATORIOS = (
        ('cedula', 'La cédula es obligatoria para el rol estudiante.'),
        ('nombres', 'Los nombres son obligatorios para el rol estudiante.'),
        ('apellidos', 'Los apellidos son obligatorios para el rol estudiante.'),
        ('correo', 'El correo es obligatorio para el rol estudiante.'),
        ('fecha_nacimiento', 'La fecha de nacimiento es obligatoria para el rol estudiante.'),
    )

    def validate(self, extra_validators=None):
        valido = super().validate(extra_validators)
        if self.rol.data == 'estudiante':
            for nombre_campo, mensaje in self.CAMPOS_ESTUDIANTE_OBLIGATORIOS:
                campo = getattr(self, nombre_campo)
                if not campo.data:
                    campo.errors.append(mensaje)
                    valido = False
            if not self.carrera_id.data or self.carrera_id.data < 1:
                self.carrera_id.errors.append('Selecciona una carrera.')
                valido = False
        elif self.rol.data in ('bibliotecario', 'gerente'):
            if not (self.username.data or '').strip():
                self.username.errors.append('El nombre de usuario es obligatorio.')
                valido = False
        else:
            self.rol.errors.append('Rol no válido.')
            valido = False
        return valido


class DevolucionLoteForm(FlaskForm):
    """
    Devolucion de varios libros de una misma operacion.

    Los campos por libro (casilla, estado y observacion) son dinamicos: se
    generan en la plantilla a partir de los prestamos pendientes y se leen
    desde request.form en el controlador. Este form aporta el token CSRF y el
    boton, que es lo unico fijo.
    """
    submit = SubmitField('Registrar devolución seleccionada')
