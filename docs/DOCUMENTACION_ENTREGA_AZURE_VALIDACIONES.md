# Documentación de entrega — Despliegue en Azure y refuerzo de validaciones

## 1. Portada / Datos generales

- **Proyecto:** Biblioteca_VV
- **Descripción:** Sistema web de gestión de biblioteca con tres roles (bibliotecario, estudiante, gerente): catálogo de libros, registro de estudiantes, préstamos, devoluciones, reportes y dashboard.
- **Tecnologías utilizadas:**
  - Backend: Flask, SQLAlchemy (Flask-SQLAlchemy), Flask-Migrate (Alembic), Flask-Login, Flask-WTF (WTForms)
  - Base de datos: PostgreSQL (funciones, triggers y vistas propias en `database/setup.sql`)
  - Frontend: Jinja2 + Bootstrap 5 + JavaScript plano
  - Pruebas: pytest + pytest-flask
  - Servidor de producción: Gunicorn
  - Infraestructura: Azure App Service (Linux) + Azure Database for PostgreSQL Flexible Server
  - CI/CD: GitHub Actions
- **Rama usada para el despliegue:** `feature/deploy-azure`
- **Objetivo del trabajo documentado aquí:** dejar el proyecto desplegado en Azure de forma funcional y automatizada, y reforzar las validaciones de datos del sistema (formularios y endpoints) para que el servidor rechace información inválida aunque no pase por el navegador.

---

## 2. Resumen general de lo realizado

En esta etapa del proyecto se hicieron dos bloques de trabajo, ambos sobre la rama `feature/deploy-azure`:

**Preparación y despliegue en Azure:**
- Se agregó Gunicorn como servidor de producción (`requirements.txt`).
- Se conectó la aplicación Flask a una base de datos PostgreSQL administrada en Azure, normalizando el formato de la URL de conexión.
- Se creó un script (`scripts/init_azure_db.py`) para inicializar la base de datos en Azure de forma segura y repetible.
- Se configuró el despliegue automático con GitHub Actions (`.github/workflows/`), disparado por cada `push` a `feature/deploy-azure`.
- Se agregó una redirección de la ruta raíz `/` hacia `/login`, para que el dominio de Azure no muestre un error 404 al abrirse sin ruta.

**Refuerzo de validaciones:**
- Se detectó que el sistema aceptaba datos claramente inválidos (nombres con números, teléfonos con letras, correos mal formados, cédulas e ISBN sin verificar su dígito de control, etc.).
- Se creó un módulo de validadores reutilizables (`app/validators.py`) y se aplicó en los formularios de estudiantes, libros y préstamos, además de en el endpoint AJAX de creación de autores.
- Se agregaron pruebas automáticas nuevas para cubrir estos casos, sin romper ninguna de las pruebas ya existentes.

---

## 3. Arquitectura del despliegue en Azure

**Componentes:**
- **Azure App Service (Linux, Python 3.12):** aloja y ejecuta la aplicación Flask a través de Gunicorn.
- **Azure Database for PostgreSQL Flexible Server:** base de datos administrada, separada de cualquier entorno local de desarrollo o pruebas.
- **GitHub Actions:** automatiza el build y el despliegue cada vez que se sube código a la rama `feature/deploy-azure`.

**Variables de entorno usadas por la aplicación** (configuradas como *App Settings* en Azure, fuera del repositorio):
- `FLASK_ENV=production`
- `DATABASE_URL` — cadena de conexión a PostgreSQL. Ejemplo con la clave oculta:
  ```
  postgresql://biblioadmin:********@biblioteca-vv-db-jaime.postgres.database.azure.com:5432/biblioteca_db?sslmode=require
  ```
- `SECRET_KEY` — clave secreta de Flask (sesiones, protección CSRF).

**Startup command:** ver sección 6.

**Flujo general de despliegue:**

```
GitHub (rama feature/deploy-azure)
        │  push
        ▼
GitHub Actions (.github/workflows/feature-deploy-azure_biblioteca-vv-jaime.yml)
        │  build (instala requirements.txt) + login a Azure (OIDC) + deploy
        ▼
Azure App Service (Linux, Python 3.12) — corre Gunicorn
        │  DATABASE_URL
        ▼
Azure Database for PostgreSQL Flexible Server
```

