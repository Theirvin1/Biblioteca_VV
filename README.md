# Biblioteca VV — Sistema de Gestión Bibliotecaria

Sistema web para la gestión integral de una biblioteca universitaria (UTEQ):
catálogo de libros, registro de estudiantes, préstamos por operación,
devoluciones parciales o totales con cálculo de multas, y reportes
gerenciales con indicadores y gráficas.

## Roles y funcionalidades

| Rol | Acceso | Funcionalidades |
|---|---|---|
| Estudiante | `/estudiante` | Catálogo paginado con filtros, detalle del libro con portada ampliable, resumen en modal, mis préstamos activos e historial, cambio de contraseña en el primer ingreso |
| Bibliotecario | `/bibliotecario` | Registro de libros (con portada y autores), registro de estudiantes con credenciales temporales, préstamos de uno o varios libros por operación (con control de cupos y stock), devoluciones parciales/totales con estado por ejemplar, listados paginados |
| Gerente | `/gerente` | Dashboard con gráficas (préstamos por estado, libros más prestados, movimiento mensual, top deudores), 6 reportes con filtros y paginación, gestión de usuarios (crear, activar/desactivar, restablecer contraseña, cambiar rol) |

## Flujo general del sistema

1. El bibliotecario registra el libro; el sistema crea un ejemplar por cada
   unidad del stock y el libro aparece en el catálogo.
2. El bibliotecario registra al estudiante; el sistema crea su cuenta y
   entrega la contraseña temporal.
3. El estudiante entra por primera vez, cambia su contraseña y consulta el
   catálogo.
4. El bibliotecario registra el préstamo de uno o varios libros; el sistema
   comprueba cupos y disponibilidad, asigna ejemplares, genera los códigos
   (`P-…`, operación `GRP-…`) y descuenta el inventario.
5. El estudiante ve sus préstamos con la fecha límite calculada por el sistema.
6. El estudiante devuelve todo o una parte; el bibliotecario indica el estado
   de cada ejemplar y el sistema ajusta el inventario y calcula la multa si
   corresponde.
7. El gerente consulta los indicadores y los reportes, que reflejan el
   movimiento del día.

## Stack tecnológico

- **Backend:** Python 3.12, Flask 3.1, Flask-Login, Flask-WTF, SQLAlchemy 2.0,
  Flask-Migrate (Alembic), APScheduler
- **Base de datos:** PostgreSQL 16 con triggers y vistas de negocio
  (`database/setup.sql`: control de stock, fecha límite, auditoría, multas)
- **Frontend:** Jinja2 + Bootstrap 5.3, Chart.js en el dashboard
- **Pruebas:** pytest (230 casos) + Playwright Test (15 casos E2E en Chromium)
- **Infraestructura:** Docker y Docker Compose

## Estructura del proyecto

```
├── app/
│   ├── controllers/        # auth + blueprints por rol
│   │   ├── bibliotecario/  # libros, estudiantes, prestamos, devoluciones
│   │   ├── estudiante/     # catalogo, prestamos, perfil
│   │   └── gerente/        # dashboard, reportes, usuarios
│   ├── models/             # SQLAlchemy (Libro, Estudiante, Prestamo, ...)
│   ├── templates/          # Jinja2 (shared/, bibliotecario/, estudiante/, gerente/)
│   └── static/             # css, js
├── database/
│   ├── setup.sql           # triggers, funciones y vistas (reejecutable)
│   └── seed.py             # usuarios demo, configuración, catálogos base
├── migrations/             # migraciones Alembic (tablas)
├── scripts/                # utilidades SQL de carga y normalización de datos
├── tests/                  # suite pytest (usa TEST_DATABASE_URL)
├── 07_AUTOMATIZACION_PLAYWRIGHT/  # suite E2E (ver su README)
├── Dockerfile / docker-compose.yml / docker-entrypoint.sh
└── run.py                  # punto de entrada Flask
```

## Instalación (recomendada: Docker)

```bash
git clone <repo>
cd biblio
copy .env.example .env     # en Linux: cp .env.example .env
# Pon un SECRET_KEY propio en .env:
# python -c "import secrets; print(secrets.token_hex(32))"
docker compose up -d --build
```

El entrypoint deja todo listo solo (migraciones + `setup.sql` + `seed.py`,
todo idempotente). La app queda en http://localhost:5000 con los usuarios
demo:

| Usuario | Clave | Rol |
|---|---|---|
| `gerente` | `Gerente` | Gerente |
| `bibliotecario` | `Biblio` | Bibliotecario |
| `estudiante` | `Estudiante` | Estudiante (con perfil vinculado) |

Comandos útiles:

```bash
docker compose logs -f app   # ver la app
docker compose down          # apagar (los datos se conservan en el volumen)
docker compose down -v       # apagar borrando los datos
```

## Instalación manual (sin Docker)

```bash
python -m venv venv
venv\Scripts\activate        # en Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env       # completar DATABASE_URL, SECRET_KEY y TEST_DATABASE_URL
flask --app run.py db upgrade
psql -U <usuario> -d biblioteca_vv -f database/setup.sql
python -m database.seed
python -m flask --app run.py run
```

## Pruebas

```bash
# Backend (230 casos; requiere TEST_DATABASE_URL distinta a la de desarrollo)
python -m pytest tests/ -q

# E2E en Chromium (15 casos TC-01…TC-15; app corriendo en localhost:5000)
cd 07_AUTOMATIZACION_PLAYWRIGHT
npm install
npm test                  # headless
npm run test:headed       # con navegador visible
npm run reporte           # reporte HTML de la última corrida
```

Detalle de la suite E2E, credenciales y modo sin internet en
`07_AUTOMATIZACION_PLAYWRIGHT/README.md`.

## Reglas de negocio principales

- Cupo por defecto: 3 préstamos activos por estudiante y plazo de 7 días
  (configurable en `configuracion_sistema`).
- Sin stock disponible no hay préstamo (disparador `fn_bloquear_stock_negativo`).
- Multa de 0.50 por día de retraso; un ejemplar devuelto como dañado no
  vuelve al stock disponible.
- Las cuentas de estudiante conservan siempre su rol y su ficha vinculada.
- Todos los listados extensos paginan y filtran en el servidor (10 por
  página; catálogo del estudiante, 15).

## Documentación adicional

- `docs/DOCUMENTACION_ENTREGA_AZURE_VALIDACIONES.md` — entrega, despliegue
  en Azure y bitácora de validaciones.
- `07_AUTOMATIZACION_PLAYWRIGHT/README.md` — suite E2E y evidencias.
- `DEPLOY_AZURE.md` — despliegue en Azure App Service.
