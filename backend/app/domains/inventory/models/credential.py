# Model ORM da tabela `credential`.
# Este model apenas MAPEIA as colunas para que o SQLAlchemy possa fazer SELECT/INSERT/UPDATE.


from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, Text, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin
from app.domains.inventory.enums import AuthType


class Credential(Base, TimestampMixin):
    """Credencial de acesso a um equipamento de rede (OLT).
    Senhas e chaves NUNCA ficam aqui. Os campos `*_ref` são REFERÊNCIAS
    para um cofre/store externo (em dev: nome de variável de ambiente;
    em prod: caminho no Vault/KMS). A aplicação resolve o ponteiro só
    no momento de conectar à OLT (Marco da Coleta).
    """

    __tablename__ = "credential"

    # `server_default=text("gen_random_uuid()")` é OBRIGATÓRIO aqui. Sem ele o ORM envia NULL explícito no INSERT.
    credential_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    label: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[str] = mapped_column(Text, nullable=False)
    secret_ref: Mapped[str] = mapped_column(Text, nullable=False)

    # Senha de "enable" (modo privilegiado), opcional. Usado em alguns
    # equipamentos que exigem segundo nível de autenticação para
    # comandos de configuração.
    enable_secret_ref: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ENUM nativo. `create_type=False`: o tipo já foi criado pelo DDL.
    # `values_callable`: grava a STRING ("password"), não o nome ("PASSWORD").
    # `default=AuthType.PASSWORD` no ORM (safety net; o schema também
    # tem default). NÃO é declarado `server_default` porque o ORM sempre
    # envia o valor (não dependemos do DEFAULT do banco).
    auth_type: Mapped[AuthType] = mapped_column(
        postgresql.ENUM(
            AuthType,
            name="auth_type_enum",
            create_type=False,
            values_callable=lambda e: [v.value for v in e],
        ),
        nullable=False,
        default=AuthType.PASSWORD,
    )

    private_key_ref: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Última vez que a credencial foi validada com sucesso contra o
    # equipamento. Preenchido pelo marco de Coleta. Fica None até lá.
    last_validated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    # created_at e updated_at vêm do TimestampMixin.

    def __repr__(self) -> str:
        return (
            f"<Credential label={self.label!r} "
            f"auth_type={self.auth_type.value} active={self.active}>"
        )
