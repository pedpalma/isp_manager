#!/usr/bin/env bash
# Responsabilidades:
#   1. Criar role isp_migrator (dono do schema, usado pelo Alembic).
#   2. Criar role isp_app (runtime da aplicação, permissões mínimas).
#   3. Criar o database isp_manager pertencente a isp_migrator.
#   4. Conceder permissões iniciais.

set -euo pipefail

# Variáveis obrigatórias, falha rápido se faltar qualquer uma.
: "${POSTGRES_DB:?POSTGRES_DB precisa estar definido}"
: "${ISP_APP_DB_USER:?ISP_APP_DB_USER precisa estar definido}"
: "${ISP_APP_DB_PASSWORD:?ISP_APP_DB_PASSWORD precisa estar definido}"
: "${ISP_MIGRATOR_DB_USER:?ISP_MIGRATOR_DB_USER precisa estar definido}"
: "${ISP_MIGRATOR_DB_PASSWORD:?ISP_MIGRATOR_DB_PASSWORD precisa estar definido}"

echo "[init.sh] Criando roles e database do ISP Manager..."

# Usa o superusuário padrão (postgres) para criar os roles da aplicação.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
    -- Role do Alembic: pode criar/alterar/excluir schema. NUNCA é usado pela API.
    -- Em dev: CREATEDB facilita testes (criar bancos temporários). Em prod: remover.
    CREATE ROLE ${ISP_MIGRATOR_DB_USER}
        WITH LOGIN
             CREATEDB
             PASSWORD '${ISP_MIGRATOR_DB_PASSWORD}';

    -- Role de runtime: SEM CREATEDB, SEM CREATEROLE, SEM SUPERUSER.
    -- Permissões em tabelas vêm na migration inicial.
    CREATE ROLE ${ISP_APP_DB_USER}
        WITH LOGIN
             PASSWORD '${ISP_APP_DB_PASSWORD}';

    -- Database de trabalho, pertencente ao migrator (que vai criar o schema).
    CREATE DATABASE ${POSTGRES_DB} OWNER ${ISP_MIGRATOR_DB_USER};

    -- Permite que isp_app se conecte ao database.
    -- Permissões granulares em tabelas/sequences serão concedidas pelo Alembic
    -- (na 0001_initial_schema.py, após CREATE TABLE).
    GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO ${ISP_APP_DB_USER};
EOSQL

# Garante que objetos criados por isp_migrator no schema public fiquem acessíveis para isp_app via "default privileges".
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "${POSTGRES_DB}" <<-EOSQL
    -- Concede uso do schema public ao runtime (necessário para SELECT/INSERT).
    GRANT USAGE ON SCHEMA public TO ${ISP_APP_DB_USER};

    -- Default privileges: tudo que isp_migrator criar no futuro em "public"
    -- já nasce com SELECT/INSERT/UPDATE/DELETE para isp_app.
    -- (UPDATE/DELETE em audit_log será REVOGADO explicitamente na migration.)
    ALTER DEFAULT PRIVILEGES
        FOR ROLE ${ISP_MIGRATOR_DB_USER}
        IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ${ISP_APP_DB_USER};

    -- Sequences (gen_random_uuid não usa, mas BIGSERIAL do event_queue usa).
    ALTER DEFAULT PRIVILEGES
        FOR ROLE ${ISP_MIGRATOR_DB_USER}
        IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO ${ISP_APP_DB_USER};

    -- Functions criadas pelo migrator (ex.: triggers set_updated_at) precisam
    -- ser executáveis pelo runtime.
    ALTER DEFAULT PRIVILEGES
        FOR ROLE ${ISP_MIGRATOR_DB_USER}
        IN SCHEMA public
        GRANT EXECUTE ON FUNCTIONS TO ${ISP_APP_DB_USER};
EOSQL

echo "[init.sh] Pronto. Roles e database criados."
echo "[init.sh]   Database:     ${POSTGRES_DB}"
echo "[init.sh]   Owner:        ${ISP_MIGRATOR_DB_USER} (Alembic)"
echo "[init.sh]   Runtime user: ${ISP_APP_DB_USER}"