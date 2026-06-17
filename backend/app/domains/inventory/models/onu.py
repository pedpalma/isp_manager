# Model ORM da tabela `onu`. A tabela mais central do sistema.


# Unicidades PARCIAIS (WHERE deleted_at IS NULL) vivem no DDL, nao aqui:
# - uq_onu_serial_active -> (serial) com deleted_at IS NULL
# - uq_onu_index_per_pon_active -> (pon_port_id, onu_index) com deleted_at IS NULL AND onu_index IS NOT NULL
# Soft delete LIBERA as duas chaves.

# Nota sobre FKs sem ForeignKey() no ORM:
# - provisioning_template_id e mapeada como UUID simples, SEM ForeignKey() no ORM,
#   porque a tabela `provisioning_template` ainda nao tem model, adiada para
#   o motor de provisionamento). A FK existe no banco e e o banco que a garante.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin


class Onu(Base, TimestampMixin, SoftDeleteMixin):
    """ONU instalada na rede, registrada no inventario.

    Identidade do equipamento: (onu_model_id, pon_port_id, serial).
    - serial e a identidade do aparelho físico; único apenas entre ONUs vivas
    (a unicidade parcial libera o serial apos soft delete, permitindo realocar
    o mesmo aparelho ou reaproveitar o numero de serie).

    - onu_index e o id da ONU dentro da PON; atribuído no provisionamento, por
    isso nullable. Varias ONUs com onu_index NULL na mesma PON sao permitidas.

    Colunas de outros donos (NAO entram no cadastro via API):
    - provisioned, first_seen_at, last_seen_at: preenchidas pelo motor de provisionamento e pela Coleta.

    - line_profile_id, service_profile_id, provisioning_template_id: entradas do motor de provisionamento;
    ficam NULL ate o marco correspondente."""

    __tablename__ = "onu"

    onu_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # FKs com model existente -> ForeignKey() normal.
    onu_model_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("onu_model.onu_model_id"),
        nullable=False,
    )
    pon_port_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("pon_port.pon_port_id"),
        nullable=False,
    )
    line_profile_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("line_profile.line_profile_id"),
        nullable=True,
    )
    service_profile_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("service_profile.service_profile_id"),
        nullable=True,
    )

    # FK sem model: coluna UUID simples.
    # O banco garante a integridade referencial.
    provisioning_template_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )

    serial: Mapped[str] = mapped_column(Text, nullable=False)
    onu_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # App não envia INSERT -> server_default OBRIGATÓRIO:
    # o ORM  precisa de RETURNING para popular o valor pós-flush. Sem isso,
    # o SQLAlchemy enviaria NULL explicito e violaria o NOT NULL.
    provisioned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    #  Preenchidos pela Coleta.
    first_seen_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    # created_at / updated_at vem do TimestampMixin (server_default now()).
    # deleted_at vem do SoftDeleteMixin.

    def __repr__(self) -> str:
        return (
            f"<Onu serial={self.serial!r} pon_port_id={self.pon_port_id} "
            f"onu_index={self.onu_index} provisioned={self.provisioned} "
            f"deleted={self.is_deleted}>"
        )