El workflow de GitHub Actions confirmado en el repositorio (`.github/workflows/feature-deploy-azure_biblioteca-vv-jaime.yml`) hace lo siguiente:
1. Se dispara con `push` a `feature/deploy-azure` (o manualmente con `workflow_dispatch`).
2. Job `build`: configura Python 3.12, instala `requirements.txt` en un entorno virtual y sube el código como artefacto (excluyendo el entorno virtual).
3. Job `deploy`: descarga el artefacto, inicia sesión en Azure mediante OIDC (`azure/login@v2`, usando credenciales federadas guardadas como *secrets* de GitHub — no hay contraseñas en texto plano en el repositorio) y despliega con `azure/webapps-deploy@v3` al App Service `biblioteca-vv-jaime`, slot `Production`.

---

## 4. Recursos creados en Azure

| Recurso | Nombre | Fuente de confirmación |
|---|---|---|
| Resource Group | `rg-biblioteca-vv` | Indicado para esta entrega; no aparece almacenado en el repositorio (los grupos de recursos no se versionan en git) |
| App Service | `biblioteca-vv-jaime` | **Confirmado**: aparece en el nombre y contenido del workflow de GitHub Actions (`app-name: 'biblioteca-vv-jaime'`) |
| PostgreSQL Flexible Server | `biblioteca-vv-db-jaime` | Indicado para esta entrega; no verificable desde el código |
| Base de datos | `biblioteca_db` | Indicado para esta entrega; no verificable desde el código |
| Región | Brazil South | **Confirmado**: coincide con el dominio público (`brazilsouth-01.azurewebsites.net`) |
| Runtime | Python 3.12 | **Confirmado**: `python-version: '3.12'` en el workflow de GitHub Actions |
| App Service Plan | — | **Pendiente de confirmar**: no aparece en ningún archivo del repositorio (se configura en Azure Portal/CLI, fuera del control de versiones) |
| URL pública | `https://biblioteca-vv-jaime-c0degxfhf6hsbeg5.brazilsouth-01.azurewebsites.net/` | Confirmada durante las pruebas de la redirección de la ruta raíz (sección 9) |

---

## 5. Variables de entorno configuradas

| Variable | Para qué sirve |
|---|---|
| `FLASK_ENV=production` | Le indica a `create_app()` (`app/__init__.py`) que use `ProductionConfig` (`config.py`): desactiva el modo debug y usa la configuración pensada para producción. |
| `DATABASE_URL` | Cadena de conexión a PostgreSQL que usa SQLAlchemy. `config.py` la normaliza automáticamente si llega con el esquema `postgres://` en vez de `postgresql://` (ver sección 6). |
| `SECRET_KEY` | Clave usada por Flask para firmar la sesión de usuario y los tokens CSRF de los formularios (Flask-WTF). Debe ser un valor aleatorio y secreto, distinto entre entornos. |
| `SCM_DO_BUILD_DURING_DEPLOYMENT=true` | Le indica a Azure (motor de build Oryx) que instale automáticamente `requirements.txt` durante el despliegue, en vez de esperar que las dependencias ya vengan incluidas en el paquete subido. |
| `WEBSITES_PORT=8000` | Le indica a Azure App Service en qué puerto interno está escuchando Gunicorn dentro del contenedor, para que el proxy de Azure enrute el tráfico correctamente hacia ese puerto. |

> No se documentan valores reales de estas variables. `DATABASE_URL` y `SECRET_KEY` viven únicamente como *App Settings* en Azure y en el archivo `.env` local (no versionado; ver `.env.example` en la raíz del proyecto para el formato esperado).

---

## 6. Cambios hechos para Azure

| Archivo | Cambio | Motivo |
|---|---|---|
| `requirements.txt` | Se agregó `gunicorn==23.0.0` | Servidor WSGI de producción; el servidor de desarrollo de Flask (`app.run()`) no está pensado para producción. |
| `config.py` | Se agregó la función `_normalizar_url_postgres()`, aplicada tanto a `DATABASE_URL` como a `TEST_DATABASE_URL` | Algunos proveedores (Azure/Heroku) entregan cadenas de conexión con el esquema `postgres://`, pero SQLAlchemy 1.4+ solo acepta `postgresql://`. Sin esta normalización, la app no arrancaría en producción. |
| `run.py` | Ya exponía `app = create_app()` a nivel de módulo (no requirió cambios) | Es lo que permite que Gunicorn encuentre la aplicación con el comando `run:app` (módulo `run`, variable `app`). |
| `scripts/init_azure_db.py` | Archivo nuevo | Ver detalle completo en la sección 7. |
| `scripts/__init__.py` | Archivo nuevo, vacío | Convierte `scripts/` en un paquete de Python para poder ejecutar `python -m scripts.init_azure_db`. |
| `DEPLOY_AZURE.md` | Archivo nuevo, en la raíz del proyecto | Guía paso a paso (comandos `az` de referencia) para crear los recursos de Azure, configurar variables de entorno, desplegar el código e inicializar la base de datos. |
| `.github/workflows/feature-deploy-azure_biblioteca-vv-jaime.yml` | Archivo generado por la integración de Azure con GitHub | Automatiza build + deploy en cada push a `feature/deploy-azure`. |

