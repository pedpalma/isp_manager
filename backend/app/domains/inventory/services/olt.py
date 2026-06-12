# Service da OLT.

# Onde mora a regra de negócio:
# - Valida FKs: olt_model_id precisa existir; credential_id precisa existir E estar active=true.
# - Pré-checks de unicidade (name e par ip+porta) entre OLTs vivas.
# - Traduz IntegrityError em erro de domínio inspecionando o nome da constraint, cobrindo a corrida entre SELECT e INSERT/UPDATE.
# - Controla a transação: commit em sucesso, rollback em falha.
# - soft delete: preenche deleted_at, libera name e par.

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.logging import get_logger
from app.domains.inventory.exceptions import (
    CredentialInactive,
    CredentialReferenceInvalid,
    OltAddressConflict,
    OltModelReferenceInvalid,
    OltNameConflict,
    OltNotFound,
)
from app.domains.inventory.models.olt import Olt
from app.domains.inventory.repositories.credential import CredentialRepository
from app.domains.inventory.repositories.olt import OltRepository
from app.domains.inventory.repositories.olt_model import OltModelRepository
from app.domains.inventory.schemas.olt import OltCreate, OltUpdate

log = get_logger(__name__)

# Nomes das constraints parciais no DDL. Usados para traduzir a corrida.
_UQ_NAME = "uq_olt_name_active"
_UQ_IP_PORT = "uq_olt_ip_port_active"


