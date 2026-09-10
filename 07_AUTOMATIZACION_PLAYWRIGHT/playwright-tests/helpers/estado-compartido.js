// Persistencia de datos compartidos entre los 10 TC de biblioteca.spec.js
// en un archivo, para sobrevivir a un comportamiento real de Playwright
// Test: cuando un test FALLA, Playwright descarta el worker (proceso)
// donde corrió y arranca uno NUEVO para los tests restantes del mismo
// archivo. Ese nuevo worker vuelve a cargar el módulo del spec desde
// cero, así que cualquier valor "aleatorio" calculado en el top-level
// del archivo (ISBN, cédula, etc.) se recalcula con valores DISTINTOS,
// aunque la base de datos ya tenga los registros creados por el worker
// anterior con los valores originales.
//
// Por eso el ISBN/cédula/contraseña temporal/código de préstamo ya no
// viven solo en el objeto `datos` en memoria: se guardan también aquí,
// y cada test los relee al empezar (ver biblioteca.spec.js, beforeEach),
// de forma que un worker nuevo recupere los valores REALES ya usados
// contra la base de datos en lugar de los que él mismo acaba de generar.

const fs = require('fs');
const path = require('path');

const RUTA_ESTADO = path.join(__dirname, '..', '.estado-suite.json');

function leerEstado() {
  try {
    const contenido = fs.readFileSync(RUTA_ESTADO, 'utf-8');
    return JSON.parse(contenido);
  } catch (error) {
    return null; // no existe todavía, o quedó corrupto: se trata como "no hay estado previo"
  }
}

function guardarEstado(datos) {
  fs.writeFileSync(RUTA_ESTADO, JSON.stringify(datos, null, 2), 'utf-8');
}

module.exports = { leerEstado, guardarEstado, RUTA_ESTADO };
