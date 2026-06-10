# Schemas Pydantic v2 do Credential.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domains.inventory.enums import AuthType


class CredentialBase(BaseModel):
    """Campos comuns à criação e à leitura (NÃO inclui ponteiros)."""

    label: str = Field(
        min_length=1,
        max_length=200,
        description="Rótulo amigável da credencial. NÃO precisa ser único.",
    )
    username: str = Field(
        min_length=1,
        max_length=200,
        description="Usuário usado para conectar ao equipamento.",
    )
    auth_type: AuthType = Field(
        default=AuthType.PASSWORD,
        description="Tipo de autenticação. Valores: password, ssh_key, certificate.",
    )
    active: bool = Field(
        default=True,
        description="Se FALSE, fica oculto em listagens com `only_active=true`.",
    )


class CredentialCreate(CredentialBase):
    """Corpo do POST /credentials.
    Inclui os ponteiros (`secret_ref`, etc.) que NÃO aparecem no Read.
    O cliente é responsável por enviar referências para o cofre, não
    a senha em si."""

    secret_ref: str = Field(
        min_length=1,
        max_length=200,
        description=(
            "Ponteiro para o segredo principal no cofre. Em dev, nome de "
            "uma variável de ambiente (ex.: 'OLT_LAB_PASSWORD'). NUNCA "
            "a senha em texto."
        ),
    )
    enable_secret_ref: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="Ponteiro para a senha de modo privilegiado, se houver.",
    )
    private_key_ref: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description=(
            "Ponteiro para a chave privada SSH (se auth_type=ssh_key). "
            "Obrigatório quando auth_type=ssh_key."
        ),
    )

    @model_validator(mode="after")
    def _check_auth_type_consistency(self) -> CredentialCreate:
        """Validação cruzada D4: ssh_key exige private_key_ref."""
        if self.auth_type is AuthType.SSH_KEY and not self.private_key_ref:
            raise ValueError("Quando auth_type='ssh_key', private_key_ref é obrigatório.")
        return self


class CredentialUpdate(BaseModel):
    """Corpo do PATCH /credentials/{id}. Todos os campos opcionais.
    A validação cruzada NÃO acontece aqui (não temos o estado atual no
    schema). O service mescla payload + estado atual e valida."""

    label: str | None = Field(default=None, min_length=1, max_length=200)
    username: str | None = Field(default=None, min_length=1, max_length=200)
    auth_type: AuthType | None = None
    active: bool | None = None

    # Ponteiros são atualizáveis (decisão D7: rotação de credencial).
    secret_ref: str | None = Field(default=None, min_length=1, max_length=200)
    enable_secret_ref: str | None = Field(default=None, min_length=1, max_length=200)
    private_key_ref: str | None = Field(default=None, min_length=1, max_length=200)


class CredentialRead(CredentialBase):
    """Resposta de leitura. NÃO expõe ponteiros (D3).
    Inclui `last_validated_at`."""

    model_config = ConfigDict(from_attributes=True)

    credential_id: UUID
    last_validated_at: datetime | None
    created_at: datetime
    updated_at: datetime