class OltService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = OltRepository(session)
        self._olt_models = OltModelRepository(session)
        self._credentials = CredentialRepository(session)

    # Leitura
    async def get(self, olt_id: UUID, *, actor: Actor) -> Olt:
        del actor
        olt = await self._repo.get_by_id(olt_id)
        if olt is None:
            raise OltNotFound(olt_id)
        return olt

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        only_active: bool = False,
        search: str | None = None,
        actor: Actor,
    ) -> tuple[Sequence[Olt], int]:
        del actor
        return await self._repo.list_page(
            offset=offset,
            limit=limit,
            only_active=only_active,
            search=search,
        )

    # Escrita
    async def create(self, data: OltCreate, *, actor: Actor) -> Olt:
        # FKs primeiro: erro de referência (400) antes de conflito (409).
        await self._validate_olt_model(data.olt_model_id)
        await self._validate_credential_active(data.credential_id)

        # Pré-checks de unicidade: mensagem nítida no caso normal.
        await self._check_name_free(data.name)
        await self._check_ip_port_free(str(data.ip), data.management_port)

        olt = Olt(
            name=data.name,
            hostname=data.hostname,
            ip=str(data.ip),
            management_port=data.management_port,
            access_protocol=data.access_protocol,
            firmware_version=data.firmware_version,
            location=data.location,
            timezone=data.timezone,
            polling_enabled=data.polling_enabled,
            active=data.active,
            olt_model_id=data.olt_model_id,
            credential_id=data.credential_id,
        )
        try:
            await self._repo.add(olt)
            await self._session.commit()
        except IntegrityError as exc:
            # Corrida: pré-check passou, outro request inseriu o mesmo
            # name ou (ip, porta) entre o SELECT e o INSERT.
            await self._session.rollback()
            self._raise_for_constraint(
                exc, name=data.name, ip=str(data.ip), port=data.management_port
            )
            raise

        log.info(
            "olt.created",
            olt_id=str(olt.olt_id),
            name=olt.name,
            ip=olt.ip,
            management_port=olt.management_port,
            actor=actor.username,
        )
        return olt

    async def update(
        self,
        olt_id: UUID,
        data: OltUpdate,
        *,
        actor: Actor,
    ) -> Olt:
        olt = await self._repo.get_by_id(olt_id)
        if olt is None:
            raise OltNotFound(olt_id)

        payload = data.model_dump(exclude_unset=True)

        # credential_id mudou -> revalida existência + ativa.
        if "credential_id" in payload and payload["credential_id"] != olt.credential_id:
            await self._validate_credential_active(payload["credential_id"])

        # name mudou -> pré-check de unicidade entre vivas.
        if "name" in payload and payload["name"] != olt.name:
            await self._check_name_free(payload["name"])

        # ip e/ou porta mudaram -> recompõe o par final e pré-checa, ignorando a própria OLT.
        ip_touched = "ip" in payload
        port_touched = "management_port" in payload
        if ip_touched or port_touched:
            final_ip = str(payload["ip"]) if ip_touched else olt.ip
            final_port = payload["management_port"] if port_touched else olt.management_port
            if (final_ip, final_port) != (olt.ip, olt.management_port):
                await self._check_ip_port_free(final_ip, final_port, exclude_olt_id=olt.olt_id)

        # Aplica. ip vem como IPvAnyAddress no payload -> normaliza para str.
        for field, value in payload.items():
            if field == "ip" and value is not None:
                value = str(value)
            setattr(olt, field, value)

        try:
            await self._repo.flush()
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            self._raise_for_constraint(
                exc,
                name=payload.get("name", olt.name),
                ip=str(payload.get("ip", olt.ip)),
                port=payload.get("management_port", olt.management_port),
            )
            raise

        log.info(
            "olt.updated",
            olt_id=str(olt.olt_id),
            fields=list(payload.keys()),
            actor=actor.username,
        )
        return olt

    async def soft_delete(self, olt_id: UUID, *, actor: Actor) -> None:
        """Soft delete. OLT inexistente ou já deletada -> 404.
        Preenche deleted_at, liberando name e (ip, porta). Não reativa."""
        olt = await self._repo.get_by_id(olt_id)
        if olt is None:
            raise OltNotFound(olt_id)

        olt.deleted_at = datetime.now(timezone.utc)  # noqa: UP017
        await self._repo.flush()
        await self._session.commit()

        log.info(
            "olt.deleted",
            olt_id=str(olt.olt_id),
            name=olt.name,
            actor=actor.username,
        )

    # Helpers de validação
    async def _validate_olt_model(self, olt_model_id: UUID) -> None:
        """olt_model_id precisa existir. Modelo descontinuado ainda é válido: não é checado active aqui."""
        model = await self._olt_models.get_by_id(olt_model_id)
        if model is None:
            raise OltModelReferenceInvalid(olt_model_id)

    async def _validate_credential_active(self, credential_id: UUID) -> None:
        """credential_id precisa existir E estar active=true."""
        cred = await self._credentials.get_by_id(credential_id)
        if cred is None:
            raise CredentialReferenceInvalid(credential_id)
        if not cred.active:
            raise CredentialInactive(credential_id)

    async def _check_name_free(self, name: str) -> None:
        existing = await self._repo.get_active_by_name(name)
        if existing is not None:
            raise OltNameConflict(name)

    async def _check_ip_port_free(
        self,
        ip: str,
        management_port: int,
        *,
        exclude_olt_id: UUID | None = None,
    ) -> None:
        existing = await self._repo.get_active_by_ip_port(ip, management_port)
        if existing is not None and existing.olt_id != exclude_olt_id:
            raise OltAddressConflict(ip, management_port)

    def _raise_for_constraint(
        self,
        exc: IntegrityError,
        *,
        name: str,
        ip: str,
        port: int,
    ) -> None:
        """Inspeciona o nome da constraint na exceção e levanta o conflito
        de domínio correspondente. Se nenhuma constraint conhecida
        casar, não levanta nada (o chamador propaga o IntegrityError cru)."""
        violated = self._violated_constraint(exc)
        if violated == _UQ_NAME:
            raise OltNameConflict(name) from exc
        if violated == _UQ_IP_PORT:
            raise OltAddressConflict(ip, port) from exc

    @staticmethod
    def _violated_constraint(exc: IntegrityError) -> str | None:
        """Extrai o nome da constraint violada. Abordagem por substring na
        representação do erro original: robusta entre asyncpg e outros
        drivers, sem depender de atributos internos específicos."""
        raw = str(getattr(exc, "orig", exc))
        if _UQ_IP_PORT in raw:
            return _UQ_IP_PORT
        if _UQ_NAME in raw:
            return _UQ_NAME
        return None
