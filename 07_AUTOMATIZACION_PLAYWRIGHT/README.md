# Automatización de pruebas — Biblioteca VV

Suite de pruebas de extremo a extremo (E2E) sobre la interfaz web del sistema,
escrita con **Playwright Test** y ejecutada sobre Chromium.

Esta suite reemplaza a la de diez casos del Corte II. El cambio no fue
cosmético: después de esa entrega cambiaron el registro de préstamos (ahora
admite varios libros en una sola operación), las devoluciones (ahora son por
operación y admiten devolución parcial, con estado por libro) y los listados
(ahora paginan y filtran en el servidor). La correspondencia entre cada caso
anterior y su sucesor está documentada en el informe final, sección 12.

---

## 1. Requisitos

| Requisito | Detalle |
|---|---|
| Node.js | 18 o superior |
| Navegador | Chromium de Playwright (`npx playwright install chromium`) |
| Aplicación | Biblioteca VV corriendo en `http://127.0.0.1:5000` |
| Base de datos | PostgreSQL con las migraciones, `database/setup.sql` y `database/seed.py` aplicados |

La suite usa las credenciales que crea el *seed*: `bibliotecario / Biblio`,
`gerente / Gerente` y `estudiante / Estudiante`. El inicio de sesión **no** es
uno de los casos de prueba: se usa como precondición reutilizable.

---

## 2. Cómo ejecutarla

```bash
# 1. Levantar la aplicación (en otra terminal, desde la carpeta del proyecto)
python -m flask --app run.py run

# 2. Instalar dependencias (solo la primera vez)
cd 07_AUTOMATIZACION_PLAYWRIGHT
npm install
npx playwright install chromium

# 3. Ejecutar la suite completa
npm test

# 4. Abrir el reporte HTML de la última ejecución
npm run reporte
```

Un solo caso:

```bash
npx playwright test -g "TC-08"
```

Con el navegador visible (útil para la defensa):

```bash
npm run test:headed
```

### Variables de entorno opcionales

| Variable | Para qué sirve |
|---|---|
| `BASE_URL` | Dirección de la aplicación, si no es `http://127.0.0.1:5000` |
| `CHROMIUM_PATH` | Ruta a un Chromium ya instalado, para entornos donde no se puede descargar el navegador |
| `ASSETS_OFFLINE=1` | Sirve Bootstrap y Chart.js desde `assets-offline/` cuando la máquina no tiene salida a internet (ver sección 5) |

---

## 3. Qué contiene la suite

15 casos de alto valor, agrupados por historia de usuario. Se ejecutan en el
orden en que están declarados y con **un solo worker**, porque comparten
datos: el libro que crea TC-01 es el que se presta después, y el estudiante
que crea TC-05 es el que va acumulando préstamos hasta el límite.

| ID | Caso | HU |
|---|---|---|
| TC-01 | Registrar un libro nuevo creando su autor sin salir del formulario | HU-02 |
| TC-02 | Rechazar un segundo libro con el mismo ISBN | HU-02 |
| TC-03 | Rechazar un ISBN-13 con dígito verificador incorrecto | HU-02 |
| TC-04 | Registrar un libro con portada y resumen, y verlo en el catálogo | HU-02 / HU-05 |
| TC-05 | Registrar un estudiante con cédula válida y entregar sus credenciales | HU-01 |
| TC-06 | Detectar una cédula duplicada mientras se escribe y al enviar | HU-01 |
| TC-07 | Registrar el préstamo de un libro y comprobar que el stock baja en uno | HU-03 |
| TC-08 | Registrar un préstamo de dos libros en una sola operación | HU-03 |
| TC-09 | Advertir que el estudiante llegó al máximo de préstamos activos | HU-03 |
| TC-10 | El servidor rechaza el préstamo aunque se envíe el formulario sin pasar por la pantalla | HU-03 |
| TC-11 | El estudiante consulta sus préstamos activos y su fecha límite | HU-05 |
| TC-12 | Registrar la devolución parcial de una operación de dos libros | HU-04 |
| TC-13 | Completar la devolución del resto de la operación | HU-04 |
| TC-14 | Un ejemplar devuelto como dañado no vuelve al stock disponible | HU-04 |
| TC-15 | Cada rol solo entra a su propio módulo y el gerente ve sus indicadores | HU-06 |

---

## 4. Estructura de archivos

```
07_AUTOMATIZACION_PLAYWRIGHT/
├── playwright.config.js          configuración (1 worker, reportes, evidencias)
├── package.json
├── assets-offline/               copias locales de Bootstrap 5.3.3 y Chart.js 4.4.1
├── scripts/
│   └── capturas-sistema.js       utilidad: recorre las pantallas y guarda capturas
└── playwright-tests/
    ├── biblioteca.spec.js        los 15 casos
    ├── fixtures.js               test/expect propios (ver sección 5)
    └── helpers/
        ├── sesion.js             inicio de sesión y cambio de clave obligatorio
        ├── generadores.js        cédulas e ISBN válidos (mismo algoritmo del backend)
        ├── inventario.js         lectura del stock desde el listado de libros
        ├── prestamos.js          flujo del formulario de préstamo con varios libros
        ├── devoluciones.js       flujo de devolución por operación
        ├── evidencias.js         ruta de las capturas
        └── estado-compartido.js  datos compartidos entre casos
```

Las evidencias **no** se guardan aquí: van a
`05_EVIDENCIAS_NUEVAS/PLAYWRIGHT/` (capturas, reporte HTML, resultado en JSON
y trazas de los casos que fallen).

---

## 5. Ejecución sin internet (`ASSETS_OFFLINE=1`)

Las pantallas de Biblioteca VV cargan Bootstrap y Chart.js desde jsdelivr. En
una máquina con internet no hay nada que configurar. En una máquina sin salida
a internet esas peticiones fallan y la página se queda sin las clases de
Bootstrap; entre ellas `d-none`, que es la que mantiene oculto el overlay de
"Procesando préstamo…". Sin esa clase el overlay tapa la pantalla y las
pruebas fallan por un motivo ajeno al sistema.

`playwright-tests/fixtures.js` resuelve eso: con `ASSETS_OFFLINE=1`, esas dos
peticiones se responden con las copias locales de `assets-offline/`, que son
**las mismas versiones** que declara la aplicación. No se modifica ningún
archivo del proyecto ni el comportamiento del sistema: solo cambia de dónde
sale un archivo estático.

---

## 6. Datos de prueba

La cédula y los ISBN se generan al azar en cada corrida, con el mismo cálculo
de dígito verificador que usa `app/validators.py`. Gracias a eso la suite se
puede repetir sin chocar con los registros que dejó la ejecución anterior.
Los valores usados en la última corrida quedan en
`05_EVIDENCIAS_NUEVAS/PLAYWRIGHT/datos-ultima-ejecucion.json`, lo que permite
reconstruir el escenario a mano durante la defensa.
