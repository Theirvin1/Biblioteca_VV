/*
 * Biblioteca VV — Suite E2E final (15 casos).
 *
 * Esta suite reemplaza a la de diez casos del Corte II. El motivo no es
 * cosmetico: despues de esa entrega cambiaron el registro de prestamos
 * (ahora se pueden prestar varios libros en una sola operacion, armando la
 * lista en pantalla), las devoluciones (ahora son por operacion y admiten
 * devolucion parcial, con estado por libro) y los listados (ahora paginan y
 * filtran en el servidor). Varios de los casos anteriores dejaron de
 * corresponder a la pantalla real; la trazabilidad de cada uno con su
 * antecesor esta documentada en el informe final.
 *
 * Orden y datos compartidos: los casos se ejecutan en el orden en que estan
 * declarados, con un solo worker (playwright.config.js). El libro que crea
 * TC-01 es el que se presta despues, y el estudiante que crea TC-05 es el
 * que va acumulando prestamos hasta el limite. Los valores compartidos se
 * persisten en .estado-suite.json para sobrevivir al reinicio de worker que
 * Playwright hace tras un fallo.
 *
 * El inicio de sesion NO es uno de los casos: es una precondicion
 * reutilizable (helpers/sesion.js).
 */

const fs = require('fs');
const path = require('path');
const { test, expect } = require('./fixtures');

const {
  generarCedulaValida,
  generarIsbnValido,
  generarIsbnConChecksumInvalido,
} = require('./helpers/generadores');
const { iniciarSesion, CREDENCIALES_SEED } = require('./helpers/sesion');
const { leerStockLibro } = require('./helpers/inventario');
const { rutaEvidencia } = require('./helpers/evidencias');
const { leerEstado, guardarEstado } = require('./helpers/estado-compartido');
const {
  RUTA_NUEVO_PRESTAMO, buscarEstudiante, buscarLibro, registrarPrestamo,
  extraerCodigoOperacion,
} = require('./helpers/prestamos');
const { abrirOperacion, devolverLibro, estadoOperacion } = require('./helpers/devoluciones');

// ---------------------------------------------------------------------
// Datos de prueba de esta ejecucion. La cedula y el ISBN se generan validos
// (mismo algoritmo de digito verificador que app/validators.py) y distintos
// en cada corrida, para que la suite se pueda repetir sin chocar con los
// registros que dejo la anterior.
// ---------------------------------------------------------------------
const sufijo = Date.now();

const datos = {
  // Libro principal (TC-01): 5 ejemplares. Se presta y se devuelve varias veces.
  isbnPrincipal: generarIsbnValido(),
  tituloPrincipal: `Verificacion de Software ${sufijo}`,
  editorialPrincipal: `Editorial VV ${sufijo}`,
  stockPrincipal: 5,

  // Libro secundario (TC-04): 2 ejemplares, con portada y resumen.
  isbnSecundario: generarIsbnValido(),
  tituloSecundario: `Pruebas Automatizadas ${sufijo}`,
  editorialSecundario: `Editorial Complementaria ${sufijo}`,
  stockSecundario: 2,
  resumenSecundario: `Resumen de prueba generado por la suite E2E (${sufijo}).`,

  // ISBN con formato correcto y digito verificador incorrecto (TC-03).
  isbnInvalido: generarIsbnConChecksumInvalido(),

  // Estudiante principal (TC-05): sujeto del limite de prestamos activos.
  cedulaPrincipal: generarCedulaValida(),
  correoPrincipal: `principal.${sufijo}@uteq.edu.ec`,
  passwordTemporal: null,
  passwordVigente: null,

  // Estudiante secundario (TC-14): solo para la devolucion en mal estado.
  cedulaSecundario: generarCedulaValida(),
  correoSecundario: `secundario.${sufijo}@uteq.edu.ec`,

  // Codigos capturados durante la ejecucion.
  codigoOperacionMultiple: null,
  codigoPrestamoIndividual: null,
  codigosOperacionMultiple: [],
  codigoPrestamoDanado: null,
};

const PLAZO_DIAS = 7;          // configuracion_sistema.plazo_prestamo_dias
const MAX_PRESTAMOS = 3;       // configuracion_sistema.max_prestamos_activos

