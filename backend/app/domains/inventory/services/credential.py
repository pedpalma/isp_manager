# Service do Credential.

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.logging import get_logger
from app.domains.audit.enums import AuditAction, AuditResult
from app.domains.audit.services.audit_log import AuditLogService
from app.domains.inventory.enums import AuthType
from app.domains.inventory.exceptions import (
    CredentialAuthMismatch,
    CredentialInUse,
    CredentialNotFound,
)
from app.domains.inventory.models.credential import Credential
from app.domains.inventory.repositories.credential import CredentialRepository
from app.domains.inventory.schemas.credential import (
    CredentialCreate,
    CredentialUpdate,
)

log = get_logger(__name__)

# Campos cujo VALOR não pode ser logado (são ponteiros para segredos).
# Quando aparecem num PATCH, o log registra só o nome.
_SECRET_FIELDS = frozenset({"secret_ref", "enable_secret_ref", "private_key_ref"})


def _dump_credential_fields(c: "Credential", fields: "Iterable[str]") -> dict[str, Any]:  # noqa: UP037
    """Serializa campos do Credential para JSONB do audit_log."""
    out: dict[str, Any] = {}
    for f in fields:
        v = getattr(c, f)
        if isinstance(v, AuthType):
            v = v.value
        out[f] = v
    return out


class CredentialService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = CredentialRepository(session)
        self._audit = AuditLogService(session)

    # Leitura
    async def get(self, credential_id: UUID, *, actor: Actor) -> Credential:
        del actor  # reservado para autorização futura por escopo
        c = await self._repo.get_by_id(credential_id)
        if c is None:
            raise CredentialNotFound(credential_id)
        return c

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        only_active: bool = False,
        search: str | None = None,
        actor: Actor,
    ) -> tuple[Sequence[Credential], int]:
        del actor
        return await self._repo.list_page(
            offset=offset,
            limit=limit,
            only_active=only_active,
            search=search,
        )

    # Escrita
    async def create(self, data: CredentialCreate, *, actor: Actor) -> Credential:
        """Cria uma credencial.
        A validação cruzada `auth_type` x `private_key_ref` já aconteceu
        no schema (`CredentialCreate` model_validator). Aqui é só persistir."""
        c = Credential(
            label=data.label,
            username=data.username,
            secret_ref=data.secret_ref,
            enable_secret_ref=data.enable_secret_ref,
            auth_type=data.auth_type,
            private_key_ref=data.private_key_ref,
            active=data.active,
        )
        self._session.add(c)
        await self._session.flush()

        # audit ANTES do commit; scrub_secrets mascara os ponteiros.
        await self._audit.record(
            actor=actor,
            action=AuditAction.CREDENTIAL_CREATED,
            result=AuditResult.SUCCESS,
            entity_type="credential",
            entity_id=c.credential_id,
            after=_dump_credential_fields(
                c,
                [
                    "label",
                    "username",
                    "secret_ref",
                    "enable_secret_ref",
                    "auth_type",
                    "private_key_ref",
                    "active",
                ],
            ),
        )

        await self._session.commit()

        log.info(
            "credential.created",
            credential_id=str(c.credential_id),
            label=c.label,
            auth_type=c.auth_type.value,
            actor=actor.username,
        )
        return c

    async def update(
        self,
        credential_id: UUID,
        data: CredentialUpdate,
        *,
        actor: Actor,
    ) -> Credential:
        """Atualiza parcialmente uma credencial (semântica PATCH)."""
        c = await self._repo.get_by_id(credential_id)
        if c is None:
            raise CredentialNotFound(credential_id)

        payload = data.model_dump(exclude_unset=True)

        # `payload[k]` se o cliente mandou; caso contrário, o valor atual.
        # Importante: usar `in payload` (não `.get()`), porque o cliente
        # pode mandar `private_key_ref=null` explicitamente para LIMPAR.
        final_auth_type: AuthType = payload["auth_type"] if "auth_type" in payload else c.auth_type  # noqa: SIM401
        final_private_key_ref: str | None = (
            payload["private_key_ref"] if "private_key_ref" in payload else c.private_key_ref  # noqa: SIM401
        )

        if final_auth_type is AuthType.SSH_KEY and not final_private_key_ref:
            raise CredentialAuthMismatch(
                credential_id=c.credential_id,
                auth_type=final_auth_type.value,
            )

        # Desativar uma credencial em uso por OLT viva é proibido.
        # Checa ANTES de qualquer mutação, então não há nada para reverter quando bloqueia.
        if payload.get("active") is False and c.active is True:
            from app.domains.inventory.repositories.olt import (  # noqa: PLC0415
                OltRepository,
            )

            olt_repo = OltRepository(self._session)
            if await olt_repo.has_active_for_credential(c.credential_id):
                raise CredentialInUse(c.credential_id)

        touched_fields = list(payload.keys())
        before = _dump_credential_fields(c, touched_fields)

        for field, value in payload.items():
            setattr(c, field, value)

        await self._repo.flush()

        after = _dump_credential_fields(c, touched_fields)

        await self._audit.record(
            actor=actor,
            action=AuditAction.CREDENTIAL_UPDATED,
            result=AuditResult.SUCCESS,
            entity_type="credential",
            entity_id=c.credential_id,
            before=before,
            after=after,
        )

        await self._session.commit()

        log.info(
            "credential.updated",
            credential_id=str(c.credential_id),
            fields=touched_fields,
            touched_secret_fields=sorted(f for f in touched_fields if f in _SECRET_FIELDS),
            actor=actor.username,
        )
        return c