**Startup command:**

- **Inicial (usado una sola vez, para inicializar la base de datos en el primer despliegue):**
  ```
  python -m scripts.init_azure_db && gunicorn --bind=0.0.0.0:8000 run:app
  ```
- **Final / recomendado (una vez la base ya está inicializada):**
  ```
  gunicorn --bind=0.0.0.0:8000 run:app
  ```

> **Nota:** el comando de inicio configurado en Azure App Service se administra desde el Portal/CLI de Azure, no desde un archivo versionado en este repositorio. Los dos comandos de arriba corresponden a lo indicado para esta entrega; `DEPLOY_AZURE.md` documenta una variante equivalente sin el puerto fijo (`gunicorn --bind=0.0.0.0 --timeout 600 run:app`), pensada como plantilla general reutilizable en otros despliegues.

---

## 7. Inicialización de la base de datos

La base de datos en Azure se inicializa con `scripts/init_azure_db.py`, que hace tres pasos en orden, dentro del mismo contexto de aplicación (`create_app()`):

1. **Migraciones (Flask-Migrate/Alembic):** llama a `flask_migrate.upgrade()`, que crea o actualiza las tablas a partir de los modelos de SQLAlchemy (`app/models/`) y del historial de migraciones (`migrations/versions/`).
2. **`database/setup.sql`:** aplica los índices, funciones (`validar_prestamo`, `generar_codigo_prestamo`, `calcular_multa`, `obtener_indicadores_dashboard`, etc.), triggers y vistas propias del sistema. El script detecta automáticamente si ya se aplicó antes (busca la vista `vista_prestamos_activos`) y se salta este paso si ya existe, porque `setup.sql` en sí mismo **no es idempotente** (`CREATE INDEX` y `CREATE TRIGGER` fallarían si se repiten sobre el mismo esquema).
3. **`database/seed.py`:** carga los datos base — catálogos (países, facultades, carreras, categorías de libros) y los tres usuarios iniciales del sistema:
   - `gerente` (rol gerente)
   - `bibliotecario` (rol bibliotecario)
   - `estudiante` (rol estudiante, con su registro de `Estudiante` vinculado)

   Este script ya es idempotente por diseño: antes de insertar cada fila verifica si ya existe, así que ejecutarlo varias veces no duplica datos.

**Por qué el script solo debía usarse para inicializar:** `scripts/init_azure_db.py` hace trabajo de mantenimiento (migrar, aplicar SQL, sembrar datos), no de servir tráfico web. Una vez que la base de datos ya quedó inicializada, dejarlo como parte del comando de arranque significaría que Azure lo ejecuta en **cada reinicio del contenedor**, lo cual es innecesario (los tres pasos ya detectan que no hay nada nuevo que hacer, pero igual consumen tiempo de arranque) y no es su propósito: por eso el comando de inicio final recomendado es solo `gunicorn --bind=0.0.0.0:8000 run:app`, sin el paso de inicialización.

---

## 8. Problemas encontrados y soluciones

> Esta sección documenta lo reportado durante el proceso real de despliegue en Azure. Ese proceso ocurrió fuera de las sesiones donde se generó el código (portal de Azure, terminal local), por lo que aquí se registra como bitácora de lo comunicado, no como algo verificado directamente desde el repositorio.