/** PNG minimo valido (1x1), para probar la subida de portada sin archivos externos. */
const PNG_1X1 = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64'
);

/** Crea un autor nuevo desde el propio formulario de libros (flujo AJAX). */
async function agregarAutorNuevo(page, nombres, apellidos) {
  await page.fill('#nuevo-autor-nombres', nombres);
  await page.fill('#nuevo-autor-apellidos', apellidos);
  await page.click('#btn-crear-autor');
  await expect(page.locator('#autores-seleccionados')).toContainText(nombres);
}

/** Registra un estudiante y devuelve la contraseña temporal que muestra el sistema. */
async function registrarEstudiante(page, { cedula, nombres, apellidos, correo }) {
  await page.goto('/bibliotecario/estudiantes/nuevo');
  await page.fill('#cedula', cedula);
  await page.fill('#nombres', nombres);
  await page.fill('#apellidos', apellidos);
  await page.fill('#correo', correo);
  await page.selectOption('#carrera_id', { index: 1 });
  await page.fill('#fecha_nacimiento', '2003-05-15');
  await page.click('input[type=submit]');

  // El sistema ya no devuelve la clave en un mensaje flash: renderiza una
  // pantalla de credenciales que la muestra una sola vez.
  await expect(page.locator('h2')).toContainText('Estudiante registrado');
  return (await page.locator('code.credencial-temporal').innerText()).trim();
}

