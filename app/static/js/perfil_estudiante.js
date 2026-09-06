/*
 * Mi perfil (estudiante) - modal "Editar telefono".
 *
 * El modal se abre normalmente con el boton (data-bs-toggle="modal"). Este
 * script solo cubre el caso en que el servidor rechazo el envio (telefono
 * invalido): la plantilla marca data-abrir="1" en esa respuesta para que el
 * modal se reabra solo, mostrando el error, en vez de perderse en la
 * pantalla completa que se vuelve a renderizar.
 */
document.addEventListener('DOMContentLoaded', function () {
    const modal = document.getElementById('modal-editar-telefono');
    if (!modal || !window.bootstrap) return;

    if (modal.dataset.abrir === '1') {
        new window.bootstrap.Modal(modal).show();
    }
});
