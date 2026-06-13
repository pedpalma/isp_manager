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


class PortStatus(str, Enum):  # noqa: UP042
    """Estado operacional/administrativo de slot e pon_port.
    Espelha o tipo nativo `port_status_enum` do Postgres (DDL.sql).

    A aplicação só pode setar 'disabled' e 'unknown' via PATCH.
    Os demais valores ('up', 'down', 'loopback', 'faulty') são exclusivos
    da Coleta; o service rejeita tentativa de mutação direta neles.
    """

    UNKNOWN = "unknown"
    UP = "up"
    DOWN = "down"
    DISABLED = "disabled"
    LOOPBACK = "loopback"
    FAULTY = "faulty"


# Conjunto de status admissíveis para mutação manual via PATCH.
ADMIN_MUTABLE_PORT_STATUS: frozenset[PortStatus] = frozenset(
    {PortStatus.DISABLED, PortStatus.UNKNOWN}
)


# NOTA: o rótulo 'XGSPON' foi renomeado para 'XG-PON' pela migration 0002.
# O DDL.sql da raiz deve refletir essa mudança após aplicar a 0002.
class PonType(str, Enum):  # noqa: UP042
    """Tecnologia PON da porta. Espelha `pon_type_enum` do Postgres."""

    GPON = "GPON"
    EPON = "EPON"
    XGS_PON = "XGS-PON"
    XG_PON = "XG-PON"
