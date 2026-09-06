/*
 * Auto-ocultado de los mensajes flash. Compartido por TODAS las pantallas:
 * se carga una sola vez desde shared/base.html.
 *
 * Solo se cierran solos los que la plantilla marca con data-auto-cerrar
 * (success e info). Los de warning/danger se quedan hasta que el usuario
 * pulse la X, para que no se pierda un aviso o un error.
 */
document.addEventListener('DOMContentLoaded', function () {
    const alertas = document.querySelectorAll('.alert[data-auto-cerrar]');

    alertas.forEach(function (alerta) {
        const espera = parseInt(alerta.getAttribute('data-auto-cerrar'), 10);
        if (!espera || espera < 0) return;

        setTimeout(function () {
            // Bootstrap se encarga del desvanecido (clases fade/show).
            if (window.bootstrap && window.bootstrap.Alert) {
                window.bootstrap.Alert.getOrCreateInstance(alerta).close();
            } else {
                alerta.remove();
            }
        }, espera);
    });
});
