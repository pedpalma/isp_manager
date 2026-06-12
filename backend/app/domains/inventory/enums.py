# Enums Python espelhando os ENUMs nativos do Postgres do domínio Inventory.

from __future__ import annotations

from enum import Enum


class AuthType(str, Enum):  # noqa: UP042
    """Tipo de autenticação de uma credencial de acesso a equipamento.
    Espelha o tipo nativo `auth_type_enum` do Postgres (DDL.sql).
    - PASSWORD: usuário + senha. `secret_ref` aponta para a senha no cofre.
    - SSH_KEY: usuário + chave privada. `private_key_ref` aponta para a chave; `secret_ref` aponta para a passphrase.
    - CERTIFICATE: autenticação por certificado.
    """

    PASSWORD = "password"
    SSH_KEY = "ssh_key"
    CERTIFICATE = "certificate"


class AccessProtocol(str, Enum):  # noqa: UP042
    """Protocolo de acesso de gerência a uma OLT.
    Espelha o tipo nativo `access_protocol_enum` do Postgres (DDL.sql).
    - SSH: acesso por SSH (porta padrão 22).
    - TELNET: acesso por Telnet (porta padrão 23).
    - SNMP: acesso por SNMP (porta padrão 161).
    """

    SSH = "SSH"
    TELNET = "TELNET"
    SNMP = "SNMP"


class ConnectionStatus(str, Enum):  # noqa: UP042
    """Estado da última tentativa de conexão da Coleta com a OLT.
    Espelha o tipo nativo `connection_status_enum` do Postgres (DDL.sql).
    A aplicação NÃO envia este campo na criação: o DEFAULT do banco
    ('unknown') assume e a Coleta atualiza depois.
    - UNKNOWN: nunca contatada (estado inicial).
    - ONLINE: última conexão bem-sucedida.
    - OFFLINE: sem resposta na última tentativa.
    - DEGRADED: respondeu, mas com sinais de problema.
    - AUTH_FAILED: alcançável, mas autenticação recusada.
    - TIMEOUT: estouro de tempo na última tentativa.
    """

    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    AUTH_FAILED = "auth_failed"
    TIMEOUT = "timeout"
