/*
 * Registro de prestamo con varios libros.
 *
 * Arma en pantalla la lista de libros a prestar y la envia en el campo oculto
 * "isbns" (separados por coma). Todo lo que se valida aqui es solo para guiar
 * al bibliotecario: el servidor vuelve a validar estudiante, cupos, stock,
 * duplicados y disponibilidad antes de guardar.
 */
document.addEventListener('DOMContentLoaded', function () {
    const inputCedula = document.getElementById('cedula');
    const inputIsbn = document.getElementById('isbn');
    const campoIsbns = document.getElementById('isbns');
    const tarjetaEstudiante = document.getElementById('tarjeta-estudiante');
    const tarjetaLibro = document.getElementById('tarjeta-libro');
    const btnAgregar = document.getElementById('btn-agregar-libro');
    const cuerpoTabla = document.querySelector('#tabla-seleccionados tbody');
    const contador = document.getElementById('contador-seleccion');
    const formulario = document.getElementById('form-prestamo');
    const btnRegistrar = document.getElementById('btn-registrar-prestamo');
    const overlay = document.getElementById('overlay-procesando');

    if (!inputCedula || !inputIsbn || !campoIsbns || !cuerpoTabla) return;

    let estudiante = null;      // datos del estudiante validado
    let cedulaCargada = '';     // cedula con la que se armo la lista actual
    let libroActual = null;     // libro mostrado en la tarjeta
    let seleccionados = [];     // libros agregados al prestamo
    let enviando = false;

    function escapar(texto) {
        const div = document.createElement('div');
        div.textContent = texto == null ? '' : texto;
        return div.innerHTML;
    }

    function alerta(tipo, mensaje) {
        return '<div class="alert alert-' + tipo + ' mb-0 py-2">' + escapar(mensaje) + '</div>';
    }

    function maximoPermitido() {
        if (!estudiante || estudiante.cupos_disponibles === null) return null;
        return estudiante.cupos_disponibles;
    }

    // ---------------------------------------------------------- tarjetas

    function pintarEstudiante(datos) {
        tarjetaEstudiante.classList.remove('d-none');

        if (!datos.nombre_completo) {
            tarjetaEstudiante.innerHTML = alerta('danger', datos.mensaje);
            return;
        }

        const cupos = datos.cupos_disponibles === null ? '—' : datos.cupos_disponibles;
        const maximo = datos.max_prestamos === null ? 'sin límite' : datos.max_prestamos;
        const edad = datos.edad === null ? 'No registrada' : datos.edad + ' años';
        const claseEstado = datos.estado === 'activo' ? 'text-bg-success' : 'text-bg-danger';

        let advertencia = '';
        if (datos.advertencia) {
            advertencia = '<div class="alert alert-danger mt-3 mb-0 py-2">' +
                escapar(datos.advertencia) + '</div>';
        } else if (!datos.ok) {
            advertencia = '<div class="alert alert-danger mt-3 mb-0 py-2">' +
                escapar(datos.mensaje) + '</div>';
        }

        tarjetaEstudiante.innerHTML =
            '<div class="card border-0 bg-light">' +
              '<div class="card-body">' +
                '<div class="d-flex flex-wrap gap-3 align-items-center">' +
                  '<div class="avatar-iniciales">' + escapar(datos.iniciales) + '</div>' +
                  '<div class="flex-grow-1">' +
                    '<h5 class="mb-1">' + escapar(datos.nombre_completo) + '</h5>' +
                    '<div class="text-muted small">Cédula ' + escapar(datos.cedula) +
                      ' · ' + escapar(edad) + '</div>' +
                    '<div class="text-muted small">' + escapar(datos.carrera) + '</div>' +
                  '</div>' +
                  '<span class="badge ' + claseEstado + ' align-self-start">' +
                    escapar(datos.estado) + '</span>' +
                '</div>' +
                '<div class="row g-2 mt-2 text-center">' +
                  '<div class="col-4"><div class="border rounded py-2 bg-white">' +
                    '<div class="fw-bold fs-5">' + escapar(datos.prestamos_activos) + '</div>' +
                    '<div class="text-muted small">Préstamos activos</div></div></div>' +
                  '<div class="col-4"><div class="border rounded py-2 bg-white">' +
                    '<div class="fw-bold fs-5">' + escapar(maximo) + '</div>' +
                    '<div class="text-muted small">Máximo permitido</div></div></div>' +
                  '<div class="col-4"><div class="border rounded py-2 bg-white">' +
                    '<div class="fw-bold fs-5">' + escapar(cupos) + '</div>' +
                    '<div class="text-muted small">Cupos disponibles</div></div></div>' +
                '</div>' +
                advertencia +
              '</div>' +
            '</div>';
    }

    function pintarLibro(datos) {
        tarjetaLibro.classList.remove('d-none');

        if (!datos.titulo) {
            tarjetaLibro.innerHTML = alerta('danger', datos.mensaje);
            btnAgregar.classList.add('d-none');
            return;
        }

        const anio = datos.anio ? datos.anio : 'No registrado';
        const claseStock = datos.stock_disponible > 0 ? 'text-bg-success' : 'text-bg-danger';
        const textoStock = datos.stock_disponible + ' de ' + datos.stock_total + ' disponibles';
        const aviso = datos.ok ? '' :
            '<div class="alert alert-danger mt-3 mb-0 py-2">' + escapar(datos.mensaje) + '</div>';

        tarjetaLibro.innerHTML =
            '<div class="card border-0 bg-light">' +
              '<div class="card-body">' +
                '<div class="d-flex flex-wrap gap-3">' +
                  '<img src="' + escapar(datos.portada_url) + '" alt="Portada" class="portada-mini">' +
                  '<div class="flex-grow-1">' +
                    '<h5 class="mb-1">' + escapar(datos.titulo) + '</h5>' +
                    '<div class="text-muted small">' + escapar(datos.autores) + '</div>' +
                    '<div class="text-muted small">ISBN ' + escapar(datos.isbn) + '</div>' +
                    '<div class="text-muted small">' + escapar(datos.categoria) + ' · ' +
                      escapar(datos.editorial) + ' · ' + escapar(anio) + '</div>' +
                    '<span class="badge ' + claseStock + ' mt-2">' + escapar(textoStock) + '</span>' +
                  '</div>' +
                '</div>' +
                aviso +
              '</div>' +
            '</div>';

        btnAgregar.classList.remove('d-none');
        actualizarBotonAgregar();
    }

    /* Solo se puede agregar si el libro es prestable, el estudiante es valido,
       el libro no esta ya en la lista y quedan cupos. */
    function actualizarBotonAgregar() {
        if (!libroActual || btnAgregar.classList.contains('d-none')) return;

        const maximo = maximoPermitido();
        const duplicado = seleccionados.some(function (libro) {
            return libro.isbn === libroActual.isbn;
        });

        btnAgregar.disabled = !libroActual.ok
            || !estudiante || !estudiante.ok
            || duplicado
            || (maximo !== null && seleccionados.length >= maximo);
    }

    // ---------------------------------------------------------- seleccion

    function sincronizar() {
        campoIsbns.value = seleccionados.map(function (libro) { return libro.isbn; }).join(',');

        cuerpoTabla.innerHTML = '';
        seleccionados.forEach(function (libro) {
            const fila = document.createElement('tr');
            fila.innerHTML =
                '<td><img src="' + escapar(libro.portada_url) + '" alt="Portada" class="portada-mini-tabla"></td>' +
                '<td class="small">' + escapar(libro.isbn) + '</td>' +
                '<td>' + escapar(libro.titulo) + '</td>' +
                '<td><span class="badge text-bg-success">' +
                    escapar(libro.stock_disponible + ' disponibles') + '</span></td>' +
                '<td class="text-end"><button type="button" class="btn btn-sm btn-outline-danger" ' +
                    'data-quitar="' + escapar(libro.isbn) + '">Quitar</button></td>';
            cuerpoTabla.appendChild(fila);
        });

        if (seleccionados.length === 0) {
            const vacia = document.createElement('tr');
            vacia.innerHTML = '<td colspan="5" class="text-center text-muted py-3">' +
                'Todavía no has agregado libros a este préstamo.</td>';
            cuerpoTabla.appendChild(vacia);
        }

        const maximo = maximoPermitido();
        contador.textContent = maximo === null
            ? seleccionados.length + ' libro(s) seleccionado(s)'
            : seleccionados.length + ' de ' + maximo + ' libros seleccionados';

        if (seleccionados.length > 0) {
            contador.classList.remove('text-danger');
        }

        actualizarBotonAgregar();
    }

    cuerpoTabla.addEventListener('click', function (evento) {
        const boton = evento.target.closest('[data-quitar]');
        if (!boton) return;
        const isbn = boton.getAttribute('data-quitar');
        seleccionados = seleccionados.filter(function (libro) { return libro.isbn !== isbn; });
        sincronizar();
    });

    btnAgregar.addEventListener('click', function () {
        if (!libroActual || !libroActual.ok) return;

        if (!estudiante || !estudiante.ok) {
            pintarLibro(Object.assign({}, libroActual, {
                ok: false, mensaje: 'Primero selecciona un estudiante válido.'
            }));
            return;
        }

        const yaEsta = seleccionados.some(function (libro) { return libro.isbn === libroActual.isbn; });
        if (yaEsta) {
            pintarLibro(Object.assign({}, libroActual, {
                ok: false, mensaje: 'Este libro ya fue agregado.'
            }));
            return;
        }

        const maximo = maximoPermitido();
        if (maximo !== null && seleccionados.length >= maximo) {
            pintarLibro(Object.assign({}, libroActual, {
                ok: false,
                mensaje: 'El estudiante alcanzó el máximo de préstamos activos (' + maximo + ' cupos).'
            }));
            return;
        }

        seleccionados.push(libroActual);
        sincronizar();

        libroActual = null;
        inputIsbn.value = '';
        tarjetaLibro.classList.add('d-none');
        tarjetaLibro.innerHTML = '';
        btnAgregar.classList.add('d-none');
        inputIsbn.focus();
    });

    // ---------------------------------------------------------- consultas

    function buscarEstudiante() {
        const cedula = inputCedula.value.trim();

        if (cedula !== cedulaCargada && seleccionados.length > 0) {
            // Al cambiar de estudiante los cupos cambian: se reinicia la lista.
            seleccionados = [];
            sincronizar();
        }

        if (cedula.length !== 10) {
            estudiante = null;
            cedulaCargada = '';
            tarjetaEstudiante.classList.add('d-none');
            tarjetaEstudiante.innerHTML = '';
            sincronizar();
            return Promise.resolve();
        }

        return fetch('/bibliotecario/api/prestamos/estudiante?cedula=' + encodeURIComponent(cedula))
            .then(function (respuesta) { return respuesta.json(); })
            .then(function (datos) {
                estudiante = datos;
                cedulaCargada = cedula;
                pintarEstudiante(datos);
                sincronizar();
            })
            .catch(function () {
                tarjetaEstudiante.classList.remove('d-none');
                tarjetaEstudiante.innerHTML = alerta('danger', 'No se pudo consultar al estudiante.');
            });
    }

    function buscarLibro(isbn) {
        return fetch('/bibliotecario/api/prestamos/libro?isbn=' + encodeURIComponent(isbn))
            .then(function (respuesta) { return respuesta.json(); })
            .then(function (datos) {
                libroActual = datos.titulo ? datos : null;
                pintarLibro(datos);
                return datos;
            })
            .catch(function () {
                libroActual = null;
                tarjetaLibro.classList.remove('d-none');
                tarjetaLibro.innerHTML = alerta('danger', 'No se pudo consultar el libro.');
            });
    }

    function consultarLibroDesdeInput() {
        const isbn = inputIsbn.value.trim();
        if (isbn.length !== 13) {
            libroActual = null;
            tarjetaLibro.classList.add('d-none');
            tarjetaLibro.innerHTML = '';
            btnAgregar.classList.add('d-none');
            return;
        }
        buscarLibro(isbn);
    }

    let temporizadorCedula = null;
    inputCedula.addEventListener('input', function () {
        clearTimeout(temporizadorCedula);
        temporizadorCedula = setTimeout(buscarEstudiante, 350);
    });

    let temporizadorIsbn = null;
    inputIsbn.addEventListener('input', function () {
        clearTimeout(temporizadorIsbn);
        temporizadorIsbn = setTimeout(consultarLibroDesdeInput, 350);
    });

    // Enter en el ISBN agrega el libro en vez de enviar el formulario.
    inputIsbn.addEventListener('keydown', function (evento) {
        if (evento.key === 'Enter') {
            evento.preventDefault();
            if (btnAgregar && !btnAgregar.classList.contains('d-none') && !btnAgregar.disabled) {
                btnAgregar.click();
            }
        }
    });

    // ---------------------------------------------------------- envio

    formulario.addEventListener('submit', function (evento) {
        if (enviando) {
            evento.preventDefault();
            return;
        }

        if (seleccionados.length === 0) {
            evento.preventDefault();
            contador.textContent = 'Agrega al menos un libro al préstamo.';
            contador.classList.add('text-danger');
            return;
        }

        enviando = true;
        btnRegistrar.disabled = true;
        overlay.classList.remove('d-none');
    });

    // Si el navegador restaura la pagina desde el cache (boton "atras"),
    // el boton debe volver a quedar utilizable.
    window.addEventListener('pageshow', function () {
        enviando = false;
        btnRegistrar.disabled = false;
        overlay.classList.add('d-none');
    });

    // ---------------------------------------------------------- rehidratacion
    // Si el servidor devolvio el formulario con un error, se reconstruye la
    // seleccion que traia el campo oculto para no perder el trabajo hecho.
    const isbnsPrevios = (campoIsbns.value || '').split(',')
        .map(function (valor) { return valor.trim(); })
        .filter(function (valor) { return valor.length === 13; });

    sincronizar();

    buscarEstudiante().then(function () {
        isbnsPrevios.reduce(function (cadena, isbn) {
            return cadena.then(function () {
                return fetch('/bibliotecario/api/prestamos/libro?isbn=' + encodeURIComponent(isbn))
                    .then(function (respuesta) { return respuesta.json(); })
                    .then(function (datos) {
                        if (datos.titulo) {
                            seleccionados.push(datos);
                            sincronizar();
                        }
                    })
                    .catch(function () { /* se ignora: la lista se puede rearmar a mano */ });
            });
        }, Promise.resolve());
    });
});
