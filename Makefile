# Makefile isp_manager

# Shell explícito.
SHELL := /bin/zsh

COMPOSE := docker compose

# Serviços nomeados.
SERVICE_API      := api
SERVICE_WORKER   := worker
SERVICE_FRONTEND := frontend
SERVICE_DB       := postgres
SERVICE_REDIS    := redis

# Arquivos .env e .env.example.
ENV_FILE         := .env
ENV_EXAMPLE      := .env.example

# Cores para output.
COLOR_RESET  := \033[0m
COLOR_BOLD   := \033[1m
COLOR_GREEN  := \033[32m
COLOR_YELLOW := \033[33m
COLOR_RED    := \033[31m
COLOR_CYAN   := \033[36m

# Alvo default quando rodar `make` sem argumentos.
.DEFAULT_GOAL := help

# HELP

.PHONY: help
help: ## Lista todos os comandos disponíveis
	@echo ""
	@echo "$(COLOR_BOLD)isp_manager comandos disponíveis$(COLOR_RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(COLOR_CYAN)%-22s$(COLOR_RESET) %s\n", $$1, $$2}' | \
		sort
	@echo ""

# SETUP INICIAL

.PHONY: setup
setup: ## Configuração inicial do projeto (primeira vez)
	@echo "$(COLOR_BOLD)Configurando isp_manager...$(COLOR_RESET)"
	@$(MAKE) check-deps
	@$(MAKE) env-init
	@$(MAKE) build
	@echo ""
	@echo "$(COLOR_GREEN) ✓ Setup concluído!$(COLOR_RESET)"
	@echo ""
	@echo "Próximos passos:"
	@echo "  1. Revise o arquivo $(COLOR_YELLOW).env$(COLOR_RESET) e ajuste senhas"
	@echo "  2. Rode $(COLOR_CYAN)make up$(COLOR_RESET) para iniciar os serviços"
	@echo "  3. Rode $(COLOR_CYAN)make migrate$(COLOR_RESET) para aplicar migrations"
	@echo ""

.PHONY: check-deps
check-deps: ## Verifica se dependências do host estão instaladas
	@echo "Verificando dependências..."
	@command -v docker >/dev/null 2>&1 || { echo "$(COLOR_RED) ✗ docker não encontrado$(COLOR_RESET)"; exit 1; }
	@docker compose version >/dev/null 2>&1 || { echo "$(COLOR_RED) ✗ docker compose v2 não encontrado$(COLOR_RESET)"; exit 1; }
	@command -v git >/dev/null 2>&1 || { echo "$(COLOR_RED) ✗ git não encontrado$(COLOR_RESET)"; exit 1; }
	@echo "$(COLOR_GREEN) ✓ Dependências OK$(COLOR_RESET)"

.PHONY: env-init
env-init: ## Cria .env a partir do .env.example (se não existir)
	@if [ ! -f $(ENV_FILE) ]; then \
		cp $(ENV_EXAMPLE) $(ENV_FILE); \
		echo "$(COLOR_GREEN) ✓ Criado $(ENV_FILE)$(COLOR_RESET)"; \
		echo "$(COLOR_YELLOW) ⚠ Edite $(ENV_FILE) e ajuste senhas antes de subir o ambiente.$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_YELLOW) ⚠ $(ENV_FILE) já existe não sobrescrito.$(COLOR_RESET)"; \
	fi

.PHONY: secret
secret: ## Gera uma chave aleatória segura (use para API_SECRET_KEY)
	@openssl rand -hex 32


# CICLO DE VIDA DOS CONTAINERS

.PHONY: up
up: ## Sobe todos os serviços em background
	@$(COMPOSE) up -d
	@echo ""
	@echo "$(COLOR_GREEN) ✓ Serviços iniciados$(COLOR_RESET)"
	@echo "  API:      http://localhost:8000"
	@echo "  Docs:     http://localhost:8000/docs"
	@echo "  Frontend: http://localhost:3000"

.PHONY: up-fg
up-fg: ## Sobe todos os serviços em primeiro plano (logs ao vivo, Ctrl+C para parar)
	@$(COMPOSE) up

.PHONY: down
down: ## Para todos os serviços (preserva volumes)
	@$(COMPOSE) down

.PHONY: restart
restart: down up ## Reinicia todos os serviços

.PHONY: restart-api
restart-api: ## Reinicia apenas a API
	@$(COMPOSE) restart $(SERVICE_API)

.PHONY: restart-worker
restart-worker: ## Reinicia apenas o worker Celery
	@$(COMPOSE) restart $(SERVICE_WORKER)

.PHONY: ps
ps: ## Lista status dos containers
	@$(COMPOSE) ps

.PHONY: stop
stop: ## Para containers sem removê-los
	@$(COMPOSE) stop

.PHONY: start
start: ## Inicia containers parados (sem rebuild)
	@$(COMPOSE) start


# BUILD

.PHONY: build
build: ## Builda todas as imagens (usa cache)
	@$(COMPOSE) build

.PHONY: rebuild
rebuild: ## Rebuild forçado sem cache (use após mudar Dockerfile ou deps)
	@$(COMPOSE) build --no-cache

.PHONY: pull
pull: ## Atualiza imagens base do registry
	@$(COMPOSE) pull


# LOGS

.PHONY: logs
logs: ## Logs de todos os serviços (follow)
	@$(COMPOSE) logs -f --tail=100

.PHONY: logs-api
logs-api: ## Logs apenas da API
	@$(COMPOSE) logs -f --tail=200 $(SERVICE_API)

.PHONY: logs-worker
logs-worker: ## Logs apenas do worker Celery
	@$(COMPOSE) logs -f --tail=200 $(SERVICE_WORKER)

.PHONY: logs-frontend
logs-frontend: ## Logs apenas do frontend
	@$(COMPOSE) logs -f --tail=200 $(SERVICE_FRONTEND)

.PHONY: logs-db
logs-db: ## Logs apenas do Postgres
	@$(COMPOSE) logs -f --tail=200 $(SERVICE_DB)

.PHONY: logs-json
logs-json: ## Logs JSON puros de api e worker (sem prefixo, filtrados, prontos para jq)
	@command -v jq >/dev/null 2>&1 || { echo "$(COLOR_RED) ✗ jq não encontrado no host. Instale: apt install jq (ou brew install jq).$(COLOR_RESET)"; exit 1; }
	@$(COMPOSE) logs -f --no-log-prefix --tail=100 $(SERVICE_API) $(SERVICE_WORKER) \
		| grep --line-buffered '^{' \
		| jq -c .


# ACESSO INTERATIVO (shells)

.PHONY: shell-api
shell-api: ## Bash dentro do container da API
	@$(COMPOSE) exec $(SERVICE_API) bash

.PHONY: shell-worker
shell-worker: ## Bash dentro do container do worker
	@$(COMPOSE) exec $(SERVICE_WORKER) bash

.PHONY: shell-frontend
shell-frontend: ## Bash dentro do container do frontend
	@$(COMPOSE) exec $(SERVICE_FRONTEND) sh

.PHONY: shell-db
shell-db: ## Console psql conectado ao banco como role da aplicação
	@$(COMPOSE) exec $(SERVICE_DB) psql -U $${ISP_APP_DB_USER:-isp_app} -d $${POSTGRES_DB:-isp_manager}

.PHONY: shell-db-root
shell-db-root: ## Console psql como superuser (use com cuidado)
	@$(COMPOSE) exec $(SERVICE_DB) psql -U $${POSTGRES_SUPERUSER:-postgres} -d $${POSTGRES_DB:-isp_manager}

.PHONY: shell-redis
shell-redis: ## redis-cli conectado ao Redis
	@$(COMPOSE) exec $(SERVICE_REDIS) redis-cli

.PHONY: python
python: ## Abre REPL Python dentro da API (com app carregada)
	@$(COMPOSE) exec $(SERVICE_API) python


# HEALTHCHECK

.PHONY: health
health: ## Testa endpoints de saúde da API
	@echo "$(COLOR_BOLD)Liveness:$(COLOR_RESET)"
	@curl -fsS http://localhost:8000/health | python3 -m json.tool || echo "$(COLOR_RED)API down$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_BOLD)Readiness (DB):$(COLOR_RESET)"
	@curl -fsS http://localhost:8000/health/db | python3 -m json.tool || echo "$(COLOR_RED)DB unavailable$(COLOR_RESET)"


# MIGRATIONS (Alembic)

.PHONY: migrate
migrate: ## Aplica todas as migrations pendentes
	@$(COMPOSE) exec $(SERVICE_API) alembic upgrade head

.PHONY: migrate-down
migrate-down: ## Reverte a última migration (CUIDADO em produção)
	@$(COMPOSE) exec $(SERVICE_API) alembic downgrade -1

.PHONY: migration
migration: ## Cria nova migration. Uso: make migration m="descrição"
	@if [ -z "$(m)" ]; then \
		echo "$(COLOR_RED) ✗ Faltou a mensagem. Use: make migration m=\"descrição\"$(COLOR_RESET)"; \
		exit 1; \
	fi
	@$(COMPOSE) exec $(SERVICE_API) alembic revision --autogenerate -m "$(m)"

.PHONY: migration-empty
migration-empty: ## Cria migration vazia (para SQL raw). Uso: make migration-empty m="descrição"
	@if [ -z "$(m)" ]; then \
		echo "$(COLOR_RED) ✗ Faltou a mensagem. Use: make migration-empty m=\"descrição\"$(COLOR_RESET)"; \
		exit 1; \
	fi
	@$(COMPOSE) exec $(SERVICE_API) alembic revision -m "$(m)"

.PHONY: migration-status
migration-status: ## Mostra revisão atual e migrations pendentes
	@$(COMPOSE) exec $(SERVICE_API) alembic current
	@echo ""
	@$(COMPOSE) exec $(SERVICE_API) alembic history --indicate-current


# BANCO DE DADOS utilitários

.PHONY: db-dump
db-dump: ## Faz dump do banco para arquivo (./backups/dump_TIMESTAMP.sql.gz)
	@mkdir -p backups
	@TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	$(COMPOSE) exec -T $(SERVICE_DB) pg_dump -U $${POSTGRES_SUPERUSER:-postgres} -d $${POSTGRES_DB:-isp_manager} | gzip > backups/dump_$$TIMESTAMP.sql.gz; \
	echo "$(COLOR_GREEN) ✓ Dump salvo em backups/dump_$$TIMESTAMP.sql.gz$(COLOR_RESET)"

.PHONY: db-reset
db-reset: ## DESTRUTIVO: apaga e recria o banco vazio
	@echo "$(COLOR_RED) ⚠ Isso vai APAGAR todos os dados do banco.$(COLOR_RESET)"
	@read -p "Digite 'sim' para confirmar: " confirm; \
	if [ "$$confirm" = "sim" ]; then \
		$(COMPOSE) down -v; \
		$(COMPOSE) up -d $(SERVICE_DB); \
		echo "$(COLOR_YELLOW)Aguardando Postgres ficar pronto...$(COLOR_RESET)"; \
		sleep 5; \
		$(MAKE) up; \
		sleep 3; \
		$(MAKE) migrate; \
		echo "$(COLOR_GREEN) ✓ Banco resetado.$(COLOR_RESET)"; \
	else \
		echo "Cancelado."; \
	fi

.PHONY: db-seed
db-seed: ## Popula banco com dados de seed (fabricantes, grupos)
	@$(COMPOSE) exec $(SERVICE_API) python -m scripts.seed_db


# TESTES E QUALIDADE

.PHONY: test
test: ## Roda toda a suíte de testes (unit + integration + e2e)
	@$(COMPOSE) exec $(SERVICE_API) pytest

.PHONY: test-unit
test-unit: ## Roda apenas testes unitários
	@$(COMPOSE) exec $(SERVICE_API) pytest tests/unit

.PHONY: test-integration
test-integration: ## Roda apenas testes de integração
	@$(COMPOSE) exec $(SERVICE_API) pytest tests/integration

.PHONY: test-e2e
test-e2e: ## Roda apenas testes end-to-end
	@$(COMPOSE) exec $(SERVICE_API) pytest tests/e2e

.PHONY: test-cov
test-cov: ## Roda testes com relatório de cobertura
	@$(COMPOSE) exec $(SERVICE_API) pytest --cov=app --cov-report=term-missing --cov-report=html

.PHONY: lint
lint: ## Roda linters (ruff + mypy) no backend
	@$(COMPOSE) exec $(SERVICE_API) ruff check app
	@$(COMPOSE) exec $(SERVICE_API) mypy app

.PHONY: format
format: ## Formata código (ruff format) no backend
	@$(COMPOSE) exec $(SERVICE_API) ruff format app
	@$(COMPOSE) exec $(SERVICE_API) ruff check --fix app

.PHONY: lint-frontend
lint-frontend: ## Roda lint no frontend
	@$(COMPOSE) exec $(SERVICE_FRONTEND) npm run lint


# DEPENDÊNCIAS (pip-tools)

.PHONY: deps-compile
deps-compile: ## Recompila requirements.txt a partir de requirements.in
	@$(COMPOSE) exec $(SERVICE_API) pip-compile requirements.in --output-file requirements.txt
	@$(COMPOSE) exec $(SERVICE_API) pip-compile requirements-dev.in --output-file=requirements-dev.txt

.PHONY: deps-upgrade
deps-upgrade: ## Atualiza todas as dependências para versões mais recentes
	@$(COMPOSE) exec $(SERVICE_API) pip-compile --upgrade requirements.in --output-file requirements.txt

.PHONY: deps-sync
deps-sync: ## Sincroniza site-packages com requirements.txt (dentro do container)
	@$(COMPOSE) exec $(SERVICE_API) pip-sync requirements.txt


# WORKER E TAREFAS

.PHONY: worker-inspect
worker-inspect: ## Lista tasks ativas no worker
	@$(COMPOSE) exec $(SERVICE_WORKER) celery -A app.celery_app inspect active

.PHONY: worker-purge
worker-purge: ## Limpa fila do Celery (CUIDADO: descarta tarefas pendentes)
	@$(COMPOSE) exec $(SERVICE_WORKER) celery -A app.celery_app purge -f


# LIMPEZA

.PHONY: clean
clean: ## Para containers e remove volumes anônimos
	@$(COMPOSE) down --remove-orphans

.PHONY: clean-all
clean-all: ## DESTRUTIVO: para tudo, remove volumes nomeados e imagens
	@echo "$(COLOR_RED) ⚠ Isso vai apagar volumes (incluindo banco) e imagens.$(COLOR_RESET)"
	@read -p "Digite 'sim' para confirmar: " confirm; \
	if [ "$$confirm" = "sim" ]; then \
		$(COMPOSE) down -v --remove-orphans --rmi local; \
		echo "$(COLOR_GREEN) ✓ Limpeza completa.$(COLOR_RESET)"; \
	else \
		echo "Cancelado."; \
	fi

.PHONY: prune
prune: ## Remove containers/imagens/volumes do Docker NÃO usados (sistema todo)
	@docker system prune -f


# INFORMAÇÕES

.PHONY: info
info: ## Mostra informações úteis do ambiente
	@echo ""
	@echo "$(COLOR_BOLD)isp_manager info do ambiente$(COLOR_RESET)"
	@echo ""
	@echo "  Docker:         $$(docker --version)"
	@echo "  Compose:        $$(docker compose version --short)"
	@echo "  Git branch:     $$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'não é repo git')"
	@echo "  Git commit:     $$(git rev-parse --short HEAD 2>/dev/null || echo 'sem commits')"
	@echo "  .env existe:    $$([ -f $(ENV_FILE) ] && echo 'sim' || echo 'NÃO')"
	@echo ""
	@$(COMPOSE) ps
	@echo ""

.PHONY: version
version: ## Mostra versão da aplicação
	@$(COMPOSE) exec $(SERVICE_API) python -c "from app.core.config import settings; print(settings.app.app_version)" 2>/dev/null || echo "API não está rodando"