| Problema | Diagnóstico | Solución aplicada |
|---|---|---|
| El repositorio "original" no aparecía como origen disponible para conectar en Azure | Se estaba trabajando desde un fork de un colaborador, no desde el repositorio raíz del equipo | Se usó el fork en GitHub `Grinjoww/Biblioteca_VV` (remoto `azure` en este repositorio local) y se desplegó específicamente la rama `feature/deploy-azure` |
| Error 500 al abrir la aplicación por primera vez en Azure | Se revisó mediante **Log Stream** de Azure App Service | Ver siguiente fila — la causa raíz fue el error de conexión a PostgreSQL |
| Error de conexión a PostgreSQL: `password authentication failed for user biblioadmin` | El log mostró que la aplicación no podía autenticarse contra la base de datos | Se reseteó la contraseña del usuario administrador de PostgreSQL, se actualizó la variable de entorno `DATABASE_URL` en los *App Settings* del App Service con la nueva contraseña, y se reinició el App Service |
| Confirmación de que el sistema quedó operativo | — | Se validó, revisando el Log Stream, que las migraciones, `setup.sql` y el seed se ejecutaron correctamente, y que Gunicorn quedó sirviendo la aplicación sin errores |

**Confirmable directamente en el código de este repositorio:** la normalización de `postgres://` → `postgresql://` en `config.py` (sección 6) existe precisamente para evitar uno de los errores de conexión más comunes al desplegar en proveedores como Azure; y el guard de `scripts/init_azure_db.py` que detecta si `setup.sql` ya fue aplicado existe para que reintentar la inicialización después de solucionar un problema (como el de la contraseña) no falle por partes ya aplicadas.

---

## 9. Redirección de la ruta raíz

**Problema:** al abrir el dominio de Azure sin ninguna ruta (`https://biblioteca-vv-jaime-c0degxfhf6hsbeg5.brazilsouth-01.azurewebsites.net/`), el servidor respondía con un error 404, porque el proyecto nunca definió una ruta para `/` — todas las rutas reales cuelgan de blueprints con prefijo (`/login`, `/bibliotecario/...`, `/estudiante/...`, `/gerente/...`).

**Solución** (`app/__init__.py`, dentro de `create_app()`, después de registrar los blueprints):

```python
@app.route('/')
def index():
    return redirect(url_for('auth.login'))
```

**Por qué `url_for('auth.login')` y no `"/login"` hardcodeado:** el endpoint de login pertenece al blueprint `auth_bp`, registrado con el nombre `auth`, por lo que Flask lo identifica internamente como `auth.login` (así lo usa también `login_manager.login_view = 'auth.login'` en el mismo archivo). Usar `url_for()` en vez de escribir la ruta a mano hace que, si el prefijo del blueprint o la URL de login cambiaran en el futuro, esta redirección se siga generando correctamente sin tener que recordar actualizarla manualmente en dos lugares distintos.

**Prueba realizada:** se levantó la aplicación localmente y se confirmó, navegando realmente (no solo leyendo el código), que `GET /` responde con una redirección y termina en `/login`. Además, `python -m pytest -v` se volvió a correr después de este cambio y las pruebas siguieron pasando sin regresiones.

---

## 10. Refuerzo de validaciones

**Problema detectado:** antes de este refuerzo, el sistema permitía registrar datos sin sentido a través de los formularios — por ejemplo, nombres compuestos solo por números, teléfonos con letras, correos sin formato de correo real, cédulas de 10 dígitos sin verificar si son cédulas ecuatorianas válidas, o ISBN de 13 dígitos inventados sin verificar su dígito de control.

**Solución:** se construyó un módulo de validadores reutilizables (`app/validators.py`) y se aplicó del lado servidor con Flask-WTF/WTForms, de modo que los datos se rechazan **aunque se envíen manualmente** (por ejemplo, desde Postman) sin pasar por el HTML del navegador. Los formularios siguen teniendo atributos HTML básicos como apoyo visual, pero la validación real y definitiva ocurre siempre en el servidor.

### Tabla de validaciones aplicadas

