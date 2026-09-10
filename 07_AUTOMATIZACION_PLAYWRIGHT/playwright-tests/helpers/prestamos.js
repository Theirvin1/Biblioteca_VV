// Helpers del formulario de prestamo con varios libros.
//
// La pantalla de "Registrar prestamo" cambio por completo despues del Corte II:
// ya no es un formulario de cedula + ISBN que se envia de una vez, sino un
// armador de operacion. El bibliotecario escribe la cedula (se consulta
// /bibliotecario/api/prestamos/estudiante y se pinta la tarjeta del
// estudiante con sus cupos), escribe un ISBN (se consulta
// /bibliotecario/api/prestamos/libro y se pinta la tarjeta del libro), pulsa
// "+ Agregar al prestamo" por cada libro y recien entonces envia.
//
// Estos helpers reproducen ese flujo real; no envian el formulario por
// atajos ni escriben directamente el campo oculto "isbns".

const { expect } = require('@playwright/test');

const RUTA_NUEVO_PRESTAMO = '/bibliotecario/prestamos/nuevo';

/** Escribe la cedula y espera la respuesta de la tarjeta del estudiante. */
async function buscarEstudiante(page, cedula) {
  const respuesta = page.waitForResponse((r) =>
    r.url().includes('/bibliotecario/api/prestamos/estudiante')
  );
  await page.fill('#cedula', cedula);
  const datos = await (await respuesta).json();
  await expect(page.locator('#tarjeta-estudiante')).toBeVisible();
  return datos;
}

/** Escribe el ISBN y espera la respuesta de la tarjeta del libro. */
async function buscarLibro(page, isbn) {
  const respuesta = page.waitForResponse((r) =>
    r.url().includes('/bibliotecario/api/prestamos/libro')
  );
  await page.fill('#isbn', isbn);
  const datos = await (await respuesta).json();
  await expect(page.locator('#tarjeta-libro')).toBeVisible();
  return datos;
}

/** Pulsa "+ Agregar al prestamo" y comprueba que el libro entro a la lista. */
async function agregarLibroSeleccionado(page, isbn) {
  await expect(page.locator('#btn-agregar-libro')).toBeEnabled();
  await page.click('#btn-agregar-libro');
  await expect(page.locator('#tabla-seleccionados tbody tr', { hasText: isbn })).toHaveCount(1);
}

/**
 * Registra una operacion de prestamo completa para `cedula` con la lista de
 * `isbns` indicada, siguiendo el flujo de pantalla. Devuelve el texto del
 * mensaje de resultado.
 */
async function registrarPrestamo(page, cedula, isbns) {
  await page.goto(RUTA_NUEVO_PRESTAMO);
  await buscarEstudiante(page, cedula);

  for (const isbn of isbns) {
    await buscarLibro(page, isbn);
    await agregarLibroSeleccionado(page, isbn);
  }

  await page.click('#btn-registrar-prestamo');
  const alerta = page.locator('.alert').first();
  await expect(alerta).toBeVisible();
  return alerta.innerText();
}

/** Extrae el codigo de operacion de grupo (GRP-YYYY-NNNN) de un mensaje. */
function extraerCodigoOperacion(texto) {
  const coincidencia = texto.match(/GRP-\d{4}-\d{4}/);
  return coincidencia ? coincidencia[0] : null;
}

/** Extrae un codigo de prestamo individual (P-YYYY-NNNN) de un texto. */
function extraerCodigoPrestamo(texto) {
  const coincidencia = texto.match(/P-\d{4}-\d{4}/);
  return coincidencia ? coincidencia[0] : null;
}

module.exports = {
  RUTA_NUEVO_PRESTAMO,
  buscarEstudiante,
  buscarLibro,
  agregarLibroSeleccionado,
  registrarPrestamo,
  extraerCodigoOperacion,
  extraerCodigoPrestamo,
};
