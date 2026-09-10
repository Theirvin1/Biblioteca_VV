/*
 * Utilidad de apoyo (NO es parte de la suite de pruebas).
 *
 * Recorre las pantallas principales del sistema con un navegador real y
 * guarda una captura de cada una en
 * 05_EVIDENCIAS_NUEVAS/CAPTURAS_SISTEMA_FINAL/. Sirve para tener evidencia
 * actualizada de la interfaz final para el informe y la presentacion, sin
 * tener que recorrer el sistema a mano.
 *
 * Uso (con la aplicacion levantada en http://127.0.0.1:5000):
 *   node scripts/capturas-sistema.js
 *
 * Variables opcionales:
 *   BASE_URL        direccion de la aplicacion (por defecto 127.0.0.1:5000)
 *   CEDULA_DEMO     cedula de un estudiante existente, para las pantallas
 *                   que muestran la tarjeta del estudiante
 *   ISBN_DEMO       ISBN de un libro existente con stock disponible
 */

const fs = require('fs');
const path = require('path');
const { chromium } = require('@playwright/test');
const { servirAssetsLocales } = require('../playwright-tests/fixtures');

const BASE = process.env.BASE_URL || 'http://127.0.0.1:5000';
const DESTINO = path.join(__dirname, '..', '..', '05_EVIDENCIAS_NUEVAS', 'CAPTURAS_SISTEMA_FINAL');

const CREDENCIALES = {
  bibliotecario: ['bibliotecario', 'Biblio'],
  gerente: ['gerente', 'Gerente'],
  estudiante: ['estudiante', 'Estudiante'],
};

async function login(page, rol) {
  const [usuario, clave] = CREDENCIALES[rol];
  await page.goto(`${BASE}/logout`);
  await page.goto(`${BASE}/login`);
  await page.fill('#username', usuario);
  await page.fill('#password', clave);
  await page.click('input[type=submit]');
  await page.waitForLoadState('networkidle').catch(() => {});
}

async function capturar(page, ruta, nombre, preparar) {
  await page.goto(`${BASE}${ruta}`);
  if (preparar) await preparar(page);
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(DESTINO, `${nombre}.png`), fullPage: true });
  console.log('capturada:', nombre);
}

(async () => {
  fs.mkdirSync(DESTINO, { recursive: true });
  const navegador = await chromium.launch(
    process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {}
  );
  const contexto = await navegador.newContext({ viewport: { width: 1366, height: 900 } });
  const page = await contexto.newPage();
  if (process.env.ASSETS_OFFLINE === '1') await servirAssetsLocales(page);

  await page.goto(`${BASE}/login`);
  await page.screenshot({ path: path.join(DESTINO, 'SIS-01-login.png'), fullPage: true });

  // ---------------- Bibliotecario
  await login(page, 'bibliotecario');
  await capturar(page, '/bibliotecario', 'SIS-02-bibliotecario-inicio');
  await capturar(page, '/bibliotecario/libros', 'SIS-03-libros-listado');
  await capturar(page, '/bibliotecario/libros/nuevo', 'SIS-04-libros-formulario');
  await capturar(page, '/bibliotecario/estudiantes', 'SIS-05-estudiantes-listado');
  await capturar(page, '/bibliotecario/estudiantes/nuevo', 'SIS-06-estudiantes-formulario');

  await capturar(page, '/bibliotecario/prestamos/nuevo', 'SIS-07-prestamo-tarjetas', async (p) => {
    if (!process.env.CEDULA_DEMO) return;
    await p.fill('#cedula', process.env.CEDULA_DEMO);
    await p.waitForTimeout(900);
    if (process.env.ISBN_DEMO) {
      await p.fill('#isbn', process.env.ISBN_DEMO);
      await p.waitForTimeout(900);
    }
  });

  await capturar(page, '/bibliotecario/prestamos?estado=todas', 'SIS-08-prestamos-operaciones');
  await capturar(page, '/bibliotecario/devoluciones?estado=todas', 'SIS-09-devoluciones-listado');

  // Primera operacion con libros pendientes, si existe.
  await page.goto(`${BASE}/bibliotecario/devoluciones?estado=pendientes`);
  const enlace = page.getByRole('link', { name: 'Registrar devolución' }).first();
  if (await enlace.count()) {
    await enlace.click();
    await page.waitForTimeout(400);
    await page.screenshot({
      path: path.join(DESTINO, 'SIS-10-devolucion-seleccion-libros.png'), fullPage: true,
    });
    console.log('capturada: SIS-10-devolucion-seleccion-libros');
  }

  // ---------------- Estudiante
  await login(page, 'estudiante');
  await capturar(page, '/estudiante/catalogo', 'SIS-11-catalogo-estudiante');
  await capturar(page, '/estudiante/prestamos', 'SIS-12-mis-prestamos');
  await capturar(page, '/estudiante/perfil', 'SIS-13-perfil-estudiante');

  // ---------------- Gerente
  await login(page, 'gerente');
  await capturar(page, '/gerente/dashboard', 'SIS-14-gerente-dashboard');
  await capturar(page, '/gerente/reportes', 'SIS-15-gerente-reportes');
  await capturar(page, '/gerente/reportes/inventario-actual', 'SIS-16-reporte-inventario');
  await capturar(page, '/gerente/reportes/historial-movimientos', 'SIS-17-reporte-historial');
  await capturar(page, '/gerente/usuarios', 'SIS-18-gestion-usuarios');

  await navegador.close();
  console.log('\nCapturas guardadas en', DESTINO);
})();
