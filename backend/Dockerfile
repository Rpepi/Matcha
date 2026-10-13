FROM python:3.13-slim

# Dépendances système pour Pillow (images) et psycopg (Postgres)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libjpeg62-turbo-dev \
    libwebp-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /backend

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY . .

RUN mkdir -p /backend/uploads

EXPOSE 5000

# Apply the pending migrations, then start the API: a fresh database is ready
# without any manual step. `exec` makes uvicorn the main process, so it gets the
# stop signal directly.
# --ws-max-size: chat frames above 16 KiB are refused (close code 1009). A
# 1000-character message escaped as \uXXXX pairs is ~12 KiB; uvicorn's
# default is 16 MiB.
# --timeout-graceful-shutdown: open SSE streams would otherwise keep every
# reload and every stop waiting for them forever, so they are cut after 3 s.
CMD ["sh", "-c", "python -m app.db.migrations.runner && exec uvicorn app.wsgi:app --host 0.0.0.0 --port 5000 --ws-max-size 16384 --reload --timeout-graceful-shutdown 3"]
