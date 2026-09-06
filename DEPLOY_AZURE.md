# Despliegue en Azure App Service (Python/Linux) + Azure Database for PostgreSQL

Guía práctica para desplegar Biblioteca_VV en Azure hoy mismo. Usa Azure CLI
(`az`); todos los comandos son de referencia, ajusta nombres y región.

## 0. Prerrequisitos

- Azure CLI instalado y logueado: `az login`.
- Código en una rama que vayas a desplegar (esta guía asume que ya tienes
  `requirements.txt` con `gunicorn` y `run.py` exponiendo `app = create_app()`,
  ambos ya listos en esta rama).

## 1. Grupo de recursos

```bash
az group create --name rg-biblioteca-vv --location eastus
```

## 2. Azure Database for PostgreSQL Flexible Server

```bash
az postgres flexible-server create \
  --resource-group rg-biblioteca-vv \
  --name biblioteca-vv-db \
  --location eastus \
  --admin-user bibliotecaadmin \
  --admin-password "<PON_UNA_CONTRASENA_SEGURA>" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 32 \
  --version 16 \
  --public-access 0.0.0.0-255.255.255.255
```

> `--public-access 0.0.0.0-255.255.255.255` abre el firewall a cualquier IP
> para desplegar rápido. Es la opción menos segura; restringe el firewall en
> cuanto puedas (ver paso 9).

Crear la base de datos de la aplicación:

```bash
az postgres flexible-server db create \
  --resource-group rg-biblioteca-vv \
  --server-name biblioteca-vv-db \
  --database-name biblioteca_vv
```

Tu cadena de conexión queda así (anótala, la usas en el paso 4):

```
postgresql://bibliotecaadmin:<PASSWORD>@biblioteca-vv-db.postgres.database.azure.com:5432/biblioteca_vv?sslmode=require
```

## 3. App Service (Python/Linux)

```bash
az appservice plan create \
  --resource-group rg-biblioteca-vv \
  --name plan-biblioteca-vv \
  --is-linux \
  --sku B1

az webapp create \
  --resource-group rg-biblioteca-vv \
  --plan plan-biblioteca-vv \
  --name biblioteca-vv-app \
  --runtime "PYTHON:3.12"
```

`biblioteca-vv-app` debe ser un nombre único en todo Azure (aparece en la URL
`https://biblioteca-vv-app.azurewebsites.net`); cámbialo si ya está tomado.

## 4. Variables de entorno (App Settings)

```bash
az webapp config appsettings set \
  --resource-group rg-biblioteca-vv \
  --name biblioteca-vv-app \
  --settings \
    FLASK_ENV=production \
    SECRET_KEY="<GENERA_UNA_CON_secrets.token_hex_32>" \
    DATABASE_URL="postgresql://bibliotecaadmin:<PASSWORD>@biblioteca-vv-db.postgres.database.azure.com:5432/biblioteca_vv?sslmode=require" \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

Genera `SECRET_KEY` localmente antes de correr el comando:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Notas:
- No configures `TEST_DATABASE_URL` aquí — solo lo usa `pytest`, nunca la app en producción.
- `SCM_DO_BUILD_DURING_DEPLOYMENT=true` hace que Azure instale `requirements.txt` automáticamente al desplegar (incluye `gunicorn`).

## 5. Startup command

```bash
az webapp config set \
  --resource-group rg-biblioteca-vv \
  --name biblioteca-vv-app \
  --startup-file "gunicorn --bind=0.0.0.0 --timeout 600 run:app"
```

`run:app` funciona porque `run.py` define `app = create_app()` a nivel de módulo.

## 6. Desplegar el código

Opción rápida con Git local:

```bash
az webapp deployment source config-local-git \
  --resource-group rg-biblioteca-vv \
  --name biblioteca-vv-app

# el comando anterior imprime una URL tipo:
# https://<usuario>@biblioteca-vv-app.scm.azurewebsites.net/biblioteca-vv-app.git
git remote add azure <ESA_URL>
git push azure feature/deploy-azure:master
```

Cualquier otro método de despliegue (GitHub Actions, `az webapp up`, Zip Deploy)
sirve igual, siempre que las App Settings y el startup command ya estén
configurados como en los pasos 4 y 5.

## 7. Inicializar la base de datos (una sola vez)

Con `DATABASE_URL` apuntando ya a Azure (puedes exportarla localmente o entrar
por SSH al App Service, ver abajo):

```bash
python -m scripts.init_azure_db
```

Esto, en orden:
1. Corre las migraciones (`flask db upgrade`, vía la API de Flask-Migrate).
2. Aplica `database/setup.sql` (índices, funciones, triggers, vistas) — se
   salta automáticamente si detecta que ya se aplicó antes.
3. Carga los datos semilla (`database/seed.py`) — también es seguro
   re-ejecutarlo, no duplica datos.

Alternativa manual paso a paso, si prefieres no usar el script:

```bash
flask --app run.py db upgrade
psql "postgresql://bibliotecaadmin:<PASSWORD>@biblioteca-vv-db.postgres.database.azure.com:5432/biblioteca_vv?sslmode=require" -f database/setup.sql
python -m database.seed
```

Para ejecutar esto DESDE DENTRO del App Service (útil si tu red local no
tiene salida directa a Postgres, o si el firewall de la base solo permite
servicios de Azure):

```bash
az webapp ssh --resource-group rg-biblioteca-vv --name biblioteca-vv-app
# ya dentro de la consola SSH del contenedor:
python -m scripts.init_azure_db
```

## 8. Verificar

- Abre `https://biblioteca-vv-app.azurewebsites.net/login`.
- Entra con los usuarios sembrados (`gerente`/`Gerente`, `bibliotecario`/`Biblio`,
  `estudiante`/`Estudiante`) y **cámbiales la contraseña de inmediato** si esto
  deja de ser solo una prueba.
- Si algo falla, revisa logs en vivo:

```bash
az webapp log tail --resource-group rg-biblioteca-vv --name biblioteca-vv-app
```

## 9. Pendientes de seguridad después del despliegue rápido de hoy

- Restringir el firewall de PostgreSQL a la IP saliente del App Service en vez
  de `0.0.0.0-255.255.255.255`:
  ```bash
  az webapp show --resource-group rg-biblioteca-vv --name biblioteca-vv-app --query outboundIpAddresses -o tsv
  ```
  y crear una regla de firewall en el servidor Postgres solo para esas IPs.
- Cambiar las contraseñas de los usuarios sembrados por defecto.
- Revisar cookies seguras / HTTPS-only en el App Service (Azure ya fuerza
  HTTPS en el dominio `azurewebsites.net` por defecto).
- Considerar Azure Key Vault para `SECRET_KEY` y la contraseña de Postgres en
  vez de dejarlas como texto plano en App Settings.