| Entidad | Campo | Validación aplicada | Mensaje de error |
|---|---|---|---|
| Estudiante | Cédula | Obligatoria; exactamente 10 dígitos; dígito verificador real de cédula ecuatoriana (código de provincia 01-24 + módulo 10) | "La cédula debe contener exactamente 10 dígitos." / "La cédula ingresada no es válida." |
| Estudiante | Nombres | Obligatorio; solo letras, espacios, tildes y ñ; 2 a 100 caracteres | "Los nombres solo pueden contener letras y espacios." |
| Estudiante | Apellidos | Igual que nombres | "Los apellidos solo pueden contener letras y espacios." |
| Estudiante | Correo | Obligatorio; formato de correo real (usuario@dominio.tld); máximo 150 caracteres; no se permite duplicado (verificado en el controlador) | "Ingresa un correo válido." |
| Estudiante | Teléfono | Opcional, pero si se ingresa: solo números, **exactamente 10 dígitos** | "El teléfono debe contener exactamente 10 dígitos." |
| Estudiante | Fecha de nacimiento | Obligatoria; no puede ser futura; la edad resultante debe estar entre 15 y 100 años | "La fecha de nacimiento no puede ser futura." / "El estudiante debe tener entre 15 y 100 años." |
| Estudiante | Carrera | Debe ser una de las carreras existentes en la base de datos (lista desplegable validada por WTForms; un id inventado se rechaza automáticamente) | "Selecciona una carrera." |
| Estudiante | Género | Solo los valores permitidos (M, F, O, o en blanco) | (rechazado automáticamente por WTForms si el valor no está en la lista) |
| Libro | ISBN | Obligatorio; exactamente 13 dígitos; dígito verificador real de ISBN-13; no se permite duplicado (verificado en el controlador) | "El ISBN debe contener exactamente 13 dígitos numéricos." / "El ISBN ingresado no es válido." |
| Libro | Título | Obligatorio; 2 a 255 caracteres; no puede ser solo números o solo símbolos (debe contener al menos una letra) | "El título no puede contener solo números o símbolos." |
| Libro | Editorial | Obligatoria; 2 a 150 caracteres; debe contener al menos una letra | "La editorial no puede contener solo números o símbolos." |
| Libro | Año de publicación | Opcional; si se ingresa, debe estar entre el año 1000 y el año actual (calculado dinámicamente, no una fecha fija) | "Ingresa un año de publicación válido (entre 1000 y el año actual)." |
| Libro | Stock inicial | Obligatorio; número entero; entre 1 y 200 (ya era `IntegerField`, por lo que letras o decimales ya se rechazaban antes de este refuerzo) | "Ingresa una cantidad entre 1 y 200." |
| Libro | Categoría | Debe existir en la base de datos (lista desplegable validada por WTForms) | "Selecciona una categoría." |
| Libro | Autores | Debe seleccionarse al menos uno; los ids se verifican contra la base de datos en el controlador antes de guardar | "Debes agregar al menos un autor." / "Uno o más autores seleccionados no son válidos." |
| Autor (creación por AJAX) | Nombres / Apellidos | Obligatorios; mínimo 2 caracteres; solo letras y espacios | "Nombres y apellidos deben tener al menos 2 caracteres." / "Nombres y apellidos solo pueden contener letras y espacios." |
| Préstamo | Cédula del estudiante | Formato: exactamente 10 dígitos numéricos (sin dígito verificador — ver nota abajo) | "La cédula debe contener exactamente 10 dígitos." |
| Préstamo | ISBN del libro | Formato: exactamente 13 dígitos numéricos (sin dígito verificador — ver nota abajo) | "El ISBN debe contener exactamente 13 dígitos numéricos." |
| Préstamo | Existencia y estado del estudiante/libro | Verificado contra la base de datos mediante la función `validar_prestamo()` (PostgreSQL): el estudiante debe existir y estar activo, el libro debe existir, estar activo y tener stock disponible | Mensaje devuelto directamente por `validar_prestamo()` |
| Préstamo | Máximo de préstamos activos | Se agregó la verificación contra `configuracion_sistema.max_prestamos_activos` (el valor ya existía en la base desde el seed, pero **no se aplicaba en ningún lado del código** antes de este refuerzo) | "El estudiante ya alcanzó el máximo de N préstamos activos permitidos." |

**Nota sobre cédula/ISBN en el formulario de préstamos:** a propósito, ese formulario **no** exige el dígito verificador completo, solo el formato (cantidad de dígitos). La razón es que ese campo busca un estudiante o un libro que **ya debe existir**, no crea uno nuevo; si se exigiera el dígito verificador ahí también, cualquier estudiante o libro de prueba/demo registrado antes de este refuerzo (con datos "inventados") dejaría de poder recibir préstamos, porque el formulario rechazaría el dato antes de siquiera consultar la base. La validación completa (dígito verificador) se aplica solo donde se **crea** el dato: al registrar un estudiante o un libro nuevo.

---

## 11. Archivos modificados por las validaciones

