# Service da ONU.

# Onde mora a regra de negócio:
# - Valida FKs: onu_model_id precisa EXISTIR (modelo descontinuado ainda vale);
#   pon_port_id precisa existir E a OLT pai estar viva (via PonPortRepository,
#   que filtra OLT viva por JOIN). FK inválida = 400.
# - Pré-checks de unicidade (serial; e (pon_port_id, onu_index) quando há índex)
#   entre ONUs vivas.
# - Traduz IntegrityError em erro de domínio inspecionando o nome da constraint,
#   cobrindo a corrida entre SELECT e INSERT/UPDATE (duas unicidades -> volta o
#   _violated_constraint por substring).
# - Controla a transação: commit em sucesso, rollback em falha.
# - soft delete: preenche deleted_at, liberando serial (pon_port, index).
# - Runtime: NUNCA insere onu_runtime_state (a trigger faz). Lê o estado num
#   SELECT pós-INSERT e embute nas respostas de ONU individual.

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.logging import get_logger
from app.domains.inventory.exceptions import (
    OnuIndexConflict,
    OnuModelReferenceInvalid,
    OnuNotFound,
    OnuSerialConflict,
    PonPortReferenceInvalid,
)
from app.domains.inventory.models.onu import Onu
from app.domains.inventory.repositories.onu import OnuRepository
from app.domains.inventory.repositories.onu_model import OnuModelRepository
from app.domains.inventory.repositories.pon_port import PonPortRepository
from app.domains.inventory.schemas.onu import (
    OnuCreate,
    OnuDetailRead,
    OnuRead,
    OnuRuntimeStateRead,
    OnuUpdate,
)

log = get_logger(__name__)

# Nomes das unicidades parciais no DDL. Usados para traduzir a corrida.
_UQ_SERIAL = "uq_onu_serial_active"
_UQ_INDEX = "uq_onu_index_per_pon_active"


