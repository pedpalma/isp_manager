# Schema Pydantic para provisioning_order.snapshot_params (JSONB).


from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SnapshotParams(BaseModel):
    """Payload embarcado na coluna snapshot_params do provisioning_order.

    Validado apenas no ingest da API. O worker relê como dict[str, Any].
    """

    model_config = ConfigDict(extra="forbid")

    line_profile_id: UUID = Field(
        description="line_profile ativo (validado contra olt_id da ordem no service).",
    )
    service_profile_id: UUID = Field(
        description="service_profile ativo (validado contra olt_id da ordem no service).",
    )
    vlan_id: UUID = Field(
        description="vlan ativa da OLT (validado contra olt_id da ordem no service).",
    )
    onu_index: int = Field(
        ge=1,
        le=128,
        description=(
            "Índice de ONU dentro da PON. Faixa 1-128 cobre Fiberhome (128) "
            "e ZTE (64) no padrão XG-PON. Valor exato validado pelo template."
        ),
    )
    custom_id: str = Field(
        min_length=1,
        max_length=64,
        description="Identificador humano (ex. contrato do ERP).",
    )

    # Gancho M20 (integração ERP). Preservado no snapshot para sync sem JOIN.
    external_customer_id: str | None = Field(
        default=None,
        max_length=128,
        description="ID do cliente no ERP externo (IXC futuro). Opcional no V1.",
    )
