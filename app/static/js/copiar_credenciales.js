/*
 * Boton "Copiar credenciales", compartido por la pantalla de registro de
 * estudiante y por la de restablecimiento de contraseña del gerente.
 *
 * El texto a copiar viaja en data-* del propio boton: la clave temporal solo
 * existe en el HTML de esta respuesta, nunca se pide de vuelta al servidor.
 */
document.addEventListener('DOMContentLoaded', function () {
    /*
     * Evita el reenvio del POST: la pantalla llega como respuesta de un POST,
     * asi que se sustituye esa entrada del historial por una URL GET segura.
     * Un F5 posterior recarga esa URL (listado de estudiantes o gestion de
     * usuarios) en vez de repetir el POST, que generaria otra clave temporal.
     * La contraseña ya esta pintada en el DOM: reemplazar la URL no la borra
     * ni la vuelve a pedir al servidor.
     */
    const contenedor = document.querySelector('[data-credenciales]');
    if (contenedor && window.history && window.history.replaceState) {
        const urlSegura = contenedor.dataset.urlSegura;
        if (urlSegura) {
            try {
                window.history.replaceState(null, '', urlSegura);
            } catch (error) {
                /* Si el navegador lo impide, la pantalla sigue siendo usable. */
            }
        }
    }

    const boton = document.querySelector('[data-accion="copiar-credenciales"]');
    if (!boton) return;

    const aviso = document.getElementById('aviso-copiado');

    function confirmar(mensaje, exito) {
        if (!aviso) return;
        aviso.textContent = mensaje;
        aviso.classList.remove('d-none', 'text-success', 'text-danger');
        aviso.classList.add(exito ? 'text-success' : 'text-danger');
        setTimeout(function () { aviso.classList.add('d-none'); }, 3000);
    }

    function copiarConFallback(texto) {
        // Sin navigator.clipboard (http sin localhost, navegadores viejos):
        // textarea temporal + execCommand, sin librerias externas.
        const area = document.createElement('textarea');
        area.value = texto;
        area.setAttribute('readonly', '');
        area.style.position = 'fixed';
        area.style.opacity = '0';
        document.body.appendChild(area);
        area.select();
        let copiado = false;
        try {
            copiado = document.execCommand('copy');
        } catch (error) {
            copiado = false;
        }
        document.body.removeChild(area);
        return copiado;
    }

    boton.addEventListener('click', function () {
        const texto = 'Usuario: ' + (boton.dataset.usuario || '') +
            '\nContraseña temporal: ' + (boton.dataset.password || '');

        function intentarFallback() {
            const copiado = copiarConFallback(texto);
            confirmar(copiado ? 'Credenciales copiadas' : 'No se pudo copiar. Cópialas a mano.', copiado);
        }

        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(texto).then(
                function () { confirmar('Credenciales copiadas', true); },
                intentarFallback
            );
            return;
        }

        intentarFallback();
    });
});
