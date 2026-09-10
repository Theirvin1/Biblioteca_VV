// Ruta de las capturas de evidencia de la suite.
//
// Las capturas ya no se guardan dentro de la carpeta de automatizacion sino
// en 05_EVIDENCIAS_NUEVAS/PLAYWRIGHT/capturas/, junto al reporte HTML, que es
// la carpeta de evidencias nuevas del examen final.

const fs = require('fs');
const path = require('path');

const CARPETA_EVIDENCIAS = path.join(
  __dirname, '..', '..', '..', '05_EVIDENCIAS_NUEVAS', 'PLAYWRIGHT', 'capturas'
);

function rutaEvidencia(nombreArchivo) {
  fs.mkdirSync(CARPETA_EVIDENCIAS, { recursive: true });
  return path.join(CARPETA_EVIDENCIAS, nombreArchivo);
}

module.exports = { rutaEvidencia, CARPETA_EVIDENCIAS };
