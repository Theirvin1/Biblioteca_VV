/*
 * Devolucion parcial/total de una operacion: marcar todos, exigir al menos un
 * libro seleccionado y evitar el doble envio mostrando el overlay de proceso.
 * El servidor vuelve a validar la seleccion antes de guardar.
 */
document.addEventListener('DOMContentLoaded', function () {
    const formulario = document.getElementById('form-devolucion');
    const boton = document.getElementById('btn-registrar-devolucion');
    const overlay = document.getElementById('overlay-procesando');
    const marcarTodos = document.getElementById('marcar-todos');
    const casillas = Array.prototype.slice.call(document.querySelectorAll('.casilla-libro'));

    if (!formulario || !boton || !overlay) return;

    let enviando = false;

    if (marcarTodos) {
        marcarTodos.addEventListener('change', function () {
            casillas.forEach(function (casilla) { casilla.checked = marcarTodos.checked; });
        });
    }

    formulario.addEventListener('submit', function (evento) {
        if (enviando) {
            evento.preventDefault();
            return;
        }

        const seleccionados = casillas.filter(function (casilla) { return casilla.checked; });
        if (seleccionados.length === 0) {
            evento.preventDefault();
            window.alert('Selecciona al menos un libro para registrar la devolución.');
            return;
        }

        enviando = true;
        boton.disabled = true;
        overlay.classList.remove('d-none');
    });

    window.addEventListener('pageshow', function () {
        enviando = false;
        boton.disabled = false;
        overlay.classList.add('d-none');
    });
});