| Archivo | Qué contiene / qué se cambió |
|---|---|
| `app/validators.py` | **Archivo nuevo.** Funciones puras de validación (`es_solo_letras`, `es_correo_valido`, `es_telefono_valido`, `es_cedula_ecuatoriana_valida`, `es_isbn13_valido`, `es_anio_valido`) y sus versiones como validadores de WTForms (`SoloLetras`, `ContieneLetra`, `CorreoValido`, `TelefonoValido`, `CedulaEcuatorianaValida`, `Isbn13Valido`, `AnioValido`, `FechaNoFutura`, `EdadEntre`). |
| `app/forms.py` | `LibroForm`, `EstudianteForm` y `PrestamoForm` reescritos para usar los validadores de `app/validators.py`, con mensajes de error en español agregados donde faltaban. |
| `app/controllers/bibliotecario/estudiantes.py` | El endpoint AJAX `api_verificar_cedula` (que valida la cédula en vivo mientras se escribe) ahora usa el dígito verificador real, no solo la cantidad de dígitos. |
| `app/controllers/bibliotecario/libros.py` | El endpoint AJAX `api_crear_autor` ahora valida longitud mínima y que nombres/apellidos contengan solo letras. |
| `app/controllers/bibliotecario/prestamos.py` | Se agregó la función `_max_prestamos_activos()` y la verificación del límite de préstamos activos antes de registrar un préstamo nuevo. |
| `app/templates/bibliotecario/estudiantes_nuevo.html` | Se agregaron los bloques de error que faltaban para los campos `telefono`, `fecha_nacimiento` y `genero` (antes esos 3 campos no mostraban su mensaje de error en pantalla aunque el servidor sí los rechazara). |
| `tests/test_validaciones_formularios.py` | Ampliado con pruebas nuevas para cubrir los casos inválidos y válidos descritos en la sección 12. |

---

## 12. Pruebas automáticas

**Comando usado:**

```bash
python -m pytest -v
```

**Resultado confirmado en este entorno:**

```
33 passed, 31 warnings in 14.25s
```

Las **20 pruebas originales** (autenticación, control de acceso por rol, rutas principales de cada módulo, reportes del gerente) siguieron pasando sin ningún cambio en su lógica. Se agregaron **13 pruebas nuevas** relacionadas con las validaciones reforzadas, entre ellas:

- Registro de libro con ISBN de formato inválido → falla
- Registro de libro con ISBN de 13 dígitos pero dígito verificador incorrecto → falla
- Registro de libro con título compuesto solo por símbolos → falla
- Registro de libro con datos válidos → se guarda correctamente
- Registro de préstamo con cédula de formato inválido → falla
- Registro de estudiante con cédula de dígito verificador incorrecto → falla
- Registro de estudiante con nombres que contienen números → falla
- Registro de estudiante con correo mal formado → falla
- Registro de estudiante con teléfono que contiene letras → falla
- Registro de estudiante con teléfono de 9 dígitos → falla
- Registro de estudiante con teléfono de 11 dígitos → falla
- Registro de estudiante con teléfono de exactamente 10 dígitos → se guarda correctamente
- Registro de estudiante con fecha de nacimiento futura → falla
- Registro de estudiante con edad fuera del rango 15-100 años → falla
- Registro de estudiante con datos válidos → se guarda correctamente

> Nota: algunas de estas pruebas dependen de que exista una base de datos de pruebas configurada en `TEST_DATABASE_URL` (separada de la base de desarrollo/producción), tal como se documentó en la fase de pruebas del proyecto. El resultado de arriba corresponde a una corrida completa contra esa base de pruebas.

---

## 13. Evidencias recomendadas para la exposición

Checklist de capturas de pantalla a preparar antes de la presentación:

- [ ] GitHub Actions con la corrida del workflow en verde (build + deploy exitosos).
- [ ] Azure App Service mostrando el estado "Running" / en ejecución.
- [ ] Log Stream del App Service mostrando a Gunicorn arrancado y sirviendo peticiones.
- [ ] Log Stream mostrando la salida de `scripts/init_azure_db.py` (migraciones, `setup.sql` y seed completados).
- [ ] Pantalla de login funcionando en la URL pública de Azure.
- [ ] Un intento de registro con datos inválidos (por ejemplo, teléfono con letras) mostrando el mensaje de error en pantalla.
- [ ] Un registro válido completado con éxito (estudiante o libro).
- [ ] Azure Database for PostgreSQL Flexible Server creado, mostrando que la app está conectada (por ejemplo, datos visibles en el catálogo o en el listado de estudiantes).

---

## 14. Instrucciones para encender/apagar recursos

**Para detener el App Service** (deja de cobrar cómputo, no borra la app ni su configuración):
```bash
az webapp stop --resource-group rg-biblioteca-vv --name biblioteca-vv-jaime
```

