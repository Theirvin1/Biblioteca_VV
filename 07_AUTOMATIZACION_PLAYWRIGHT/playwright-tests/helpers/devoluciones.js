// Helpers de la pantalla de devoluciones.
//
// Cambio respecto del Corte II: la devolucion ya no se registra prestamo por
// prestamo con un formulario de un solo estado. El listado muestra
// OPERACIONES (uno o varios libros) y la pantalla de devolucion permite
// marcar con casillas cuales libros vuelven, con su propio estado
// (bueno / dañado / perdido) y su observacion. Devolver una parte de la
// operacion es una devolucion PARCIAL; devolver el resto la completa.

const { expect } = require('@playwright/test');

/** Abre la pantalla de devolucion de la operacion que contiene `codigo`. */
async function abrirOperacion(page, codigo) {
  await page.goto(`/bibliotecario/devoluciones?estado=pendientes&q=${encodeURIComponent(codigo)}`);
  const fila = page.locator('table tbody tr', { hasText: codigo });
  await expect(fila.first()).toBeVisible();
  await fila.first().getByRole('link', { name: 'Registrar devolución' }).click();
  await expect(page.locator('#form-devolucion')).toBeVisible();
}

/**
 * Marca el libro cuyo codigo de prestamo es `codigoPrestamo`, le asigna el
 * estado indicado y registra la devolucion. Devuelve el texto del mensaje.
 */
async function devolverLibro(page, codigoPrestamo, estadoEjemplar = 'bueno', observacion = '') {
  const fila = page.locator('#form-devolucion tbody tr', { hasText: codigoPrestamo });
  await expect(
    fila,
    `no se encontro el prestamo ${codigoPrestamo} entre los libros pendientes de la operacion`
  ).toHaveCount(1);

  const casilla = fila.locator('input.casilla-libro');
  const idPrestamo = await casilla.getAttribute('value');
  await casilla.check();

  await fila.locator(`select[name="estado_${idPrestamo}"]`).selectOption(estadoEjemplar);
  if (observacion) {
    await fila.locator(`input[name="observacion_${idPrestamo}"]`).fill(observacion);
  }

  await page.click('#btn-registrar-devolucion');
  const alerta = page.locator('.alert').first();
  await expect(alerta).toBeVisible();
  return alerta.innerText();
}

/** Lee el estado que el listado muestra para una operacion (badge de estado). */
async function estadoOperacion(page, codigo) {
  await page.goto(`/bibliotecario/devoluciones?estado=todas&q=${encodeURIComponent(codigo)}`);
  const fila = page.locator('table tbody tr', { hasText: codigo }).first();
  await expect(fila).toBeVisible();
  return (await fila.locator('td .badge').first().innerText()).trim();
}

module.exports = { abrirOperacion, devolverLibro, estadoOperacion };
