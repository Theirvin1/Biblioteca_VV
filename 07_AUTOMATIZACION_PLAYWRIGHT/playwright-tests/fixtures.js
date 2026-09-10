/*
 * Fixture de la suite: `test` y `expect` que se usan en biblioteca.spec.js.
 *
 * Extiende el `test` de Playwright con una sola cosa: la posibilidad de
 * ejecutar la suite en una maquina SIN acceso a internet.
 *
 * Biblioteca VV carga Bootstrap y Chart.js desde jsdelivr. En una maquina
 * con internet no hay nada que hacer y esta fixture no interviene. Pero en
 * un laboratorio sin salida a internet, o en un servidor de integracion
 * continua, esas peticiones fallan y la pagina se queda sin las clases de
 * Bootstrap; entre ellas `d-none`, que es la que mantiene oculto el overlay
 * de "Procesando prestamo...". Sin esa clase el overlay tapa la pantalla y
 * las pruebas fallan por un motivo que no tiene nada que ver con el sistema.
 *
 * Con ASSETS_OFFLINE=1 la suite responde esas dos peticiones con las copias
 * locales de assets-offline/ (las MISMAS versiones que declara la
 * aplicacion: Bootstrap 5.3.3 y Chart.js 4.4.1). No se modifica ningun
 * archivo del proyecto ni el comportamiento de la aplicacion: solo cambia
 * de donde sale un archivo estatico.
 */

const fs = require('fs');
const path = require('path');
const base = require('@playwright/test');

const CARPETA_ASSETS = path.join(__dirname, '..', 'assets-offline');

// Cada patron de URL con el archivo local que lo sustituye y su tipo MIME.
const SUSTITUCIONES = [
  { patron: /bootstrap[^/]*\/dist\/css\/bootstrap\.min\.css/, archivo: 'bootstrap.min.css', tipo: 'text/css' },
  { patron: /bootstrap[^/]*\/dist\/js\/bootstrap\.bundle\.min\.js/, archivo: 'bootstrap.bundle.min.js', tipo: 'application/javascript' },
  { patron: /chart\.js/, archivo: 'chart.umd.js', tipo: 'application/javascript' },
];

async function servirAssetsLocales(page) {
  await page.route('**://cdn.jsdelivr.net/**', async (ruta) => {
    const url = ruta.request().url();
    const sustitucion = SUSTITUCIONES.find((s) => s.patron.test(url));
    const destino = sustitucion && path.join(CARPETA_ASSETS, sustitucion.archivo);

    if (!destino || !fs.existsSync(destino)) return ruta.continue();

    await ruta.fulfill({
      status: 200,
      contentType: sustitucion.tipo,
      body: fs.readFileSync(destino),
    });
  });
}

const test = base.test.extend({
  page: async ({ page }, use) => {
    if (process.env.ASSETS_OFFLINE === '1') await servirAssetsLocales(page);
    await use(page);
  },
});

module.exports = { test, expect: base.expect, servirAssetsLocales };
