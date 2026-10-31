FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    DEBCONF_NONINTERACTIVE_SEEN=true

WORKDIR /app

# Системные пакеты и Chromium не зависят от кода. Обновление Layla их не перекачивает.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates proxychains4 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir 'playwright>=1.49' \
    && playwright install --with-deps chromium

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

EXPOSE 8000

# Run migrations then start the API.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
