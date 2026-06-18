# Schemas (DTOs) da ONU e do seu estado operacional.

# Contrato do V1 (ONU como registro de EQUIPAMENTO):
# - Create: onu_model_id, pon_port_id, serial (obrigatórios) + onu_index, description (opcionais).
# - Update (PATCH): apenas onu_index e description (mutáveis). Imutáveis ficam
#   FORA do schema: onu_model_id, pon_port_id, serial. Mover de PON ou trocar
#   serial = soft delete + recriar (o serial e liberado pela unicidade parcial).
# - Read: campos do equipamento. As FKs de provisionamento (line/service/template)
#   aparecem como leitura (NULL ate o motor de provisionamento existir).
# - DetailRead: Read + `runtime` (estado operacional 1:1), preenchido nas
#   respostas de ONU individual (GET /{id}, POST, PATCH). A LISTA usa Read sem
#   runtime (mais barato; sem N+1).

# customer_id NAO aparece em nenhum schema: cadastro de cliente nao e do EMS.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domains.inventory.enums import ConnectionStatus, SyncStatus

# Guard-rails defensivos (o DDL não tem CHECK em serial/onu_index).
_SERIAL_MIN = 4
_SERIAL_MAX = 64
# onu_index: id da ONU dentro da PON. ge=0 aceita qualquer índice físico; le=1023 e guard-rail
# folgado (nenhuma PON real chega perto). Mais permissivo que os índices de topologia (le-255)
# porque XGS-PON admite muitas ONUs por PON.
_ONU_INDEX_MIN = 0
_ONU_INDEX_MAX = 1023
_DESCRIPTION_MAX = 500


class OnuCreate(BaseModel):
    onu_model_id: UUID = Field(description="Modelo da ONU (catálogo). Precisa existir.")
    pon_port_id: UUID = Field(
        description="Porta PON onde a ONU está instalada. Precisa existir e a OLT pai estar viva."
    )
    serial: str = Field(
        min_length=_SERIAL_MAX,
        max_length=_SERIAL_MAX,
        description="Número de série do aparelho. Único apenas entre ONUs vivas.",
    )
    onu_index: int | None = Field(
        default=None,
        ge=_ONU_INDEX_MIN,
        le=_ONU_INDEX_MAX,
        description="ID da ONU dentro da PON. Opcional (atribuído no provisionamento).",
    )
    description: str | None = Field(
        default=None,
        max_length=_DESCRIPTION_MAX,
        description="Texto livre.",
    )

    @field_validator("serial", mode="before")
    @classmethod
    def _strip_serial(cls, v: object) -> object:
        # Strip ANTES da checagem de tamanho (mode="before"): " ab " não passa
        # como serial válido só por causa dos espaços.
        return v.strip() if isinstance(v, str) else v

    class OnuUpdate(BaseModel):
        # Fora daqui (imutáveis): onu_model_id, pon_port_id, serial.
        onu_index: int | None = Field(
            default=None,
            ge=_ONU_INDEX_MIN,
            le=_ONU_INDEX_MAX,
            description="Novo índice na PON. Enviar null limpa o índice.",
        )
        description: str | None = Field(
            default=None,
            max_length=_DESCRIPTION_MAX,
            description="Nova descrição. Enviar null limpa.",
        )


class OnuRuntimeStateRead(BaseModel):
    """Estado operacional atual da ONU (somente leitura). Preenchido pela Coleta."""

    model_config = ConfigDict(from_attributes=True)

    connection_status: ConnectionStatus
    oper_state: str | None
    sync_status: SyncStatus
    last_signal_at: datetime | None
    last_down_reason: str | None
    distance_m: float | None
    last_collected_at: datetime | None
    updated_at: datetime


class OnuRead(BaseModel):
    """Representação da ONU em listagens. Sem `runtime`."""

    model_config = ConfigDict(from_attributes=True)

    onu_id: UUID
    onu_model_id: UUID
    pon_port_id: UUID
    serial: str
    onu_index: int | None
    description: str | None
    provisioned: bool
    # Entradas do motor de provisionamento.
    line_profile_id: UUID | None
    service_profile_id: UUID | None
    provisioning_template_id: UUID | None
    # Preenchidos pela Coleta.
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OnuDetailRead(OnuRead):
    """Detalhe da ONU: Read + estado operacional 1:1."""

    runtime: OnuRuntimeStateRead | None = Field(
        default=None,
        description="Estado operacional atual. Presente nas respostas de ONU individual.",
    )
