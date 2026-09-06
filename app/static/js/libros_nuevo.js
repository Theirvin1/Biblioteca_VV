document.addEventListener('DOMContentLoaded', function () {
    const inputBuscar = document.getElementById('buscar-autor');
    const listaResultados = document.getElementById('resultados-autores');
    const inputNombres = document.getElementById('nuevo-autor-nombres');
    const inputApellidos = document.getElementById('nuevo-autor-apellidos');
    const btnCrear = document.getElementById('btn-crear-autor');
    const contenedorSeleccionados = document.getElementById('autores-seleccionados');
    const mensaje = document.getElementById('autores-mensaje');
    const campoAutoresIds = document.getElementById('autores_ids');

    if (!inputBuscar) return;

    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    const seleccionados = new Map();
    let temporizador = null;

    function actualizarCampoOculto() {
        campoAutoresIds.value = Array.from(seleccionados.keys()).join(',');
    }

    function renderSeleccionados() {
        contenedorSeleccionados.innerHTML = '';
        seleccionados.forEach(function (nombre, id) {
            const chip = document.createElement('span');
            chip.className = 'badge text-bg-primary d-flex align-items-center gap-2 p-2';
            chip.textContent = nombre;

            const botonQuitar = document.createElement('button');
            botonQuitar.type = 'button';
            botonQuitar.className = 'btn-close btn-close-white btn-sm';
            botonQuitar.setAttribute('aria-label', 'Quitar');
            botonQuitar.addEventListener('click', function () {
                seleccionados.delete(id);
                renderSeleccionados();
                actualizarCampoOculto();
            });

            chip.appendChild(botonQuitar);
            contenedorSeleccionados.appendChild(chip);
        });
    }

    function agregarAutor(id, nombre) {
        seleccionados.set(id, nombre);
        renderSeleccionados();
        actualizarCampoOculto();
        listaResultados.innerHTML = '';
        inputBuscar.value = '';
        mensaje.textContent = '';
    }

    function buscarAutores() {
        const termino = inputBuscar.value.trim();
        if (termino.length < 2) {
            listaResultados.innerHTML = '';
            return;
        }
        fetch('/bibliotecario/api/autores/buscar?q=' + encodeURIComponent(termino))
            .then(function (resp) { return resp.json(); })
            .then(function (autores) {
                listaResultados.innerHTML = '';
                if (!autores.length) {
                    const li = document.createElement('li');
                    li.className = 'list-group-item text-muted';
                    li.textContent = 'Sin coincidencias';
                    listaResultados.appendChild(li);
                    return;
                }
                autores.forEach(function (autor) {
                    const li = document.createElement('li');
                    li.className = 'list-group-item list-group-item-action';
                    li.style.cursor = 'pointer';
                    li.textContent = autor.nombre;
                    li.addEventListener('click', function () {
                        agregarAutor(String(autor.id), autor.nombre);
                    });
                    listaResultados.appendChild(li);
                });
            });
    }

    inputBuscar.addEventListener('input', function () {
        clearTimeout(temporizador);
        temporizador = setTimeout(buscarAutores, 300);
    });

    btnCrear.addEventListener('click', function () {
        const nombres = inputNombres.value.trim();
        const apellidos = inputApellidos.value.trim();
        mensaje.textContent = '';

        if (!nombres || !apellidos) {
            mensaje.className = 'small text-danger';
            mensaje.textContent = 'Ingresa nombres y apellidos del nuevo autor.';
            return;
        }

        fetch('/bibliotecario/api/autores', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ nombres: nombres, apellidos: apellidos })
        })
            .then(function (resp) {
                return resp.json().then(function (datos) { return { ok: resp.ok, datos: datos }; });
            })
            .then(function (resultado) {
                if (!resultado.ok) {
                    mensaje.className = 'small text-danger';
                    mensaje.textContent = resultado.datos.error || 'No se pudo crear el autor.';
                    return;
                }
                agregarAutor(String(resultado.datos.id), resultado.datos.nombre);
                inputNombres.value = '';
                inputApellidos.value = '';
            })
            .catch(function () {
                mensaje.className = 'small text-danger';
                mensaje.textContent = 'Error de conexión al crear el autor.';
            });
    });

    document.querySelector('form').addEventListener('submit', function (evento) {
        if (seleccionados.size === 0) {
            evento.preventDefault();
            mensaje.className = 'small text-danger';
            mensaje.textContent = 'Agrega al menos un autor antes de guardar.';
        }
    });
});
