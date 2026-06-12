CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

--  ENUMS CONTROLADOS

CREATE TYPE connection_status_enum AS ENUM (
    'unknown', 'online', 'offline', 'degraded', 'auth_failed', 'timeout'
);

CREATE TYPE port_status_enum AS ENUM (
    'unknown', 'up', 'down', 'disabled', 'loopback', 'faulty'
);

CREATE TYPE sync_status_enum AS ENUM (
    'pending', 'synced', 'failed', 'conflict', 'disabled'
);

CREATE TYPE job_status_enum AS ENUM (
    'pending', 'running', 'success', 'failed', 'partial', 'cancelled'
);

CREATE TYPE job_trigger_type_enum AS ENUM (
    'manual', 'scheduled', 'retry', 'webhook'
);

CREATE TYPE provisioning_status_enum AS ENUM (
    'pending', 'validating', 'running', 'success',
    'failed', 'rolled_back', 'partial'
);

CREATE TYPE rollback_status_enum AS ENUM (
    'pending', 'running', 'success', 'failed'
);

CREATE TYPE pending_onu_state_enum AS ENUM (
    'detected', 'waiting', 'resolved'
);

CREATE TYPE resolution_type_enum AS ENUM (
    'provisioned', 'ignored', 'duplicate', 'rejected', 'merged'
);

CREATE TYPE optical_alert_status_enum AS ENUM (
    'open', 'acknowledged', 'resolved'
);

CREATE TYPE event_queue_status_enum AS ENUM (
    'pending', 'processing', 'processed', 'failed', 'dead_letter'
);

CREATE TYPE auth_type_enum AS ENUM (
    'password', 'ssh_key', 'certificate'
);

CREATE TYPE document_type_enum AS ENUM (
    'CPF', 'CNPJ'
);

CREATE TYPE pppoe_status_enum AS ENUM (
    'active', 'suspended', 'blocked'
);

CREATE TYPE ip_type_enum AS ENUM (
    'static', 'dynamic'
);

CREATE TYPE optical_severity_enum AS ENUM (
    'info', 'warning', 'critical'
);

CREATE TYPE optical_scope_type_enum AS ENUM (
    'onu', 'pon_port', 'olt', 'global'
);

CREATE TYPE pon_type_enum AS ENUM (
    'GPON', 'EPON', 'XGS-PON', 'XGSPON'
);

CREATE TYPE access_protocol_enum AS ENUM (
    'SSH', 'TELNET', 'SNMP'
);

--  1. CATÁLOGO E FABRICANTES

-- 1.1 Fabricantes
CREATE TABLE manufacturer (
    manufacturer_id  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name             TEXT        NOT NULL,
    slug             TEXT        NOT NULL,
    active           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_manufacturer_slug UNIQUE (slug)
);

COMMENT ON TABLE  manufacturer       IS 'Fabricantes de equipamentos de rede (Huawei, ZTE, Nokia, Fiberhome).';
COMMENT ON COLUMN manufacturer.slug  IS 'Apelido curto sem espaços, usado internamente e em integrações.';


-- 1.2 Modelos de OLT por fabricante
CREATE TABLE olt_model (
    olt_model_id    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    manufacturer_id UUID        NOT NULL REFERENCES manufacturer(manufacturer_id),
    model           TEXT        NOT NULL,
    active          BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_olt_model UNIQUE (manufacturer_id, model)
);

COMMENT ON TABLE olt_model IS 'Modelos de OLT por fabricante. Não fica preso a uma única versão de firmware.';


-- 1.3 Modelos de ONU por fabricante
CREATE TABLE onu_model (
    onu_model_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    manufacturer_id   UUID        NOT NULL REFERENCES manufacturer(manufacturer_id),
    model             TEXT        NOT NULL,
    vendor_id         TEXT,
    category          TEXT,
    capabilities_json JSONB,
    active            BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_onu_model UNIQUE (manufacturer_id, model)
);

-- Unicidade do vendor_id (4 chars hex do GPON) por fabricante quando informado
CREATE UNIQUE INDEX uq_onu_model_vendor_id
    ON onu_model (manufacturer_id, vendor_id)
    WHERE vendor_id IS NOT NULL;

COMMENT ON COLUMN onu_model.vendor_id         IS 'Identificador de vendor (ex: 4 chars hex do GPON). Usado para casar ONU descoberta com modelo.';
COMMENT ON COLUMN onu_model.capabilities_json IS 'Capacidades do modelo em formato flexível. Ex: {"wifi": true, "fxs": 2, "catv": false}';


-- 1.4 Perfil de comandos por modelo + firmware
CREATE TABLE olt_command_profile (
    olt_command_profile_id UUID                 PRIMARY KEY DEFAULT gen_random_uuid(),
    olt_model_id           UUID                 NOT NULL REFERENCES olt_model(olt_model_id),
    firmware_version       TEXT                 NOT NULL,
    access_protocol        access_protocol_enum NOT NULL DEFAULT 'SSH',
    version_constraint     TEXT,
    parser_profile         TEXT,
    active                 BOOLEAN              NOT NULL DEFAULT TRUE,
    created_at             TIMESTAMPTZ          NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ          NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_olt_command_profile UNIQUE (olt_model_id, firmware_version, access_protocol)
);

