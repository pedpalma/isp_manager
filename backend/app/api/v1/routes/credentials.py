# Rotas REST de Credential.

# Convenções (mesmas do gabarito do Marco 9):
# - GET /credentials -> lista paginada (filtros por query)
# - GET /credentials/{id} -> detalhe
# - POST /credentials -> criação (201 Created)
# - PATCH /credentials/{id} -> atualização parcial

# DELETE não é exposto. Para "desativar" uma credencial, use PATCH com `{"active": false}`.

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.actor import Actor
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.inventory.schemas.credential import (
    CredentialCreate,
    CredentialRead,
    CredentialUpdate,
)
from app.domains.inventory.services.credential import CredentialService

router = APIRouter(prefix="/credentials", tags=["inventory:credentials"])


def get_service(
    session: AsyncSession = Depends(get_session),
) -> CredentialService:
    """Factory de service: lê a sessão (Depends) e injeta no service."""
    return CredentialService(session)


@router.get(
    "",
    response_model=Page[CredentialRead],
    summary="Lista credenciais (paginada)",
)
async def list_credentials(
    params: PageParams = Depends(page_params),
    only_active: bool = Query(
        default=False,
        description="Se true, retorna apenas credenciais ativas.",
    ),
    search: str | None = Query(
        default=None,
        max_length=200,
        description="Filtro `LIKE` em label OU username (case-insensitive).",
    ),
    service: CredentialService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),  # noqa: B008
) -> Page[CredentialRead]:
    items, total = await service.list_page(
        offset=params.offset,
        limit=params.limit,
        only_active=only_active,
        search=search,
        actor=actor,
    )
    return Page[CredentialRead](
        items=[CredentialRead.model_validate(c) for c in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get(
    "/{credential_id}",
    response_model=CredentialRead,
    summary="Detalhe de uma credencial",
)
async def get_credential(
    credential_id: UUID,
    service: CredentialService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> CredentialRead:
    c = await service.get(credential_id, actor=actor)
    return CredentialRead.model_validate(c)


@router.post(
    "",
    response_model=CredentialRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cria uma credencial",
)
async def create_credential(
    data: CredentialCreate,
    service: CredentialService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> CredentialRead:
    c = await service.create(data, actor=actor)
    return CredentialRead.model_validate(c)


@router.patch(
    "/{credential_id}",
    response_model=CredentialRead,
    summary="Atualiza parcialmente uma credencial",
)
async def update_credential(
    credential_id: UUID,
    data: CredentialUpdate,
    service: CredentialService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> CredentialRead:
    c = await service.update(credential_id, data, actor=actor)
    return CredentialRead.model_validate(c)
