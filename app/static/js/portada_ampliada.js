/*
 * Portada -> modal compartido (shared/_modal_portada.html).
 *
 * Un solo modal por pagina: se rellena con los data-* del boton pulsado y se
 * muestra sin recargar (delegacion de eventos sobre document, igual que
 * resumen_libro.js).
 */
document.addEventListener('DOMContentLoaded', function () {
    const modalEl = document.getElementById('modal-portada-libro');
    if (!modalEl || !window.bootstrap) return;

    const modal = new window.bootstrap.Modal(modalEl);
    const elTitulo = document.getElementById('modal-portada-titulo');
    const elImagen = document.getElementById('modal-portada-imagen');

    document.addEventListener('click', function (evento) {
        const boton = evento.target.closest('[data-accion="ver-portada"]');
        if (!boton) return;

        const titulo = boton.dataset.titulo || 'Portada del libro';
        elTitulo.textContent = titulo;
        elImagen.src = boton.dataset.portada || '';
        elImagen.alt = 'Portada de ' + titulo;

        modal.show();
    });
});
