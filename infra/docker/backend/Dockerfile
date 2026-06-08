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

# DEPENDÊNCIAS PYTHON (PROD)
# O estágio base instala APENAS o que vai para produção. O estágio dev acrescenta
# as deps de teste/lint em cima disso, sem poluir a imagem de prod.
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

# DEPENDÊNCIAS PYTHON (DEV)
# requirements-dev.txt é o lock COMPLETO (prod + extras de dev), gerado por
# pip-compile sobre requirements-dev.in (que faz "-r requirements.in").
# Reinstalar sobre o que já veio do base é seguro e idempotente: pip detecta
# o que já está satisfeito e instala somente os extras (pytest, pytest-asyncio,
# factory-boy, httpx, ...). Resultado: imagem de dev tem tudo; imagem de prod
# permanece enxuta.
#
# Esse passo precisa rodar no BUILD (não em runtime). O bind mount
# ./backend:/app no compose sobrescreve /app, mas as deps vivem em
# site-packages do sistema, fora de /app, portanto não são afetadas.
COPY backend/requirements-dev.txt /tmp/requirements-dev.txt
RUN pip install -r /tmp/requirements-dev.txt

# Sanity check: falha o build se o lock estiver inconsistente com a imagem.
# Custa milissegundos e evita o sintoma de "pytest sumiu" reaparecer no futuro.
RUN python -c "import pytest, pytest_asyncio, factory, httpx"

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
