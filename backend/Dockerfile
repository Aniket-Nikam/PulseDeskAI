FROM python:3.12-slim

WORKDIR /app

# System dependencies for psycopg2/asyncpg native builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Remove local .env so Docker env vars take precedence
RUN rm -f .env

# Create required directories
RUN mkdir -p ./screenshots ./logs

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level info"]
