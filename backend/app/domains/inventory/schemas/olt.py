# Schemas Pydantic v2 da OLT.

# Decisões refletidas aqui:
# - Separação de campos entre Create / Update / Read.
#   * olt_model_id: só Create (imutável). Não existe no Update.
#   * credential_id: Create e Update (mutável).
#   * connection_status, last_seen_at, last_collected_at: só Read.
#   * deleted_at: OMITIDO do Read (não expõe estado de soft delete).
# - ip via IPvAnyAddress (host, rejeita máscara/rede); management_port em 1..65535; timezone validado contra IANA.
# - `active` entra no Create (default True), por consistência com o credential (que tem `active` no Base).

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo, available_timezones

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    IPvAnyAddress,
    field_validator,
)

from app.domains.inventory.enums import AccessProtocol, ConnectionStatus

# Conjunto de timezones IANA válidas, resolvido uma vez na importação.
_IANA_TIMEZONES = available_timezones()


def _validate_timezone(value: str) -> str:
    """Valida que `value` é uma timezone IANA conhecida (ex.: 'America/Sao_Paulo').

    Usa o conjunto do sistema e confirma com ZoneInfo. Rejeita offsets
    soltos e nomes inventados. Levanta ValueError (vira 422 no Pydantic)."""
    if value not in _IANA_TIMEZONES:
        raise ValueError(
            f"timezone inválida: '{value}'. Use um nome IANA, ex.: 'America/Sao_Paulo' ou 'UTC'."
        )
    try:
        ZoneInfo(value)
    except Exception as exc:
        raise ValueError(f"timezone inválida: '{value}'.") from exc
    return value


class OltBase(BaseModel):
    """Campos comuns a Create e Read. credential_id está aqui porque é
    mutável (aparece em Create, Update e Read)."""

    name: str = Field(
        min_length=1,
        max_length=200,
        description="Nome da OLT. Único entre OLTs vivas (deleted_at IS NULL).",
    )
    hostname: str | None = Field(
        default=None,
        max_length=255,
        description="Hostname de gerência, opcional.",
    )
    ip: IPvAnyAddress = Field(
        description="Endereço de gerência (host IPv4/IPv6). Não aceita máscara/rede.",
    )
    management_port: int = Field(
        default=22,
        ge=1,
        le=65535,
        description="Porta de gerência (1..65535). Default 22 (SSH).",
    )
    access_protocol: AccessProtocol = Field(
        default=AccessProtocol.SSH,
        description="Protocolo de acesso. Valores: ssh, telnet, snmp.",
    )
    firmware_version: str | None = Field(
        default=None,
        max_length=100,
        description="Versão de firmware, opcional.",
    )
    location: str | None = Field(
        default=None,
        max_length=255,
        description="Localização física, opcional.",
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone IANA. Default 'UTC'.",
    )
    polling_enable: bool = Field(
        default=True,
        description="Se a Coleta deve buscar dados desta OLT.",
    )
    active: bool = Field(
        default=True,
        description="Desativação administrativa. Não libera o par (ip, porta).",
    )
    credential_id: UUID = Field(
        description="Credencial usada para conectar. Deve existir e estar ativa.",
    )

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, v: str) -> str:
        return _validate_timezone(v)


class OltCreate(OltBase):
    """Corpo do POST /olts. Acrescenta olt_model_id (imutável)."""

    olt_model_id: UUID = Field(
        description="Modelo de OLT (imutável após criação). Deve existir.",
    )


class OltUpdate(BaseModel):
    """Corpo do PATCH /olts/{id}. Todos os campos opcionais.

    olt_model_id NÃO aparece aqui. Se o cliente mandar olt_model_id no corpo,
    o Pydantic ignora (campo não declarado) e o modelo nunca é tocado."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    hostname: str | None = Field(default=None, max_length=255)
    ip: IPvAnyAddress | None = Field(default=None)
    management_port: int | None = Field(default=None, ge=1, le=65535)
    access_protocol: AccessProtocol | None = None
    firmware_version: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=255)
    timezone: str | None = Field(default=None)
    polling_enabled: bool | None = None
    active: bool | None = None
    credential_id: UUID | None = None

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _validate_timezone(v)


class OltRead(OltBase):
    """Resposta de leitura. Acrescenta identificadores e campos da Coleta.
    deleted_at NÃO é exposto."""

    model_config = ConfigDict(from_attributes=True)

    olt_id: UUID
    olt_model_id: UUID
    connection_status: ConnectionStatus
    last_seen_at: datetime | None
    last_collected_at: datetime | None
    created_at: datetime
    updated_at: datetime
