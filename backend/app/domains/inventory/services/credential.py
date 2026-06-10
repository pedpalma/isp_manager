# Service do Credential.

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.logging import get_logger
from app.domains.inventory.enums import AuthType
from app.domains.inventory.exceptions import (
    CredentialAuthMismatch,
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


class CredentialService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = CredentialRepository(session)

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

        for field, value in payload.items():
            setattr(c, field, value)

        await self._repo.flush()
        await self._session.commit()

        # Log: nunca emitir valores de ponteiros. Só os NOMES dos campos
        # tocados (`fields`). Os secretos não-tocados também não vazam
        touched_fields = list(payload.keys())
        log.info(
            "credential.updated",
            credential_id=str(c.credential_id),
            fields=touched_fields,
            touched_secret_fields=sorted(f for f in touched_fields if f in _SECRET_FIELDS),
            actor=actor.username,
        )
        return c
