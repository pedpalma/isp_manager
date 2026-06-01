#!/usr/bin/env bash
# Inicialização do cluster Postgres do ISP Manager.
set -euo pipefail

# Variáveis obrigatórias; falha rápido se faltar qualquer uma.
: "${POSTGRES_USER:?POSTGRES_USER precisa estar definido}"
: "${POSTGRES_DB:?POSTGRES_DB precisa estar definido}"
: "${ISP_APP_DB_USER:?ISP_APP_DB_USER precisa estar definido}"
: "${ISP_APP_DB_PASSWORD:?ISP_APP_DB_PASSWORD precisa estar definido}"
: "${ISP_MIGRATOR_DB_USER:?ISP_MIGRATOR_DB_USER precisa estar definido}"
: "${ISP_MIGRATOR_DB_PASSWORD:?ISP_MIGRATOR_DB_PASSWORD precisa estar definido}"

echo "[init.sh] Configurando roles e database do ISP Manager..."

# Etapa 1: roles + database + dono. Conectado ao database de manutenção "postgres".
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
	-- Roles idempotentes (não falham se já existirem; \$\$ é o dollar-quoting
	-- do PL/pgSQL, escapado para o bash não o interpretar como PID).
	DO \$\$
	BEGIN
	    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${ISP_MIGRATOR_DB_USER}') THEN
	        -- Role do Alembic: cria/altera/exclui schema. NUNCA usado pela API.
	        -- Em dev, CREATEDB facilita testes; em prod, remover.
	        CREATE ROLE ${ISP_MIGRATOR_DB_USER} WITH LOGIN CREATEDB PASSWORD '${ISP_MIGRATOR_DB_PASSWORD}';
	    END IF;

	    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${ISP_APP_DB_USER}') THEN
	        -- Role de runtime: SEM CREATEDB, CREATEROLE ou SUPERUSER.
	        CREATE ROLE ${ISP_APP_DB_USER} WITH LOGIN PASSWORD '${ISP_APP_DB_PASSWORD}';
	    END IF;
	END
	\$\$;

	-- Cria o database SOMENTE se ainda não existir (o entrypoint pode tê-lo
	-- criado via POSTGRES_DB). CREATE DATABASE não roda dentro de transação,
	-- por isso usamos o truque do \gexec: a SELECT gera o comando e o \gexec o executa.
	SELECT format('CREATE DATABASE %I OWNER %I', '${POSTGRES_DB}', '${ISP_MIGRATOR_DB_USER}')
	WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${POSTGRES_DB}')
	\gexec

	-- Garante o dono correto, tenha o database sido criado aqui ou pelo entrypoint.
	-- É ESTA linha que dá ao isp_migrator o CREATE no schema public.
	ALTER DATABASE ${POSTGRES_DB} OWNER TO ${ISP_MIGRATOR_DB_USER};

	-- isp_app apenas conecta; o DML vem por default privileges (Etapa 2).
	GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO ${ISP_APP_DB_USER};
EOSQL

# Etapa 2: permissões do runtime. Conectado ao database da aplicação.
# Default privileges valem por (role criador, schema), então rodam aqui dentro.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "${POSTGRES_DB}" <<-EOSQL
	-- Uso do schema public pelo runtime (necessário para SELECT/INSERT/etc).
	GRANT USAGE ON SCHEMA public TO ${ISP_APP_DB_USER};

	-- Tudo que o isp_migrator criar em "public" já nasce com DML para o isp_app.
	-- (UPDATE/DELETE em audit_log é REVOGADO explicitamente na migration 0001.)
	ALTER DEFAULT PRIVILEGES FOR ROLE ${ISP_MIGRATOR_DB_USER} IN SCHEMA public
	    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ${ISP_APP_DB_USER};

	-- Sequences (o BIGSERIAL de event_queue usa; UUID não).
	ALTER DEFAULT PRIVILEGES FOR ROLE ${ISP_MIGRATOR_DB_USER} IN SCHEMA public
	    GRANT USAGE, SELECT ON SEQUENCES TO ${ISP_APP_DB_USER};

	-- Funções criadas pelo migrator precisam ser executáveis pelo runtime.
	ALTER DEFAULT PRIVILEGES FOR ROLE ${ISP_MIGRATOR_DB_USER} IN SCHEMA public
	    GRANT EXECUTE ON FUNCTIONS TO ${ISP_APP_DB_USER};
EOSQL

echo "[init.sh] Pronto. Roles e database configurados."
echo "[init.sh]   Database:     ${POSTGRES_DB}"
echo "[init.sh]   Owner:        ${ISP_MIGRATOR_DB_USER} (Alembic/DDL)"
echo "[init.sh]   Runtime user: ${ISP_APP_DB_USER}"