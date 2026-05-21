# OSS-ISP

Sistema OSS/BSS para provedor de internet. Substitui UNM2000 e NetNumen.

## Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Celery
- **Banco:** PostgreSQL 16
- **Cache/Broker:** Redis 7
- **Cofre:** HashiCorp Vault
- **Frontend:** Next.js 15 (App Router), React 19, Tailwind, shadcn/ui
- **Infra:** Docker Compose em Proxmox

## Estrutura

```
backend/    API FastAPI + worker Celery (mesma base de código)
frontend/   App Next.js
infra/      Dockerfiles, scripts, nginx, backups
docs/       ADRs e runbooks operacionais
```

## Começando

```bash
cp .env.example .env
make up         # sobe tudo
make migrate    # aplica migrações
make seed       # popula dados iniciais
```

API: http://localhost:8000/docs
Frontend: http://localhost:3000

## Comandos úteis

```bash
make up          # docker compose up -d
make down        # docker compose down
make logs        # logs de todos os serviços
make migrate     # alembic upgrade head
make migration   # alembic revision --autogenerate
make test        # pytest no backend
make lint        # ruff + mypy
make shell-api   # bash no container da API
make shell-db    # psql no postgres
```

## Documentação

- `docs/architecture/` — decisões arquiteturais (ADRs)
- `docs/runbooks/` — procedimentos operacionais
