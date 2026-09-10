// Lectura del inventario tal como lo ve el bibliotecario en la UI.
//
// Cambio respecto de la version anterior de la suite: el listado de libros
// ahora PAGINA en el servidor (10 libros por pagina, app/paginacion.py), asi
// que ya no basta con abrir /bibliotecario/libros y buscar la fila; un libro
// registrado hace varias corridas puede estar en la pagina 7. Se usa el
// buscador del propio listado (?q=<isbn>), que es tambien lo que haria una
// persona. Ademas, el <tbody> ya no lleva id y la ultima celda de la fila es
// el boton "Ver resumen", no el stock: el stock es la 6a columna.

const { expect } = require('@playwright/test');

const COLUMNA_STOCK = 6;

/**
 * Devuelve { disponible, total } del libro con ese ISBN, leido de la tabla
 * de /bibliotecario/libros (columna "Stock", con formato "disponible / total").
 */
async function leerStockLibro(page, isbn) {
  await page.goto(`/bibliotecario/libros?q=${encodeURIComponent(isbn)}`);

  const fila = page.locator('table tbody tr', { hasText: isbn });
  await expect(
    fila,
    `no se encontro en /bibliotecario/libros una fila con el ISBN ${isbn}; ` +
    'revisa si ese libro realmente se registro en esta ejecucion'
  ).toHaveCount(1);

  const texto = await fila.locator(`td:nth-child(${COLUMNA_STOCK})`).innerText();
  const [disponible, total] = texto.split('/').map((parte) => parseInt(parte.trim(), 10));
  return { disponible, total };
}

module.exports = { leerStockLibro, COLUMNA_STOCK };