class OnuService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = OnuRepository(session)
        self._onu_models = OnuModelRepository(session)
        self._pon_ports = PonPortRepository(session)

    # Leitura
    async def get(self, onu_id: UUID, *, actor: Actor) -> OnuDetailRead:
        del actor
        onu = await self._repo.get_by_id(onu_id)
        if onu is None:
            raise OnuNotFound(onu_id)
        return await self._build_detail(onu)

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        pon_port_id: UUID | None = None,
        serial: str | None = None,
        actor: Actor,
    ) -> tuple[Sequence[Onu], int]:
        del actor
        return await self._repo.list_page(
            offset=offset,
            limit=limit,
            pon_port_id=pon_port_id,
            serial=serial,
        )

    # Escrita
    async def create(self, data: OnuCreate, *, actor: Actor) -> OnuDetailRead:
        # FKs primeiro: erro de referencia (400) antes de conflito (409).
        await self._validate_onu_model(data.onu_model_id)
        await self._validate_pon_port_alive(data.pon_port_id)

        # Pre-checks de unicidade: mensagem nítida no caso normal.
        await self._check_serial_free(data.serial)
        if data.onu_index is not None:
            await self._check_pon_index_free(data.pon_port_id, data.onu_index)

        onu = Onu(
            onu_model_id=data.onu_model_id,
            pon_port_id=data.pon_port_id,
            serial=data.serial,
            onu_index=data.onu_index,
            description=data.description,
        )
        try:
            await self._repo.add(onu)
            await self._session.commit()
        except IntegrityError as exc:
            # Corrida: pre-check passou, outro request inseriu o mesmo serial
            # ou (pon_port, index) entre o SELECT e o INSERT.
            await self._session.rollback()
            self._raise_for_constraint(
                exc,
                serial=data.serial,
                pon_port_id=data.pon_port_id,
                onu_index=data.onu_index,
            )
            raise

        log.info(
            "onu.created",
            onu_id=str(onu.onu_id),
            serial=onu.serial,
            pon_port_id=str(onu.pon_port_id),
            onu_index=onu.onu_index,
            actor=actor.username,
        )
        return await self._build_detail(onu)

    async def update(self, onu_id: UUID, data: OnuUpdate, *, actor: Actor) -> OnuDetailRead:
        onu = await self._repo.get_by_id(onu_id)
        if onu is None:
            raise OnuNotFound(onu_id)

        payload = data.model_dump(exclude_unset=True)
        if not payload:
            return await self._build_detail(onu)

        # onu_index mudou para um valor nao-nulo -> pre-check de unicidade na PON,
        # ignorando a própria ONU. (serial e imutável: nao entra aqui.)
        if "onu_index" in payload:
            new_index = payload["onu_index"]
            if new_index is not None and new_index != onu.onu_index:
                await self._check_pon_index_free(
                    onu.pon_port_id, new_index, exclude_onu_id=onu.onu_id
                )

        for field, value in payload.items():
            setattr(onu, field, value)

        try:
            await self._repo.flush()
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            self._raise_for_constraint(
                exc,
                serial=onu.serial,
                pon_port_id=onu.pon_port_id,
                onu_index=payload.get("onu_index", onu.onu_index),
            )
            raise

        log.info(
            "onu.updated",
            onu_id=str(onu.onu_id),
            fields=list(payload.keys()),
            actor=actor.username,
        )
        return await self._build_detail(onu)

    async def soft_delete(self, onu_id: UUID, *, actor: Actor) -> None:
        """Soft delete. ONU inexistente ou ja deletada -> 404.
        Preenche deleted_at, liberando serial e (pon_port, index). Nao reativa.
        A linha de onu_runtime_state NAO e removida (CASCADE so no hard delete)."""
        onu = await self._repo.get_by_id(onu_id)
        if onu is None:
            raise OnuNotFound(onu_id)

        onu.deleted_at = datetime.now(timezone.utc)  # noqa: UP017
        await self._repo.flush()
        await self._session.commit()

        log.info(
            "onu.deleted",
            onu_id=str(onu.onu_id),
            serial=onu.serial,
            actor=actor.username,
        )

    # Helpers de leitura
    async def _build_detail(self, onu: Onu) -> OnuDetailRead:
        """Monta o detalhe com o estado operacional 1:1 (lido apos o INSERT,
        ja criado pela trigger). Sem runtime -> campo None."""
        runtime_orm = await self._repo.get_runtime(onu.onu_id)
        runtime = (
            OnuRuntimeStateRead.model_validate(runtime_orm) if runtime_orm is not None else None
        )
        base = OnuRead.model_validate(onu)
        return OnuDetailRead(**base.model_dump(), runtime=runtime)

    # Helpers de validação
    async def _validate_onu_model(self, onu_model_id: UUID) -> None:
        """onu_model_id precisa existir. Modelo descontinuado (active=false) ainda
        e valido: nao se checa active aqui (assimetria do Marco 11)."""
        model = await self._onu_models.get_by_id(onu_model_id)
        if model is None:
            raise OnuModelReferenceInvalid(onu_model_id)

    async def _validate_pon_port_alive(self, pon_port_id: UUID) -> None:
        """pon_port_id precisa existir E a OLT pai estar viva. O get_by_id do
        PonPortRepository ja faz o JOIN ate olt e filtra deleted_at IS NULL,
        então PON de OLT soft-deletada retorna None."""
        pon_port = await self._pon_ports.get_by_id(pon_port_id)
        if pon_port is None:
            raise PonPortReferenceInvalid(pon_port_id)

    async def _check_serial_free(self, serial: str) -> None:
        existing = await self._repo.get_active_by_serial(serial)
        if existing is not None:
            raise OnuSerialConflict(serial)

    async def _check_pon_index_free(
        self,
        pon_port_id: UUID,
        onu_index: int,
        *,
        exclude_onu_id: UUID | None = None,
    ) -> None:
        existing = await self._repo.get_active_by_pon_index(
            pon_port_id, onu_index, exclude_onu_id=exclude_onu_id
        )
        if existing is not None:
            raise OnuIndexConflict(pon_port_id, onu_index)

    def _raise_for_constraint(
        self,
        exc: IntegrityError,
        *,
        serial: str,
        pon_port_id: UUID,
        onu_index: int | None,
    ) -> None:
        """Inspeciona o nome da constraint na exceção e levanta o conflito de
        domínio correspondente. Se nenhuma constraint conhecida casar, nao
        levanta nada (o chamador propaga o IntegrityError cru)."""
        violated = self._violated_constraint(exc)
        if violated == _UQ_SERIAL:
            raise OnuSerialConflict(serial) from exc
        if violated == _UQ_INDEX:
            # onu_index aqui nunca e None (a unicidade so existe com index nao-nulo).
            raise OnuIndexConflict(pon_port_id, onu_index if onu_index is not None else -1) from exc

    @staticmethod
    def _violated_constraint(exc: IntegrityError) -> str | None:
        """Extrai o nome da constraint violada por substring na representação do
        erro original: robusto entre asyncpg e outros drivers."""
        raw = str(getattr(exc, "orig", exc))
        if _UQ_INDEX in raw:
            return _UQ_INDEX
        if _UQ_SERIAL in raw:
            return _UQ_SERIAL
        return None