test.describe('Biblioteca VV — Suite E2E final', () => {

  test.beforeEach(async ({}, testInfo) => {
    if (testInfo.title.startsWith('TC-01 ')) {
      guardarEstado(datos);
      return;
    }
    const persistido = leerEstado();
    if (persistido) Object.assign(datos, persistido);
    else guardarEstado(datos);
  });

  // ===================================================================
  // HU-02 · Gestión de libros
  // ===================================================================

  test('TC-01 Registrar un libro nuevo creando su autor sin salir del formulario', async ({ page }) => {
    await iniciarSesion(page, CREDENCIALES_SEED.bibliotecario);

    await page.goto('/bibliotecario/libros/nuevo');
    await page.fill('#isbn', datos.isbnPrincipal);
    await page.fill('#titulo', datos.tituloPrincipal);
    await page.fill('#editorial_nombre', datos.editorialPrincipal);
    await page.selectOption('#categoria_id', { index: 1 });
    await page.fill('#stock_inicial', String(datos.stockPrincipal));
    await agregarAutorNuevo(page, 'Autor', 'Principal');

    await page.click('input[type=submit]');

    const alerta = page.locator('.alert').first();
    await expect(alerta).toContainText('registrado con');
    await expect(alerta).toContainText(`${datos.stockPrincipal} ejemplar`);

    // El stock debe quedar completo: se crea un ejemplar por unidad.
    const { disponible, total } = await leerStockLibro(page, datos.isbnPrincipal);
    expect(disponible).toBe(datos.stockPrincipal);
    expect(total).toBe(datos.stockPrincipal);

    await page.screenshot({ path: rutaEvidencia('TC-01-registrar-libro-autor-ajax.png'), fullPage: true });
  });

  test('TC-02 Rechazar un segundo libro con el mismo ISBN', async ({ page }) => {
    await iniciarSesion(page, CREDENCIALES_SEED.bibliotecario);

    await page.goto('/bibliotecario/libros/nuevo');
    await page.fill('#isbn', datos.isbnPrincipal);
    await page.fill('#titulo', `Libro Duplicado ${sufijo}`);
    await page.fill('#editorial_nombre', `Editorial Duplicada ${sufijo}`);
    await page.selectOption('#categoria_id', { index: 1 });
    await page.fill('#stock_inicial', '1');
    await agregarAutorNuevo(page, 'Autor', 'Duplicado');

    await page.click('input[type=submit]');

    await expect(page.locator('.alert').first())
      .toContainText('Ya existe un libro registrado con ese ISBN');

    await page.screenshot({ path: rutaEvidencia('TC-02-isbn-duplicado.png'), fullPage: true });
  });

  test('TC-03 Rechazar un ISBN-13 con dígito verificador incorrecto', async ({ page }) => {
    await iniciarSesion(page, CREDENCIALES_SEED.bibliotecario);

    await page.goto('/bibliotecario/libros/nuevo');
    await page.fill('#isbn', datos.isbnInvalido);
    await page.fill('#titulo', `Libro ISBN Invalido ${sufijo}`);
    await page.fill('#editorial_nombre', `Editorial Invalida ${sufijo}`);
    await page.selectOption('#categoria_id', { index: 1 });
    await page.fill('#stock_inicial', '1');
    // El formulario tambien exige al menos un autor del lado del navegador:
    // se agrega para que este caso pruebe unicamente la regla del ISBN.
    await agregarAutorNuevo(page, 'Autor', 'IsbnInvalido');

    await page.click('input[type=submit]');

    await expect(page.locator('body')).toContainText('El ISBN ingresado no es válido');

    await page.screenshot({ path: rutaEvidencia('TC-03-isbn-checksum-invalido.png'), fullPage: true });
  });

  test('TC-04 Registrar un libro con portada y resumen, y verlo en el catálogo del estudiante', async ({ page }) => {
    await iniciarSesion(page, CREDENCIALES_SEED.bibliotecario);

    await page.goto('/bibliotecario/libros/nuevo');
    await page.fill('#isbn', datos.isbnSecundario);
    await page.fill('#titulo', datos.tituloSecundario);
    await page.fill('#editorial_nombre', datos.editorialSecundario);
    await page.selectOption('#categoria_id', { index: 1 });
    await page.fill('#stock_inicial', String(datos.stockSecundario));
    await page.fill('#resumen', datos.resumenSecundario);
    await page.setInputFiles('#portada', {
      name: 'portada-prueba.png', mimeType: 'image/png', buffer: PNG_1X1,
    });
    await agregarAutorNuevo(page, 'Autora', 'Secundaria');

    await page.click('input[type=submit]');
    await expect(page.locator('.alert').first()).toContainText('registrado con');

    // La portada guardada debe llegar hasta el catalogo del estudiante, no
    // el placeholder por defecto. El catalogo pagina y filtra en el servidor
    // (formulario GET con boton Buscar), asi que se busca por titulo y se
    // verifica sobre la tarjeta renderizada.
    await iniciarSesion(page, CREDENCIALES_SEED.estudianteDemo);
    await page.goto('/estudiante/catalogo');
    await page.fill('#buscador-catalogo', datos.tituloSecundario);
    await page.click('button[type=submit]');
    const tarjeta = page.locator('#contenedor-libros .card', { hasText: datos.tituloSecundario });
    await expect(
      tarjeta,
      'el libro registrado debe aparecer en el catálogo del estudiante'
    ).toBeVisible();
    await expect(tarjeta).toContainText(`${datos.stockSecundario} disponible(s)`);
    await expect(tarjeta.locator('img')).toHaveAttribute('src', /\/uploads\/portadas\//);
    await expect(tarjeta.locator('[data-accion="ver-resumen"]'))
      .toHaveAttribute('data-resumen', /Resumen de prueba/);

    await page.screenshot({ path: rutaEvidencia('TC-04-libro-portada-resumen-catalogo.png'), fullPage: true });
  });

  // ===================================================================
  // HU-01 · Gestión de estudiantes
  // ===================================================================

  test('TC-05 Registrar un estudiante con cédula válida y entregar sus credenciales', async ({ page }) => {
    await iniciarSesion(page, CREDENCIALES_SEED.bibliotecario);

    const temporal = await registrarEstudiante(page, {
      cedula: datos.cedulaPrincipal,
      nombres: 'Estudiante',
      apellidos: 'Principal',
      correo: datos.correoPrincipal,
    });

    expect(temporal.length).toBeGreaterThanOrEqual(8);
    datos.passwordTemporal = temporal;
    datos.passwordVigente = temporal;
    guardarEstado(datos);

    await page.screenshot({ path: rutaEvidencia('TC-05-estudiante-registrado-credenciales.png'), fullPage: true });

    // El estudiante debe quedar disponible de inmediato en el listado.
    await page.goto(`/bibliotecario/estudiantes?q=${datos.cedulaPrincipal}`);
    await expect(page.locator('table tbody tr', { hasText: datos.cedulaPrincipal })).toHaveCount(1);
  });

  test('TC-06 Detectar una cédula duplicada mientras se escribe y al enviar el formulario', async ({ page }) => {
    await iniciarSesion(page, CREDENCIALES_SEED.bibliotecario);
    await page.goto('/bibliotecario/estudiantes/nuevo');

    const respuesta = page.waitForResponse((r) =>
      r.url().includes('/bibliotecario/api/estudiantes/verificar-cedula')
    );
    await page.fill('#cedula', datos.cedulaPrincipal);
    const json = await (await respuesta).json();

    expect(json.existe).toBe(true);
    await expect(page.locator('#cedula-mensaje')).toHaveText(/Ya existe un estudiante registrado/);
    await expect(page.locator('#cedula-mensaje')).toHaveClass(/text-danger/);

    await page.screenshot({ path: rutaEvidencia('TC-06-cedula-duplicada-aviso.png'), fullPage: true });

    // El servidor debe rechazarla igual si se envia el formulario de todos modos.
    await page.fill('#nombres', 'Estudiante');
    await page.fill('#apellidos', 'Duplicado');
    await page.fill('#correo', `duplicado.${sufijo}@uteq.edu.ec`);
    await page.selectOption('#carrera_id', { index: 1 });
    await page.fill('#fecha_nacimiento', '2003-05-15');
    await page.click('input[type=submit]');

    await expect(page.locator('.alert').first())
      .toContainText('Ya existe un estudiante registrado con esa cédula');
  });

  // ===================================================================
  // HU-03 · Registro de préstamos
  // ===================================================================

  test('TC-07 Registrar el préstamo de un libro y comprobar que el stock baja en uno', async ({ page }) => {
    await iniciarSesion(page, CREDENCIALES_SEED.bibliotecario);

    const { disponible: antes } = await leerStockLibro(page, datos.isbnPrincipal);
    expect(antes).toBe(datos.stockPrincipal);

    const mensaje = await registrarPrestamo(page, datos.cedulaPrincipal, [datos.isbnPrincipal]);
    expect(mensaje).toContain('Préstamo registrado correctamente');
    expect(mensaje).toContain(datos.tituloPrincipal);

    const { disponible: despues, total } = await leerStockLibro(page, datos.isbnPrincipal);
    expect(despues).toBe(antes - 1);
    expect(total).toBe(datos.stockPrincipal);

    await page.screenshot({ path: rutaEvidencia('TC-07-prestamo-individual-stock.png'), fullPage: true });
  });

  test('TC-08 Registrar un préstamo de dos libros en una sola operación', async ({ page }) => {
    await iniciarSesion(page, CREDENCIALES_SEED.bibliotecario);

    const principalAntes = (await leerStockLibro(page, datos.isbnPrincipal)).disponible;
    const secundarioAntes = (await leerStockLibro(page, datos.isbnSecundario)).disponible;

    const mensaje = await registrarPrestamo(
      page, datos.cedulaPrincipal, [datos.isbnPrincipal, datos.isbnSecundario]
    );
    expect(mensaje).toContain('Operación');
    expect(mensaje).toContain('2 libro(s)');

    const codigo = extraerCodigoOperacion(mensaje);
    expect(codigo, 'la operación de varios libros debe recibir un código GRP-AAAA-NNNN').not.toBeNull();
    datos.codigoOperacionMultiple = codigo;
    guardarEstado(datos);

    // Cada libro descuenta su propio ejemplar.
    expect((await leerStockLibro(page, datos.isbnPrincipal)).disponible).toBe(principalAntes - 1);
    expect((await leerStockLibro(page, datos.isbnSecundario)).disponible).toBe(secundarioAntes - 1);

    // La operación se muestra como UNA fila con dos libros, no como dos filas.
    await page.goto(`/bibliotecario/prestamos?estado=pendientes&q=${codigo}`);
    const fila = page.locator('table tbody tr', { hasText: codigo });
    await expect(fila).toHaveCount(1);
    await expect(fila).toContainText('2');

    await page.screenshot({ path: rutaEvidencia('TC-08-prestamo-multiple-operacion.png'), fullPage: true });
  });

  test('TC-09 Advertir que el estudiante llegó al máximo de préstamos activos', async ({ page }) => {
    await iniciarSesion(page, CREDENCIALES_SEED.bibliotecario);

    // Precondición comprobada, no supuesta: el estudiante debe tener
    // exactamente 3 préstamos activos y el libro todavía debe tener stock.
    const { disponible } = await leerStockLibro(page, datos.isbnPrincipal);
    expect(disponible, 'el libro principal debe seguir teniendo ejemplares disponibles').toBeGreaterThan(0);

    await page.goto(RUTA_NUEVO_PRESTAMO);
    const estudiante = await buscarEstudiante(page, datos.cedulaPrincipal);

    expect(estudiante.prestamos_activos).toBe(MAX_PRESTAMOS);
    expect(estudiante.max_prestamos).toBe(MAX_PRESTAMOS);
    expect(estudiante.cupos_disponibles).toBe(0);
    expect(
      estudiante.ok,
      'sin cupos disponibles, la tarjeta del estudiante no debe darse por válida'
    ).toBe(false);
    expect(estudiante.mensaje).toMatch(/máximo/i);

    await expect(page.locator('#tarjeta-estudiante')).toContainText(/máximo/i);

    // Aunque el libro exista y tenga stock, no se puede agregar al préstamo.
    await buscarLibro(page, datos.isbnPrincipal);
    await expect(page.locator('#btn-agregar-libro')).toBeDisabled();

    await page.screenshot({ path: rutaEvidencia('TC-09-limite-prestamos-activos.png'), fullPage: true });
  });

  test('TC-10 El servidor rechaza el préstamo aunque se envíe el formulario sin pasar por la pantalla', async ({ page }) => {
    await iniciarSesion(page, CREDENCIALES_SEED.bibliotecario);

    // Se envía el formulario directamente, saltándose las comprobaciones que
    // hace el navegador. La regla del máximo de préstamos activos debe
    // aplicarse igual, porque vive en el servidor y no en la pantalla.
    await page.goto(RUTA_NUEVO_PRESTAMO);
    const csrf = await page.locator('input[name=csrf_token]').first().inputValue();

    const respuesta = await page.request.post(RUTA_NUEVO_PRESTAMO, {
      form: {
        csrf_token: csrf,
        cedula: datos.cedulaPrincipal,
        isbns: datos.isbnPrincipal,
        observaciones: 'Envío directo del formulario (prueba de validación en servidor)',
        submit: 'Registrar préstamo',
      },
    });

    expect(respuesta.status()).toBe(200);
    const html = await respuesta.text();
    expect(html).toMatch(/máximo de 3 préstamos activos|no dispone|cupo/i);

    // Y el estudiante debe seguir con exactamente 3 préstamos, no 4.
    const tarjeta = await page.request.get(
      `/bibliotecario/api/prestamos/estudiante?cedula=${datos.cedulaPrincipal}`
    );
    const json = await tarjeta.json();
    expect(json.prestamos_activos).toBe(MAX_PRESTAMOS);
  });

  // ===================================================================
  // HU-05 · Autogestión del estudiante
  // ===================================================================

  test('TC-11 El estudiante consulta sus préstamos activos y su fecha límite', async ({ page }) => {
    const NUEVA = 'ClaveNueva2026';
    await iniciarSesion(page, {
      username: datos.cedulaPrincipal,
      password: datos.passwordVigente,
      passwordNueva: NUEVA,
    });
    datos.passwordVigente = NUEVA;
    guardarEstado(datos);

    await page.goto('/estudiante/prestamos');

    const activos = page.locator('.card', { hasText: 'Préstamos activos' }).locator('tbody tr');
    await expect(activos).toHaveCount(MAX_PRESTAMOS);

    // La fecha límite la calcula la base de datos: préstamo + 7 días. Se
    // deriva de la fecha de préstamo mostrada en la fila (reloj del
    // servidor), no del reloj de esta máquina: si el contenedor va en UTC y
    // aquí es de noche, "hoy" puede ser un día distinto en cada lado.
    const textoFila = await activos.first().innerText();
    const fechas = textoFila.match(/\d{2}\/\d{2}\/\d{4}/g) || [];
    expect(fechas.length, 'la fila debe mostrar préstamo y límite').toBeGreaterThanOrEqual(2);
    const [dia, mes, anio] = fechas[0].split('/').map(Number);
    const limite = new Date(anio, mes - 1, dia + PLAZO_DIAS);
    const limiteEsperado =
      `${String(limite.getDate()).padStart(2, '0')}/${String(limite.getMonth() + 1).padStart(2, '0')}/${limite.getFullYear()}`;
    await expect(activos.first()).toContainText(limiteEsperado);
    await expect(activos.first()).toContainText('A tiempo');

    // Los códigos de los tres préstamos se guardan para las devoluciones.
    const codigos = [];
    for (const fila of await activos.all()) {
      codigos.push((await fila.locator('td').first().innerText()).trim());
    }
    datos.codigosOperacionMultiple = codigos;
    guardarEstado(datos);

    await page.screenshot({ path: rutaEvidencia('TC-11-estudiante-prestamos-activos.png'), fullPage: true });
  });

  // ===================================================================
  // HU-04 · Gestión de devoluciones
  // ===================================================================

  test('TC-12 Registrar la devolución parcial de una operación de dos libros', async ({ page }) => {
    await iniciarSesion(page, CREDENCIALES_SEED.bibliotecario);

    const antes = (await leerStockLibro(page, datos.isbnPrincipal)).disponible;

    await abrirOperacion(page, datos.codigoOperacionMultiple);

    // Se devuelve solo el primer libro de la operación: el otro queda pendiente.
    const filas = page.locator('#form-devolucion tbody tr');
    await expect(filas).toHaveCount(2);
    const primerCodigo = (await filas.first().innerText()).match(/P-\d{4}-\d{4}/)[0];
    datos.codigoPrestamoIndividual = primerCodigo;
    guardarEstado(datos);

    const mensaje = await devolverLibro(page, primerCodigo, 'bueno', 'Devuelto en buen estado');
    expect(mensaje).toContain('Devolución parcial');
    expect(mensaje).toContain('1 pendiente');

    // El ejemplar devuelto en buen estado sí vuelve al stock disponible.
    expect((await leerStockLibro(page, datos.isbnPrincipal)).disponible).toBe(antes + 1);

    // Y la operación queda marcada como parcial, no como completa.
    expect(await estadoOperacion(page, datos.codigoOperacionMultiple)).toContain('parcial');

    await page.screenshot({ path: rutaEvidencia('TC-12-devolucion-parcial.png'), fullPage: true });
  });

  test('TC-13 Completar la devolución del resto de la operación', async ({ page }) => {
    await iniciarSesion(page, CREDENCIALES_SEED.bibliotecario);

    const antes = (await leerStockLibro(page, datos.isbnSecundario)).disponible;

    await abrirOperacion(page, datos.codigoOperacionMultiple);
    const filas = page.locator('#form-devolucion tbody tr');
    const pendiente = page.locator('#form-devolucion tbody tr').filter({
      has: page.locator('input.casilla-libro'),
    });
    await expect(pendiente, 'solo debe quedar un libro pendiente en la operación').toHaveCount(1);
    await expect(filas).toHaveCount(2); // el ya devuelto se sigue mostrando

    const codigoPendiente = (await pendiente.innerText()).match(/P-\d{4}-\d{4}/)[0];
    const mensaje = await devolverLibro(page, codigoPendiente, 'bueno');
    expect(mensaje).toContain('Devolución completada');

    expect((await leerStockLibro(page, datos.isbnSecundario)).disponible).toBe(antes + 1);
    expect(await estadoOperacion(page, datos.codigoOperacionMultiple)).toContain('completa');

    await page.screenshot({ path: rutaEvidencia('TC-13-devolucion-completa.png'), fullPage: true });
  });

  test('TC-14 Un ejemplar devuelto como dañado no vuelve al stock disponible', async ({ page }) => {
    await iniciarSesion(page, CREDENCIALES_SEED.bibliotecario);

    // Estudiante exclusivo de este caso: así el conteo del estudiante
    // principal no interfiere con el escenario.
    await registrarEstudiante(page, {
      cedula: datos.cedulaSecundario,
      nombres: 'Estudiante',
      apellidos: 'Devolucion',
      correo: datos.correoSecundario,
    });

    const mensaje = await registrarPrestamo(page, datos.cedulaSecundario, [datos.isbnPrincipal]);
    expect(mensaje).toContain('Préstamo registrado correctamente');

    // El préstamo de un solo libro se identifica en el listado por su propio
    // código (P-AAAA-NNNN). La búsqueda por cédula deja una única operación
    // pendiente para este estudiante: la que se acaba de registrar. La fila
    // muestra el nombre del estudiante, no su cédula, así que se toma la
    // primera fila del resultado filtrado en vez de buscar la cédula en ella.
    await page.goto(`/bibliotecario/devoluciones?estado=pendientes&q=${datos.cedulaSecundario}`);
    const fila = page.locator('table tbody tr').first();
    await expect(fila).toBeVisible();
    const codigoOperacion = (await fila.innerText()).match(/P-\d{4}-\d{4}/)[0];
    datos.codigoPrestamoDanado = codigoOperacion;
    guardarEstado(datos);

    const { disponible: antes, total: totalAntes } = await leerStockLibro(page, datos.isbnPrincipal);

    await abrirOperacion(page, codigoOperacion);
    const resultado = await devolverLibro(page, codigoOperacion, 'dañado', 'Tapa desprendida');
    expect(resultado).toContain('Devolución completada');

    // Regla de negocio: el disparador de la base repone el ejemplar, y la
    // aplicación lo corrige porque volvió dañado. El stock disponible debe
    // quedar igual que antes; el total no cambia, porque no se perdió.
    const { disponible: despues, total: totalDespues } = await leerStockLibro(page, datos.isbnPrincipal);
    expect(
      despues,
      'un ejemplar devuelto como dañado no debe volver al stock disponible'
    ).toBe(antes);
    expect(totalDespues).toBe(totalAntes);

    await page.screenshot({ path: rutaEvidencia('TC-14-devolucion-danado-stock.png'), fullPage: true });
  });

  // ===================================================================
  // HU-06 · Módulo del gerente y control de acceso
  // ===================================================================

  test('TC-15 Cada rol solo entra a su propio módulo y el gerente ve sus indicadores', async ({ page }) => {
    // El estudiante no puede entrar al módulo del gerente ni al del bibliotecario.
    await iniciarSesion(page, {
      username: datos.cedulaPrincipal,
      password: datos.passwordVigente,
    });

    await page.goto('/gerente/dashboard');
    expect(page.url()).toContain('/estudiante/catalogo');

    await page.goto('/bibliotecario/libros');
    expect(page.url()).toContain('/estudiante/catalogo');

    await page.screenshot({ path: rutaEvidencia('TC-15a-estudiante-sin-acceso-gerente.png'), fullPage: true });

    // El gerente sí entra y ve los indicadores y sus reportes.
    await iniciarSesion(page, CREDENCIALES_SEED.gerente);
    await page.goto('/gerente/dashboard');
    await expect(page.locator('body')).toContainText('Libros activos');

    await page.goto('/gerente/reportes/inventario-actual');
    await expect(page.locator('body')).toContainText('Inventario actual');
    await expect(page.locator('table tbody tr').first()).toBeVisible();

    await page.screenshot({ path: rutaEvidencia('TC-15b-gerente-indicadores-reportes.png'), fullPage: true });
  });

});

// Al terminar la suite se deja una copia del estado usado, util para
// reconstruir el escenario a mano durante la defensa.
test.afterAll(async () => {
  const destino = path.join(__dirname, '..', '..', '05_EVIDENCIAS_NUEVAS', 'PLAYWRIGHT');
  try {
    fs.mkdirSync(destino, { recursive: true });
    fs.writeFileSync(
      path.join(destino, 'datos-ultima-ejecucion.json'),
      JSON.stringify(leerEstado() || datos, null, 2), 'utf-8'
    );
  } catch (error) {
    // No es parte del resultado de ninguna prueba: si falla, no altera nada.
  }
});
