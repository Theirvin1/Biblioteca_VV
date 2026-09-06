document.addEventListener('DOMContentLoaded', function () {
    const inputCedula = document.getElementById('cedula');
    const mensaje = document.getElementById('cedula-mensaje');
    if (!inputCedula || !mensaje) return;

    let temporizador = null;

    inputCedula.addEventListener('input', function () {
        clearTimeout(temporizador);
        mensaje.textContent = '';
        const cedula = inputCedula.value.trim();
        if (cedula.length !== 10) return;

        temporizador = setTimeout(function () {
            fetch('/bibliotecario/api/estudiantes/verificar-cedula?cedula=' + encodeURIComponent(cedula))
                .then(function (resp) { return resp.json(); })
                .then(function (datos) {
                    mensaje.className = datos.existe ? 'small text-danger' : 'small text-success';
                    mensaje.textContent = datos.mensaje;
                });
        }, 300);
    });
});
