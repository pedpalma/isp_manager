# Stage 1: base
# Tanto dev quanto prod herdam daqui.
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

WORKDIR /app

# pip-tools fica disponível tanto em dev (recompile) quanto em prod (auditoria).
RUN pip install --upgrade pip pip-tools

# Wait-for-db script utilitário (sem chmod já aplicado no git).
COPY infra/scripts/wait-for-db.sh /usr/local/bin/wait-for-db
RUN chmod +x /usr/local/bin/wait-for-db

# DEPENDÊNCIAS PYTHON
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# tini como PID 1 garante encaminhamento de sinais (graceful shutdown).
ENTRYPOINT ["/usr/bin/tini", "--"]


# Stage 2: dev adiciona ferramentas de desenvolvimento.
# Código vem via bind mount no compose; nada de COPY de app/ aqui.
FROM base AS dev

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        git \
        vim-tiny \
    && rm -rf /var/lib/apt/lists/*

# Em dev rodamos como root para facilitar instalação ad-hoc de pacotes,
# ajustes em arquivos via bind mount, etc. Em prod usamos user não-root.
USER root


# Stage 3: prod imagem enxuta para deploy.
FROM base AS prod

# User não-root para reduzir blast radius em caso de RCE.
RUN groupadd --system --gid 1000 app \
    && useradd  --system --uid 1000 --gid app --home-dir /app --shell /usr/sbin/nologin app

# Copia o código da aplicação (sem bind mount em prod).
COPY --chown=app:app backend/ /app/

USER app

# CMD final é definido pelo orquestrador (compose/Kubernetes) por serviço.
# Exemplo para api: uvicorn app.main:app --host 0.0.0.0 --port 8000
# Exemplo para worker: celery -A app.celery_app worker --loglevel=INFO