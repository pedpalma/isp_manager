# Imagem ÚNICA para api (FastAPI) e worker (Celery).
#
# Três stages:
#   base: sistema + Python + dependências comuns
#   dev: ferramentas de desenvolvimento
#   prod: imagem final

# Base:
FROM python:3.12-slim-bookworm AS base

    # Não gera .pyc
ENV PYTHONDONTWRITEBYTECODE=1 \
    # Logs aparecem imediatamente
    PYTHONUNBUFFERED=1 \
    # Não guarda cache do pip
    PIP_NO_CACHE_DIR=1 \
    # Não fica avisando que existe versão nova
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# Dependências de sistema
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

# Espera o Postgres ficar pronto antes de subir api/worker.
COPY infra/scripts/wait-for-db.sh /usr/local/bin/wait-for-db
RUN chmod +x /usr/local/bin/wait-for-db

# Garante encaminhamento correto de sinais (graceful shutdown).
ENTRYPOINT ["/usr/bin/tini", "--"]


# Dev
FROM base AS dev

# Instala dependências apenas se o lock file existir.
COPY backend/requirements.tx[t] /tmp/requirements.txt
RUN if [ -f /tmp/requirements.txt ]; then \
        pip install -r /tmp/requirements.txt; \
    else \
        echo "[dev] backend/requirements.txt ainda não existe."; \
    fi

USER root

# Prod
FROM base AS prod

# Cria usuário e grupo dedicados (não-root) para rodar a aplicação.
RUN groupadd --system --gid 1000 app \
    && useradd  --system --uid 1000 --gid app --home-dir /app --shell /usr/sbin/nologin app

# Instala dependências congeladas.
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# Copia o código da aplicação.
COPY --chown=app:app backend/ /app/

USER app

# CMD definido pelo orquestrador (compose / Kubernetes / systemd) por serviço.