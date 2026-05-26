# Backend Dockerfile

# Stage 1: base
FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        netcat-openbsd \
        ca-certificates \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Diretório de trabalho da aplicação.
WORKDIR /app

# Atualiza pip e instala pip-tools 
RUN pip install --upgrade pip pip-tools

COPY infra/scripts/wait-for-db.sh /usr/local/bin/wait-for-db
RUN chmod +x /usr/local/bin/wait-for-db

# Garante encaminhamento correto de sinais (graceful shutdown).
ENTRYPOINT ["/usr/bin/tini", "--"]


# Stage 2: dev
FROM base AS dev

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

USER root

FROM base AS prod

RUN groupadd --system --gid 1000 app \
    && useradd  --system --uid 1000 --gid app --home-dir /app --shell /usr/sbin/nologin app

# Instala dependências congeladas.
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# Copia o código da aplicação.
COPY --chown=app:app backend/ /app/

USER app

# CMD definido pelo orquestrador (compose / Kubernetes / systemd) por serviço.