COMMENT ON TABLE  olt_command_profile                  IS 'Camada que diferencia comportamento de comandos por modelo + firmware.';
COMMENT ON COLUMN olt_command_profile.version_constraint IS 'Regra semântica de versão. Ex: ">=6.0,<7.0"';
COMMENT ON COLUMN olt_command_profile.parser_profile    IS 'Conjunto de parsers para interpretar saídas desta combinação.';


-- 1.5 Comandos normalizados por fabricante/modelo
CREATE TABLE normalized_command (
    normalized_command_id   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    manufacturer_id         UUID        NOT NULL REFERENCES manufacturer(manufacturer_id),
    olt_model_id            UUID        REFERENCES olt_model(olt_model_id),
    command_key             TEXT        NOT NULL,
    command_type            TEXT        NOT NULL,
    template_string         TEXT        NOT NULL,
    output_parser           TEXT,
    version_constraint      TEXT,
    timeout_ms              INTEGER     NOT NULL DEFAULT 10000,
    requires_privileged     BOOLEAN     NOT NULL DEFAULT FALSE,
    supports_ssh            BOOLEAN     NOT NULL DEFAULT TRUE,
    supports_telnet         BOOLEAN     NOT NULL DEFAULT FALSE,
    active                  BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Garante que não tenhamos múltiplas definições ativas para o mesmo (fabricante, modelo, comando, restrição)
-- olt_model_id pode ser NULL (comando genérico do fabricante).
CREATE UNIQUE INDEX uq_normalized_command_key
    ON normalized_command (
        manufacturer_id,
        COALESCE(olt_model_id, '00000000-0000-0000-0000-000000000000'),
        command_key,
        COALESCE(version_constraint, '')
    ) WHERE active = TRUE;

COMMENT ON TABLE  normalized_command                IS 'Catálogo de comandos normalizados. O sistema usa command_key genérico; esta tabela resolve para o comando real do fabricante.';
COMMENT ON COLUMN normalized_command.command_key    IS 'Nome genérico do comando. Ex: "reboot_onu", "get_onu_status", "list_unprovisioned".';
COMMENT ON COLUMN normalized_command.template_string IS 'Comando real do fabricante com variáveis marcadas para substituição. Ex: "show gpon onu unconfigured slot {slot} pon {pon}".';

--  2. CREDENCIAIS E OLTs

-- 2.1 Credenciais de acesso aos equipamentos
CREATE TABLE credential (
    credential_id     UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    label             TEXT            NOT NULL,
    username          TEXT            NOT NULL,
    secret_ref        TEXT            NOT NULL,
    enable_secret_ref TEXT,
    auth_type         auth_type_enum  NOT NULL DEFAULT 'password',
    private_key_ref   TEXT,
    last_validated_at TIMESTAMPTZ,
    active            BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  credential            IS 'Credenciais de acesso a OLTs. Senhas armazenadas como referência para cofre/KMS/Vault.';
COMMENT ON COLUMN credential.secret_ref IS 'Referência para cofre de segredos (Vault, AWS KMS, etc.). Nunca a senha em texto.';


-- 2.2 OLT: equipamento físico instalado na rede
CREATE TABLE olt (
    olt_id            UUID                   PRIMARY KEY DEFAULT gen_random_uuid(),
    olt_model_id      UUID                   NOT NULL REFERENCES olt_model(olt_model_id),
    credential_id     UUID                   NOT NULL REFERENCES credential(credential_id),
    name              TEXT                   NOT NULL,
    hostname          TEXT,
    ip                INET                   NOT NULL,
    management_port   INTEGER                NOT NULL DEFAULT 22,
    access_protocol   access_protocol_enum   NOT NULL DEFAULT 'SSH',
    firmware_version  TEXT,
    connection_status connection_status_enum NOT NULL DEFAULT 'unknown',
    location          TEXT,
    timezone          TEXT                   NOT NULL DEFAULT 'America/Sao_Paulo',
    polling_enabled   BOOLEAN                NOT NULL DEFAULT TRUE,
    last_seen_at      TIMESTAMPTZ,
    last_collected_at TIMESTAMPTZ,
    active            BOOLEAN                NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ            NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ            NOT NULL DEFAULT NOW(),
    deleted_at        TIMESTAMPTZ
);

-- IP + porta de gerência são únicos juntos (permite VRFs/POPs com IPs sobrepostos em portas diferentes)
-- e ignora OLTs desativadas (soft delete).
CREATE UNIQUE INDEX uq_olt_ip_port_active
    ON olt (ip, management_port)
    WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX uq_olt_name_active
    ON olt (name)
    WHERE deleted_at IS NULL;

COMMENT ON TABLE  olt                   IS 'Equipamento físico OLT instalado na rede. Cada linha é uma OLT real.';
COMMENT ON COLUMN olt.polling_enabled   IS 'Se FALSE, a OLT não será monitorada ativamente pelo sistema de coleta.';
COMMENT ON COLUMN olt.deleted_at        IS 'Soft delete: a OLT pode ser desativada sem perder histórico de coleta e provisionamento.';

--  3. ESTRUTURA FÍSICA: CHASSIS / SLOT / PON

-- 3.1 Chassi da OLT
CREATE TABLE chassis (
    chassis_id    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    olt_id        UUID        NOT NULL REFERENCES olt(olt_id),
    chassis_index INTEGER     NOT NULL,
    description   TEXT,
    discovered_at TIMESTAMPTZ,
    last_seen_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_chassis_olt_index UNIQUE (olt_id, chassis_index)
);


-- 3.2 Slot dentro do chassi
CREATE TABLE slot (
    slot_id       UUID              PRIMARY KEY DEFAULT gen_random_uuid(),
    chassis_id    UUID              NOT NULL REFERENCES chassis(chassis_id),
    slot_index    INTEGER           NOT NULL,
    board_type    TEXT,
    status        port_status_enum  NOT NULL DEFAULT 'unknown',
    discovered_at TIMESTAMPTZ,
    last_seen_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ       NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_slot_chassis_index UNIQUE (chassis_id, slot_index)
);


-- 3.3 Porta PON dentro do slot
CREATE TABLE pon_port (
    pon_port_id   UUID              PRIMARY KEY DEFAULT gen_random_uuid(),
    slot_id       UUID              NOT NULL REFERENCES slot(slot_id),
    pon_index     INTEGER           NOT NULL,
    pon_type      pon_type_enum     NOT NULL DEFAULT 'GPON',
    status        port_status_enum  NOT NULL DEFAULT 'unknown',
    discovered_at TIMESTAMPTZ,
    last_seen_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ       NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_pon_port_slot_index UNIQUE (slot_id, pon_index)
);

--  4. USUÁRIOS E PERMISSÕES

-- 4.1 Grupos de usuários
CREATE TABLE user_group (
    user_group_id    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name             TEXT        NOT NULL,
    permissions_json JSONB       NOT NULL DEFAULT '{}',
    active           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_user_group_name UNIQUE (name)
);

COMMENT ON COLUMN user_group.permissions_json IS 'Permissões do grupo. Ex: {"provision_onu": true, "view_only": false}';


-- 4.2 Usuários do sistema
CREATE TABLE app_user (
    app_user_id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_group_id             UUID        NOT NULL REFERENCES user_group(user_group_id) ON DELETE RESTRICT,
    username                  TEXT        NOT NULL,
    email                     TEXT        NOT NULL,
    password_hash             TEXT        NOT NULL,
    active                    BOOLEAN     NOT NULL DEFAULT TRUE,
    must_change_password      BOOLEAN     NOT NULL DEFAULT FALSE,
    reset_password_token      TEXT,
    reset_password_expires_at TIMESTAMPTZ,
    last_login_at             TIMESTAMPTZ,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_app_user_username UNIQUE (username),
    CONSTRAINT uq_app_user_email    UNIQUE (email)
);

COMMENT ON COLUMN app_user.password_hash IS 'Hash da senha (bcrypt ou Argon2). Nunca armazenar senha em texto puro.';


-- 4.3 Sessões de usuário (tokens JWT/refresh)
CREATE TABLE app_user_session (
    app_user_session_id UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    app_user_id         UUID        NOT NULL REFERENCES app_user(app_user_id) ON DELETE CASCADE,
    token_hash          TEXT        NOT NULL,
    refresh_token_hash  TEXT,
    user_agent          TEXT,
    ip_address          INET,
    issued_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMPTZ NOT NULL,
    revoked_at          TIMESTAMPTZ,
    last_used_at        TIMESTAMPTZ,

    CONSTRAINT uq_app_user_session_token UNIQUE (token_hash)
);

CREATE INDEX idx_app_user_session_user_active
    ON app_user_session (app_user_id)
    WHERE revoked_at IS NULL;

COMMENT ON TABLE app_user_session IS 'Sessões ativas/históricas de usuário. Permite invalidar tokens, listar dispositivos e auditar logins.';

--  5. PERFIS E TEMPLATES DE PROVISIONAMENTO

-- 5.1 VLANs da OLT
CREATE TABLE vlan (
    vlan_id     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    olt_id      UUID        NOT NULL REFERENCES olt(olt_id),
    vlan_number INTEGER     NOT NULL CHECK (vlan_number BETWEEN 1 AND 4094),
    name        TEXT,
    type        TEXT,
    description TEXT,
    active      BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_vlan_olt_number UNIQUE (olt_id, vlan_number)
);


-- 5.2 Perfil de linha (velocidade)
CREATE TABLE line_profile (
    line_profile_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    olt_id               UUID        NOT NULL REFERENCES olt(olt_id),
    logical_name         TEXT,
    name                 TEXT        NOT NULL,
    version              TEXT        NOT NULL DEFAULT '1',
    upstream_bandwidth   TEXT        NOT NULL,
    downstream_bandwidth TEXT        NOT NULL,
    raw_config           JSONB,
    active               BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_line_profile_olt_name_version UNIQUE (olt_id, name, version)
);

COMMENT ON COLUMN line_profile.logical_name IS 'Nome lógico do perfil replicado em N OLTs. Ex: "PLANO_600M". Permite consultas agregadas e edição em massa futura.';


-- 5.3 Perfil de serviço (VLANs, serviços de rede)
CREATE TABLE service_profile (
    service_profile_id UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    olt_id             UUID        NOT NULL REFERENCES olt(olt_id),
    logical_name       TEXT,
    name               TEXT        NOT NULL,
    version            TEXT        NOT NULL DEFAULT '1',
    raw_config         JSONB,
    active             BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_service_profile_olt_name_version UNIQUE (olt_id, name, version)
);

COMMENT ON COLUMN service_profile.logical_name IS 'Nome lógico do perfil replicado em N OLTs.';


-- 5.4 Template de provisionamento
CREATE TABLE provisioning_template (
    provisioning_template_id UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    manufacturer_id          UUID        NOT NULL REFERENCES manufacturer(manufacturer_id),
    olt_model_id             UUID        REFERENCES olt_model(olt_model_id),
    created_by_user_id       UUID        REFERENCES app_user(app_user_id),
    template_scope           TEXT        NOT NULL DEFAULT 'onu_provision',
    name                     TEXT        NOT NULL,
    version                  TEXT        NOT NULL DEFAULT '1',
    firmware_constraint      TEXT,
    command_vars             JSONB,
    raw_template             JSONB       NOT NULL,
    active                   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Mesmo padrão de COALESCE: olt_model_id pode ser NULL
CREATE UNIQUE INDEX uq_provisioning_template_key
    ON provisioning_template (
        manufacturer_id,
        COALESCE(olt_model_id, '00000000-0000-0000-0000-000000000000'),
        name,
        version
    );

COMMENT ON COLUMN provisioning_template.template_scope      IS 'Escopo do template. Ex: onu_provision, onu_remove, vlan_config.';
COMMENT ON COLUMN provisioning_template.firmware_constraint IS 'Restrição de versão de firmware compatível. Ex: ">=5.2".';

--  6. CLIENTES E ONUs

-- 6.1 Cliente final
CREATE TABLE customer (
    customer_id   UUID                 PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT                 NOT NULL,
    document      TEXT                 NOT NULL,
    document_type document_type_enum   NOT NULL,
    external_ref  TEXT,
    created_at    TIMESTAMPTZ          NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ          NOT NULL DEFAULT NOW(),
    deleted_at    TIMESTAMPTZ,

    CONSTRAINT uq_customer_document UNIQUE (document_type, document)
);

COMMENT ON COLUMN customer.external_ref IS 'Referência no sistema externo (IXC). Para sincronização completa, usar sync_state.';


-- 6.2 ONU - tabela mais central do sistema
CREATE TABLE onu (
    onu_id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    onu_model_id             UUID        NOT NULL REFERENCES onu_model(onu_model_id),
    pon_port_id              UUID        NOT NULL REFERENCES pon_port(pon_port_id),
    customer_id              UUID        REFERENCES customer(customer_id),
    line_profile_id          UUID        REFERENCES line_profile(line_profile_id),
    service_profile_id       UUID        REFERENCES service_profile(service_profile_id),
    provisioning_template_id UUID        REFERENCES provisioning_template(provisioning_template_id),
    serial                   TEXT        NOT NULL,
    onu_index                INTEGER,
    description              TEXT,
    provisioned              BOOLEAN     NOT NULL DEFAULT FALSE,
    first_seen_at            TIMESTAMPTZ,
    last_seen_at             TIMESTAMPTZ,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at               TIMESTAMPTZ
);

-- Unicidade do serial só vale entre ONUs ATIVAS.
-- Permite reuso/realocação do mesmo serial após desativação.
CREATE UNIQUE INDEX uq_onu_serial_active
    ON onu (serial)
    WHERE deleted_at IS NULL;

-- onu_index não pode repetir dentro da mesma PON entre ONUs ativas
CREATE UNIQUE INDEX uq_onu_index_per_pon_active
    ON onu (pon_port_id, onu_index)
    WHERE deleted_at IS NULL AND onu_index IS NOT NULL;

-- Índices operacionais frequentes
CREATE INDEX idx_onu_pon_port
    ON onu (pon_port_id)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_onu_customer
    ON onu (customer_id)
    WHERE deleted_at IS NULL AND customer_id IS NOT NULL;

CREATE INDEX idx_onu_serial_trgm
    ON onu USING gin (serial gin_trgm_ops)
    WHERE deleted_at IS NULL;

COMMENT ON TABLE  onu        IS 'ONU instalada e ativa na rede. Tabela mais central do sistema.';
COMMENT ON COLUMN onu.serial IS 'Número de série. Unicidade apenas entre ONUs ativas (deleted_at IS NULL) para permitir reuso após desativação.';


-- 6.3 Estado operacional atual da ONU (1:1 com onu)
CREATE TABLE onu_runtime_state (
    onu_id            UUID                   PRIMARY KEY REFERENCES onu(onu_id) ON DELETE CASCADE,
    connection_status connection_status_enum NOT NULL DEFAULT 'unknown',
    oper_state        TEXT,
    sync_status       sync_status_enum       NOT NULL DEFAULT 'pending',
    last_signal_at    TIMESTAMPTZ,
    last_down_reason  TEXT,
    distance_m        NUMERIC(10,2),
    last_collected_at TIMESTAMPTZ,
    updated_at        TIMESTAMPTZ            NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_onu_runtime_status
    ON onu_runtime_state (connection_status);

COMMENT ON TABLE onu_runtime_state IS 'Estado operacional atual da ONU, separado da identidade. Relação 1:1 com onu. Reduz sobrescritas na tabela principal.';


-- 6.4 ONU pendente (fila de espera para provisionamento)
CREATE TABLE pending_onu (
    pending_onu_id   UUID                    PRIMARY KEY DEFAULT gen_random_uuid(),
    olt_id           UUID                    NOT NULL REFERENCES olt(olt_id),
    pon_port_id      UUID                    NOT NULL REFERENCES pon_port(pon_port_id),
    onu_model_id     UUID                    REFERENCES onu_model(onu_model_id),
    linked_onu_id    UUID                    REFERENCES onu(onu_id),
    serial           TEXT                    NOT NULL,
    vendor_id        TEXT,
    pon_position     INTEGER,
    state            pending_onu_state_enum  NOT NULL DEFAULT 'detected',
    is_duplicate     BOOLEAN                 NOT NULL DEFAULT FALSE,
    raw_payload      JSONB,
    discovery_source TEXT,
    resolution_type  resolution_type_enum,
    first_seen_at    TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    last_seen_at     TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    resolved_at      TIMESTAMPTZ,
    created_at       TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ             NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_pending_onu UNIQUE (olt_id, pon_port_id, serial)
);

CREATE INDEX idx_pending_onu_olt_state
    ON pending_onu (olt_id, state);

CREATE INDEX idx_pending_onu_serial
    ON pending_onu (serial);

CREATE INDEX idx_pending_onu_unresolved
    ON pending_onu (olt_id, last_seen_at DESC)
    WHERE state IN ('detected', 'waiting');

COMMENT ON TABLE  pending_onu              IS 'ONUs detectadas na rede ainda não provisionadas. Ciclo: detected → waiting → resolved.';
COMMENT ON COLUMN pending_onu.linked_onu_id IS 'Preenchido após resolução, apontando para a ONU definitiva criada.';

--  7. COLETA

-- 7.1 Tarefa de coleta
CREATE TABLE collection_job (
    collection_job_id    UUID                  PRIMARY KEY DEFAULT gen_random_uuid(),
    olt_id               UUID                  NOT NULL REFERENCES olt(olt_id),
    requested_by_user_id UUID                  REFERENCES app_user(app_user_id),
    job_type             TEXT                  NOT NULL,
    trigger_type         job_trigger_type_enum NOT NULL DEFAULT 'manual',
    target_scope         TEXT,
    payload              JSONB,
    status               job_status_enum       NOT NULL DEFAULT 'pending',
    retry_count          INTEGER               NOT NULL DEFAULT 0,
    started_at           TIMESTAMPTZ,
    finished_at          TIMESTAMPTZ,
    error_message        TEXT,
    created_at           TIMESTAMPTZ           NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_collection_job_olt_status_created
    ON collection_job (olt_id, status, created_at DESC);

CREATE INDEX idx_collection_job_running
    ON collection_job (olt_id, started_at)
    WHERE status IN ('pending', 'running');


-- 7.2 Log detalhado de cada comando enviado
CREATE TABLE collection_log (
    collection_log_id UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_job_id UUID        NOT NULL REFERENCES collection_job(collection_job_id),
    olt_id            UUID        NOT NULL REFERENCES olt(olt_id),
    step_name         TEXT,
    command_sent      TEXT        NOT NULL,
    output_received   TEXT,
    parser_status     TEXT,
    success           BOOLEAN     NOT NULL DEFAULT FALSE,
    duration_ms       INTEGER,
    executed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_collection_log_job
    ON collection_log (collection_job_id, executed_at);

--  8. PROVISIONAMENTO

-- 8.1 Ordem de provisionamento
CREATE TABLE provisioning_order (
    provisioning_order_id    UUID                      PRIMARY KEY DEFAULT gen_random_uuid(),
    olt_id                   UUID                      NOT NULL REFERENCES olt(olt_id),
    pon_port_id              UUID                      NOT NULL REFERENCES pon_port(pon_port_id),
    onu_id                   UUID                      REFERENCES onu(onu_id),
    app_user_id              UUID                      NOT NULL REFERENCES app_user(app_user_id),
    provisioning_template_id UUID                      NOT NULL REFERENCES provisioning_template(provisioning_template_id),
    retry_of_order_id        UUID                      REFERENCES provisioning_order(provisioning_order_id),
    idempotency_key          TEXT                      NOT NULL,
    status                   provisioning_status_enum  NOT NULL DEFAULT 'pending',
    failure_reason           TEXT,
    result_summary           TEXT,
    snapshot_params          JSONB                     NOT NULL,
    requested_at             TIMESTAMPTZ               NOT NULL DEFAULT NOW(),
    started_at               TIMESTAMPTZ,
    finished_at              TIMESTAMPTZ,
    created_at               TIMESTAMPTZ               NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_provisioning_idempotency UNIQUE (idempotency_key)
);

CREATE INDEX idx_provisioning_order_olt_status
    ON provisioning_order (olt_id, status, created_at DESC);

CREATE INDEX idx_provisioning_order_user
    ON provisioning_order (app_user_id, created_at DESC);

CREATE INDEX idx_provisioning_order_onu
    ON provisioning_order (onu_id)
    WHERE onu_id IS NOT NULL;

COMMENT ON COLUMN provisioning_order.idempotency_key  IS 'Chave única para evitar execuções duplicadas acidentais.';
COMMENT ON COLUMN provisioning_order.snapshot_params  IS 'Foto dos parâmetros usados (serial, perfis, VLAN). Congelada, nunca deve ser alterada.';
COMMENT ON COLUMN provisioning_order.retry_of_order_id IS 'Auto-referência: aponta para a ordem original quando é uma nova tentativa.';


-- 8.2 Passo individual de provisionamento
CREATE TABLE provisioning_step (
    provisioning_step_id  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    provisioning_order_id UUID        NOT NULL REFERENCES provisioning_order(provisioning_order_id) ON DELETE CASCADE,
    step_order            INTEGER     NOT NULL,
    step_key              TEXT        NOT NULL,
    phase                 TEXT        NOT NULL,
    command_sent          TEXT,
    output_received       TEXT,
    parser_output         JSONB,
    success               BOOLEAN     NOT NULL DEFAULT FALSE,
    duration_ms           INTEGER,
    executed_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_provisioning_step_order UNIQUE (provisioning_order_id, step_order)
);

CREATE INDEX idx_provisioning_step_order
    ON provisioning_step (provisioning_order_id, step_order);


-- 8.3 Rollback de provisionamento
CREATE TABLE provisioning_rollback (
    provisioning_rollback_id UUID                 PRIMARY KEY DEFAULT gen_random_uuid(),
    provisioning_order_id    UUID                 NOT NULL REFERENCES provisioning_order(provisioning_order_id),
    reason                   TEXT                 NOT NULL,
    rollback_commands        JSONB                NOT NULL,
    rollback_status          rollback_status_enum NOT NULL DEFAULT 'pending',
    output_received          TEXT,
    executed                 BOOLEAN              NOT NULL DEFAULT FALSE,
    executed_at              TIMESTAMPTZ,
    created_at               TIMESTAMPTZ          NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_provisioning_rollback_order
    ON provisioning_rollback (provisioning_order_id);

--  9. SINAL ÓPTICO (PARTICIONADO POR MÊS)

-- 9.1 Leituras ópticas - particionado por collected_at
-- A chave primária precisa incluir a coluna de partição (collected_at).
CREATE TABLE optical_reading (
    optical_reading_id UUID        NOT NULL DEFAULT gen_random_uuid(),
    onu_id             UUID        NOT NULL REFERENCES onu(onu_id),
    rx_power_dbm       NUMERIC(6,2),
    tx_power_dbm       NUMERIC(6,2),
    status             TEXT,
    alert_critical     BOOLEAN     NOT NULL DEFAULT FALSE,
    distance_m         NUMERIC(10,2),
    temperature        NUMERIC(5,2),
    voltage            NUMERIC(6,3),
    bias_current       NUMERIC(7,3),
    collected_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    collection_source  TEXT,

    CONSTRAINT pk_optical_reading PRIMARY KEY (optical_reading_id, collected_at)
) PARTITION BY RANGE (collected_at);

COMMENT ON TABLE optical_reading IS 'Medições periódicas de sinal óptico. Particionada mensalmente por collected_at.';

-- Índices na tabela pai são herdados pelas partições
CREATE INDEX idx_optical_reading_onu_collected
    ON optical_reading (onu_id, collected_at DESC);

CREATE INDEX idx_optical_reading_critical
    ON optical_reading (collected_at DESC)
    WHERE alert_critical = TRUE;

-- Partição padrão para capturar leituras fora das partições explícitas
-- (não deve ser usada na operação normal - apenas safety net).
CREATE TABLE optical_reading_default
    PARTITION OF optical_reading DEFAULT;

-- Cria partições para o mês corrente, anterior e próximos 12 meses
-- (rotina periódica deve criar partições futuras automaticamente).
DO $$
DECLARE
    start_month DATE := date_trunc('month', NOW() - INTERVAL '1 month')::date;
    part_date   DATE;
    part_name   TEXT;
    range_start TEXT;
    range_end   TEXT;
    i INTEGER;
BEGIN
    FOR i IN 0..13 LOOP
        part_date   := start_month + (i || ' months')::interval;
        part_name   := 'optical_reading_' || to_char(part_date, 'YYYY_MM');
        range_start := to_char(part_date, 'YYYY-MM-DD');
        range_end   := to_char(part_date + INTERVAL '1 month', 'YYYY-MM-DD');

        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF optical_reading
             FOR VALUES FROM (%L) TO (%L)',
            part_name, range_start, range_end
        );
    END LOOP;
END;
$$;


-- 9.2 Política de threshold óptico
CREATE TABLE optical_threshold_policy (
    optical_threshold_policy_id UUID                     PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_type                  optical_scope_type_enum  NOT NULL,
    scope_id                    UUID,
    metric_name                 TEXT                     NOT NULL,
    threshold_min               NUMERIC(8,3),
    threshold_max               NUMERIC(8,3),
    severity                    optical_severity_enum    NOT NULL DEFAULT 'warning',
    active                      BOOLEAN                  NOT NULL DEFAULT TRUE,
    created_at                  TIMESTAMPTZ              NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ              NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_threshold_range CHECK (
        threshold_min IS NOT NULL OR threshold_max IS NOT NULL
    )
);

-- Garante unicidade do par (escopo, métrica). NULL no scope_id = global.
CREATE UNIQUE INDEX uq_optical_threshold_policy_scope
    ON optical_threshold_policy (
        scope_type,
        COALESCE(scope_id, '00000000-0000-0000-0000-000000000000'),
        metric_name
    ) WHERE active = TRUE;

COMMENT ON TABLE  optical_threshold_policy          IS 'Políticas de threshold óptico por escopo. Separa definição de limiar da ocorrência de alertas.';
COMMENT ON COLUMN optical_threshold_policy.scope_id IS 'ID da entidade. NULL indica política global.';


-- 9.3 Evento de alerta óptico
CREATE TABLE optical_alert_event (
    optical_alert_event_id UUID                      PRIMARY KEY DEFAULT gen_random_uuid(),
    onu_id                 UUID                      NOT NULL REFERENCES onu(onu_id),
    policy_id              UUID                      NOT NULL REFERENCES optical_threshold_policy(optical_threshold_policy_id),
    metric_name            TEXT                      NOT NULL,
    value                  NUMERIC(8,3)              NOT NULL,
    status                 optical_alert_status_enum NOT NULL DEFAULT 'open',
    triggered_at           TIMESTAMPTZ               NOT NULL DEFAULT NOW(),
    resolved_at            TIMESTAMPTZ,
    created_at             TIMESTAMPTZ               NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_optical_alert_open
    ON optical_alert_event (onu_id, triggered_at DESC)
    WHERE status = 'open';

CREATE INDEX idx_optical_alert_status
    ON optical_alert_event (status, triggered_at DESC);

-- 10. AUDITORIA E INTEGRAÇÃO

-- 10.1 Log de auditoria - append-only
CREATE TABLE audit_log (
    audit_log_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    app_user_id           UUID        REFERENCES app_user(app_user_id),
    olt_id                UUID        REFERENCES olt(olt_id),
    onu_id                UUID        REFERENCES onu(onu_id),
    provisioning_order_id UUID        REFERENCES provisioning_order(provisioning_order_id),
    entity_type           TEXT        NOT NULL,
    entity_id             UUID        NOT NULL,
    action                TEXT        NOT NULL,
    result                TEXT        NOT NULL,
    error_detail          TEXT,
    before_data           JSONB,
    after_data            JSONB,
    metadata              JSONB,
    request_id            TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_log_entity   ON audit_log (entity_type, entity_id);
CREATE INDEX idx_audit_log_created  ON audit_log (created_at DESC);
CREATE INDEX idx_audit_log_user     ON audit_log (app_user_id, created_at DESC) WHERE app_user_id IS NOT NULL;
CREATE INDEX idx_audit_log_olt      ON audit_log (olt_id, created_at DESC)      WHERE olt_id IS NOT NULL;
CREATE INDEX idx_audit_log_request  ON audit_log (request_id)                   WHERE request_id IS NOT NULL;

COMMENT ON TABLE audit_log IS 'Registro permanente e imutável de todas as ações do sistema. UPDATE e DELETE devem ser bloqueados via REVOKE no role da aplicação.';

-- Trigger que bloqueia UPDATE/DELETE em audit_log
CREATE OR REPLACE FUNCTION audit_log_immutable()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_log é append-only. % não é permitido.', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_log_no_update
    BEFORE UPDATE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();

CREATE TRIGGER trg_audit_log_no_delete
    BEFORE DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();


-- 10.2 Fila de eventos (outbox pattern)
CREATE TABLE event_queue (
    event_queue_id    UUID                    PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type        TEXT                    NOT NULL,
    entity_type       TEXT                    NOT NULL,
    entity_id         UUID                    NOT NULL,
    topic             TEXT,
    dedup_key         TEXT,
    sequence_number   BIGSERIAL               NOT NULL,
    payload           JSONB                   NOT NULL,
    status            event_queue_status_enum NOT NULL DEFAULT 'pending',
    retry_count       INTEGER                 NOT NULL DEFAULT 0,
    available_at      TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    created_at        TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    last_attempt_at   TIMESTAMPTZ,
    processed_at      TIMESTAMPTZ,
    processed_by      TEXT,
    error_message     TEXT
);

-- Índice crítico para processamento eficiente da fila
CREATE INDEX idx_event_queue_status_available
    ON event_queue (status, available_at)
    WHERE status IN ('pending', 'failed');

CREATE INDEX idx_event_queue_dedup
    ON event_queue (dedup_key)
    WHERE dedup_key IS NOT NULL;

CREATE INDEX idx_event_queue_entity
    ON event_queue (entity_type, entity_id, sequence_number);

COMMENT ON TABLE  event_queue                IS 'Fila de eventos para integração assíncrona (outbox pattern). Workers consomem e atualizam status.';
COMMENT ON COLUMN event_queue.sequence_number IS 'Sequencial global. Permite ordenar eventos por entidade preservando ordem de produção.';


-- 10.3 Estado de sincronização com sistemas externos
CREATE TABLE sync_state (
    sync_state_id   UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type     TEXT             NOT NULL,
    entity_id       UUID             NOT NULL,
    external_system TEXT             NOT NULL,
    external_id     TEXT,
    sync_status     sync_status_enum NOT NULL DEFAULT 'pending',
    last_sync_at    TIMESTAMPTZ,
    error_detail    TEXT,
    created_at      TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ      NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_sync_state UNIQUE (entity_type, entity_id, external_system)
);

CREATE INDEX idx_sync_state_entity   ON sync_state (entity_type, entity_id);
CREATE INDEX idx_sync_state_external ON sync_state (external_system, external_id) WHERE external_id IS NOT NULL;
CREATE INDEX idx_sync_state_pending  ON sync_state (external_system, sync_status) WHERE sync_status IN ('pending', 'failed');

COMMENT ON TABLE sync_state IS 'Centraliza integração com sistemas externos. Evita espalhar external_id e sync_status em múltiplas tabelas.';

-- 11. PPPoE

-- 11.1 Credencial PPPoE
CREATE TABLE pppoe_credential (
    pppoe_credential_id UUID              PRIMARY KEY DEFAULT gen_random_uuid(),
    onu_id              UUID              NOT NULL REFERENCES onu(onu_id),
    customer_id         UUID              NOT NULL REFERENCES customer(customer_id),
    username            TEXT              NOT NULL,
    secret_ref          TEXT              NOT NULL,
    status              pppoe_status_enum NOT NULL DEFAULT 'active',
    ip_type             ip_type_enum      NOT NULL DEFAULT 'dynamic',
    last_auth_at        TIMESTAMPTZ,
    expires_at          TIMESTAMPTZ,
    notes               TEXT,
    created_at          TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ       NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_pppoe_credential_username UNIQUE (username)
);

CREATE INDEX idx_pppoe_credential_onu      ON pppoe_credential (onu_id);
CREATE INDEX idx_pppoe_credential_customer ON pppoe_credential (customer_id);

COMMENT ON COLUMN pppoe_credential.secret_ref IS 'Referência para cofre de segredos. Nunca a senha PPPoE em texto.';


-- 11.2 Sessões PPPoE
CREATE TABLE pppoe_session (
    pppoe_session_id    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    pppoe_credential_id UUID        NOT NULL REFERENCES pppoe_credential(pppoe_credential_id),
    ip_assigned         INET,
    nas_ip              INET,
    session_id          TEXT,
    connected_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    disconnected_at     TIMESTAMPTZ,
    disconnect_reason   TEXT,
    bytes_in            BIGINT      NOT NULL DEFAULT 0,
    bytes_out           BIGINT      NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pppoe_session_credential
    ON pppoe_session (pppoe_credential_id, connected_at DESC);

CREATE INDEX idx_pppoe_session_active
    ON pppoe_session (pppoe_credential_id)
    WHERE disconnected_at IS NULL;

COMMENT ON TABLE pppoe_session IS 'Histórico de sessões PPPoE. Alto volume - definir política de retenção (recomendado particionar quando ativar).';

-- 12. FUNÇÕES E TRIGGERS

-- 12.1 Trigger genérico para updated_at
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Aplica o trigger em todas as tabelas com updated_at
DO $$
DECLARE
    t TEXT;
BEGIN
    FOR t IN SELECT unnest(ARRAY[
        'manufacturer', 'olt_model', 'onu_model', 'olt_command_profile',
        'normalized_command', 'credential', 'olt',
        'chassis', 'slot', 'pon_port',
        'user_group', 'app_user',
        'vlan', 'line_profile', 'service_profile', 'provisioning_template',
        'customer', 'onu', 'pending_onu',
        'optical_threshold_policy',
        'sync_state',
        'pppoe_credential'
    ])
    LOOP
        EXECUTE format(
            'CREATE TRIGGER trg_%I_updated_at
             BEFORE UPDATE ON %I
             FOR EACH ROW EXECUTE FUNCTION set_updated_at()',
            t, t
        );
    END LOOP;
END;
$$;


-- 12.2 Criação automática de onu_runtime_state quando uma ONU é inserida
CREATE OR REPLACE FUNCTION ensure_onu_runtime_state()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO onu_runtime_state (onu_id)
    VALUES (NEW.onu_id)
    ON CONFLICT (onu_id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_onu_runtime_state_create
    AFTER INSERT ON onu
    FOR EACH ROW EXECUTE FUNCTION ensure_onu_runtime_state();


-- 12.3 Função utilitária: criar partição mensal de optical_reading
CREATE OR REPLACE FUNCTION create_optical_reading_partition(target_month DATE)
RETURNS TEXT AS $$
DECLARE
    part_name   TEXT;
    range_start TEXT;
    range_end   TEXT;
    month_start DATE;
BEGIN
    month_start := date_trunc('month', target_month)::date;
    part_name   := 'optical_reading_' || to_char(month_start, 'YYYY_MM');
    range_start := to_char(month_start, 'YYYY-MM-DD');
    range_end   := to_char(month_start + INTERVAL '1 month', 'YYYY-MM-DD');

    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF optical_reading
         FOR VALUES FROM (%L) TO (%L)',
        part_name, range_start, range_end
    );

    RETURN part_name;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION create_optical_reading_partition(DATE) IS 'Cria partição mensal de optical_reading. Chamar mensalmente via cron para garantir partições futuras.';

-- 13. SEED INICIAL

-- Grupos de usuários padrão
INSERT INTO user_group (name, permissions_json) VALUES
    ('Administrador', '{"all": true}'),
    ('Técnico',       '{"provision_onu": true, "view_olt": true, "view_onu": true}'),
    ('Visualizador',  '{"view_olt": true, "view_onu": true}');

-- Fabricantes comuns
INSERT INTO manufacturer (name, slug) VALUES
    ('Huawei',    'huawei'),
    ('ZTE',       'zte'),
    ('Fiberhome', 'fiberhome'),
    ('Nokia',     'nokia');
