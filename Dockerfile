# Replica del contenedor manual "biblio-app" (python:3.12-slim).
# El codigo se monta con bind en docker-compose.yml para desarrollo con
# recarga; la imagen tambien lleva una copia para poder arrancar sin montaje.
FROM python:3.12-slim

# Cliente PostgreSQL: lo usa docker-entrypoint.sh para esperar la BD (pg_isready)
# y aplicar database/setup.sql. Sin dependencias de compilacion.
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

# Dependencias primero para aprovechar la cache de capas.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x docker-entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["python", "-m", "flask", "--app", "run.py", "run", "--host=0.0.0.0", "--port=5000"]
