FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: build tools for cryptography, libpq for psycopg, and git for
# checking out target repositories in the worker.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-worker.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# The Celery worker image also installs the Strix engine. The API image skips
# it (leaner, faster builds) by leaving INSTALL_STRIX at its default.
ARG INSTALL_STRIX=false
RUN if [ "$INSTALL_STRIX" = "true" ]; then pip install -r requirements-worker.txt; fi

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
