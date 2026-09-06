/*
 * Boton "Ver resumen" -> modal compartido (shared/_modal_resumen.html).
 *
 * Un solo modal por pagina: se rellena con los data-* del boton pulsado y se
 * muestra sin recargar. Funciona con botones renderizados en el HTML inicial
 * y con los que agrega el catalogo del estudiante via AJAX (delegacion de
 * eventos sobre document, no hace falta re-enlazar nada).
 */
document.addEventListener('DOMContentLoaded', function () {
    const modalEl = document.getElementById('modal-resumen-libro');
    if (!modalEl || !window.bootstrap) return;

    const modal = new window.bootstrap.Modal(modalEl);
    const elTitulo = document.getElementById('modal-resumen-titulo');
    const elPortada = document.getElementById('modal-resumen-portada');
    const elAutores = document.getElementById('modal-resumen-autores');
    const elTexto = document.getElementById('modal-resumen-texto');

    document.addEventListener('click', function (evento) {
        const boton = evento.target.closest('[data-accion="ver-resumen"]');
        if (!boton) return;

        const resumen = (boton.dataset.resumen || '').trim();

        elTitulo.textContent = boton.dataset.titulo || 'Resumen del libro';
        elPortada.src = boton.dataset.portada || '';
        elPortada.alt = 'Portada de ' + (boton.dataset.titulo || '');
        elAutores.textContent = boton.dataset.autores || '';
        elTexto.textContent = resumen || 'No hay un resumen disponible para este libro.';
        elTexto.classList.toggle('text-muted', !resumen);
        elTexto.classList.toggle('fst-italic', !resumen);

        modal.show();
    });
});