**Para detener el servidor PostgreSQL Flexible Server** (deja de cobrar cómputo del servidor de base de datos):
```bash
az postgres flexible-server stop --resource-group rg-biblioteca-vv --name biblioteca-vv-db-jaime
```

**Recomendación:** apagar ambos recursos cuando no se estén usando (por ejemplo, entre la entrega y la exposición final) para no consumir crédito de Azure innecesariamente. Un servidor PostgreSQL Flexible Server detenido se reinicia automáticamente solo después de un tiempo límite fijado por Azure si no se enciende manualmente antes; conviene encenderlo con margen de anticipación.

**Orden recomendado para encender antes de la exposición:**
1. **PostgreSQL primero** (`az postgres flexible-server start ...`) — la app necesita la base de datos disponible desde el primer request.
2. **App Service después** (`az webapp start ...`).
3. **Probar login y algunos registros** antes de empezar la exposición, para confirmar que todo responde con margen de tiempo por si algo necesita un reinicio adicional.

---

## 15. Conclusiones

- El sistema de Biblioteca_VV quedó desplegado en Azure App Service (Linux, Python 3.12), con Gunicorn como servidor de producción.
- La base de datos quedó alojada en Azure Database for PostgreSQL Flexible Server, un servicio administrado y separado del entorno de desarrollo local.
- El despliegue quedó automatizado con GitHub Actions: cada `push` a la rama `feature/deploy-azure` dispara un build e implementación automáticos hacia el App Service.
- Se mejoró la calidad y seguridad de los datos del sistema agregando validaciones robustas del lado del servidor (cédula ecuatoriana con dígito verificador, ISBN-13 con dígito verificador, formatos de nombre/correo/teléfono, rangos de fecha y edad), que rechazan datos inválidos sin depender de que el navegador los filtre primero.
- Se agregó soporte para portadas de libros (ver sección 16), mejorando la presentación del catálogo sin afectar el resto del sistema.
- Las pruebas automáticas confirman que estas mejoras no rompieron ninguna funcionalidad existente del sistema (ver el resultado exacto en la sección 16 para la corrida más reciente, que incluye las pruebas de portadas).

---

## 16. Portadas de libros (subida de imágenes)

Agregado después de la primera versión de esta documentación: ahora el bibliotecario puede subir una imagen de portada al registrar un libro, y esa portada se muestra en los catálogos y el detalle del libro.

**Campo nuevo en el modelo:** `Libro.portada_archivo` (`app/models/libros.py`) — cadena de texto opcional (`nullable=True`), guarda la ruta relativa a `app/static/` del archivo (por ejemplo `uploads/portadas/3f9a...c2.png`). Al ser opcional, los libros ya existentes (incluidos los que no tienen portada) siguen funcionando sin ningún cambio.

**Migración:** `migrations/versions/b4f2a1c9e3d7_portada_libro.py` (`flask db upgrade` la aplica junto con las demás).

**Dónde se guardan las imágenes:** localmente, en `app/static/uploads/portadas/`, con un nombre de archivo generado con UUID (no se usa el nombre original que sube el usuario, evitando colisiones y problemas de seguridad con nombres de archivo). Esta carpeta está en `.gitignore` (excepto un `.gitkeep` para que exista en el repositorio); las imágenes reales que suban los usuarios nunca se suben al repositorio.

> **Limitación conocida para producción:** en Azure App Service, el disco donde vive el código de la app puede no persistir de forma confiable entre despliegues (sobre todo si Azure usa "Run From Package"/zip deploy, que puede dejar esa carpeta de solo lectura). Para esta entrega universitaria, el almacenamiento local alcanza para la demo. Para un entorno de producción real, lo recomendado es Azure Blob Storage (subir el archivo ahí y guardar en `portada_archivo` la URL o el nombre del blob en vez de una ruta local). No se implementó Blob Storage en esta entrega porque el proyecto no tenía esa configuración todavía.

**Formatos aceptados:** JPG, JPEG, PNG y WEBP, máximo 2 MB. Se valida en el servidor (no solo en el `accept` del HTML) de dos formas:
1. Extensión del archivo, con `flask_wtf.file.FileAllowed`.
2. Contenido real del archivo: se leen los primeros bytes ("magic numbers") y se comparan con las firmas conocidas de JPEG/PNG/WEBP (`app/portadas.py`), para no confiar solo en la extensión o en el `Content-Type` que manda el navegador, que se pueden falsificar.

