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

CMD ["uvicorn", "app.wsgi:app", "--host", "0.0.0.0", "--port", "5000", "--reload"]
