# ==> Atalhos para tarefas comuns de desenvolvimento.

# Carrega o .env (se existir) e exporta as variáveis pros sub-comandos
ifneq (,$(wildcard ./.env))
	include .env
	export
endif

COMPOSE := docker compose

.DEFAULT_GOAL := help

# --> Help <--

.PHONY: help
# Lista todos os comandos disponíveis
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'


# --> Setup inicial <--
.PHONY: init
# Cria .env a partir do exemplo (se não existir)
init:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Archive .env created from .env.example."; \
	else \
		echo ".env already exists. Nothing made."; \
	fi


# --> Lifecycle dos containers <--
.PHONY: build
# Builda as imagens
build:
	$(COMPOSE) build

.PHONY: up
# Sobe todos os serviços em background
up:
	$(COMPOSE) up -d

.PHONY: up-fg
# Sobe todos os serviços em foreground (logs na tela)
up-fg:
	$(COMPOSE) up

.PHONY: down
# Para e remove os containers (mantém volumes)
down:
	$(COMPOSE) down

.PHONY: down-volumes
# Para e remove containers + volumes
down-volumes:
	$(COMPOSE) down -v

.PHONY: restart
#  Reinicia todos os serviços
restart:
	$(COMPOSE) restart

# Mostra status dos containers.PHONY: ps
ps:
	$(COMPOSE) ps


# --> Logs <--
.PHONY: logs
# Logs de todos os serviços (follow)
logs:
	$(COMPOSE) logs -f --tail=100

.PHONY: logs-api
# Logs da API
logs-api:
	$(COMPOSE) logs -f --tail=100 api

.PHONY: logs-worker
# Logs do worker
logs-worker:
	$(COMPOSE) logs -f --tail=100 worker

.PHONY: logs-db
# Logs do Postgres
logs-db:
	$(COMPOSE) logs -f --tail=100 postgres


# --> Shell <--
.PHONY: shell-api
# Abre shell dentro do container da API
shell-api:
	$(COMPOSE) exec api bash

.PHONY: shell-worker
# Abre shell dentro do container do worker
shell-worker:
	$(COMPOSE) exec worker bash

.PHONY: shell-db
# Abre psql no Postgres
shell-db:
	$(COMPOSE) exec postgres psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)


# --> Banco / Migrations <--
.PHONY: migrate
# Aplica migrations pendentes
migrate:
	$(COMPOSE) exec api alembic upgrade head

.PHONY: migrate-down
# Reverte a última migration
migrate-down:
	$(COMPOSE) exec api alembic downgrade -1

.PHONY: migration
# Cria nova migration (make migration name="add_xxx")
migration:
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(name)"


# --> Diagnóstico <--
.PHONY: health
# Testa o endpoint /health da API
health:
	@curl -fsS http://localhost:8000/health | jq . || echo "API não respondeu"

.PHONY: ping-olt
# Testa conectividade do container da API com uma OLT (make ping-olt ip=10.0.0.1)
ping-olt:
	$(COMPOSE) exec api ping -c 3 $(ip)