Si el archivo no es válido, se muestra el mensaje "La portada debe ser una imagen JPG, PNG o WEBP." Si supera el tamaño máximo, "La imagen no debe superar los 2 MB."

**Vistas donde ahora aparece la portada:**
- Catálogo de libros del estudiante (`estudiante/catalogo.html`): cada libro se muestra como tarjeta con la portada arriba, manteniendo título, categoría, editorial y disponibilidad.
- Detalle de libro del estudiante (`estudiante/libro_detalle.html`): portada más grande junto a los datos del libro.
- Listado de libros del bibliotecario (`bibliotecario/libros_lista.html`): miniatura pequeña en la tabla, sin agrandar el diseño.
- Formulario de registro de libro (`bibliotecario/libros_nuevo.html`): campo para subir la portada.

**Dónde NO se agregó portada, a propósito:** en el formulario de registrar préstamo. Ese formulario busca un libro por ISBN con retroalimentación en texto (AJAX), no tiene una tarjeta o selección visual del libro, así que agregar una imagen ahí no aportaría y complicaría el formulario sin necesidad.

**Placeholder:** los libros sin portada (los ya existentes y los nuevos que se registren sin subir imagen) muestran `app/static/img/book-placeholder.svg`, un ícono simple en los mismos colores institucionales del resto del sistema. La vista nunca se rompe por falta de portada: la lógica de "¿tiene portada o no?" está centralizada en una sola función (`app/portadas.py:url_portada`) y una sola plantilla reutilizable (`shared/_macros.html:portada_libro`).

**Edición de libro:** no se implementó — el sistema no tiene, hasta esta entrega, una pantalla para editar un libro ya registrado (ni siquiera sin portada). Queda pendiente para una entrega futura; no se creó una pantalla de edición nueva para no salirse del alcance de este cambio.

**Archivos modificados/creados por este cambio:**
- `app/models/libros.py` — columna `portada_archivo`.
- `migrations/versions/b4f2a1c9e3d7_portada_libro.py` — migración nueva.
- `app/portadas.py` — módulo nuevo: validación de extensión/tamaño/firma, guardado con nombre único, borrado y helper de URL con placeholder.
- `app/forms.py` — campo `portada` (`FileField`) en `LibroForm`.
- `config.py` — `MAX_CONTENT_LENGTH` (3 MB) como límite global de tamaño de petición.
- `app/__init__.py` — se registra `url_portada` como función global de Jinja.
- `app/controllers/bibliotecario/libros.py` — guarda la portada al registrar un libro; el buscador AJAX de libros ahora incluye `portada_url`.
- `app/controllers/estudiante/catalogo.py` — el buscador AJAX del catálogo también incluye `portada_url`.
- `app/templates/shared/_macros.html` — macro `portada_libro`, reutilizada en las plantillas server-side.
- `app/templates/bibliotecario/libros_nuevo.html`, `libros_lista.html`, `estudiante/catalogo.html`, `estudiante/libro_detalle.html` — muestran la portada.
- `app/static/js/libros_lista.js`, `estudiante_catalogo.js` — las filas/tarjetas generadas por AJAX también incluyen la portada.
- `app/static/css/estilos.css` — clases `.portada-miniatura`, `.portada-catalogo`, `.portada-detalle` para controlar el tamaño en cada vista.
- `app/static/img/book-placeholder.svg` — imagen por defecto.
- `app/static/uploads/portadas/.gitkeep` — mantiene la carpeta en el repositorio sin subir imágenes reales.
- `.gitignore` — excluye el contenido real de `app/static/uploads/portadas/`.
- `tests/test_portadas.py` — pruebas nuevas (ver más abajo).

**Pruebas nuevas (`tests/test_portadas.py`):**
- Registrar un libro sin portada sigue funcionando igual que antes.
- Registrar un libro con una portada válida guarda el libro y la ruta de la portada, y el listado del bibliotecario la muestra sin errores.
- Un archivo con extensión inválida (ej. `.txt`) se rechaza con el mensaje correspondiente, sin crear el libro.
- El formulario de registrar libro renderiza con el campo de portada y `enctype="multipart/form-data"`.
- El catálogo y el detalle del estudiante cargan sin romperse cuando un libro no tiene portada (se ve el placeholder).

**Resultado de `python -m pytest -v` después de este cambio:**

```
38 passed, 36 warnings in 13.10s
```

Las pruebas anteriores a este cambio (33) siguieron pasando sin modificaciones en su lógica; se sumaron 5 pruebas nuevas de portadas.
