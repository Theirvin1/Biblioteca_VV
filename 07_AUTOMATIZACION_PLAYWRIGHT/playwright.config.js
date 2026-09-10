// Configuracion de la suite E2E de Biblioteca VV.
//
// workers: 1 a proposito. Los casos comparten datos entre si (el libro que
// crea TC-01 es el que prestan TC-06/07, y el estudiante de TC-04 es el que
// va acumulando prestamos hasta el limite), asi que deben ejecutarse en
// orden y en un solo proceso. Con fullyParallel en su valor por defecto
// (false) y un unico worker, Playwright respeta el orden de declaracion.
//
// Las evidencias (reporte HTML y capturas) se escriben FUERA de esta
// carpeta, en 05_EVIDENCIAS_NUEVAS/PLAYWRIGHT/, que es donde el informe
// espera encontrarlas.

const path = require('path');
const { defineConfig } = require('@playwright/test');

const CARPETA_EVIDENCIAS = path.join(__dirname, '..', '05_EVIDENCIAS_NUEVAS', 'PLAYWRIGHT');

module.exports = defineConfig({
  testDir: './playwright-tests',
  workers: 1,
  timeout: 60000,

  use: {
    baseURL: process.env.BASE_URL || 'http://127.0.0.1:5000',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'off',
    // Normalmente se deja vacio y Playwright usa el Chromium que instalo
    // `npx playwright install`. CHROMIUM_PATH solo hace falta en entornos
    // donde el navegador ya viene instalado aparte (por ejemplo un
    // contenedor de integracion continua sin descarga de navegadores).
    launchOptions: process.env.CHROMIUM_PATH
      ? { executablePath: process.env.CHROMIUM_PATH }
      : {},
  },

  outputDir: path.join(CARPETA_EVIDENCIAS, 'resultados'),

  reporter: [
    ['list'],
    ['html', { outputFolder: path.join(CARPETA_EVIDENCIAS, 'reporte-html'), open: 'never' }],
    ['json', { outputFile: path.join(CARPETA_EVIDENCIAS, 'resultado-ejecucion.json') }],
  ],
});
