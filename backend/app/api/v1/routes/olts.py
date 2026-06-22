# Rotas REST de OLT.

# Convenções (mesmas do gabarito):
# - GET /olts -> lista paginada (filtros por query)
# - GET /olts/{id} -> detalhe
# - POST /olts -> criação (201 Created)
# - PATCH /olts/{id} -> atualização parcial
# - DELETE /olts/{id} -> soft delete (204 No Content)

# Diferente de credential, DELETE É exposto: significa soft delete,
# que libera name e o par (ip, porta).
# Para apenas pausar sem liberar, use PATCH com {"active": false}.

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_actor
from app.core.actor import Actor
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.inventory.schemas.olt import OltCreate, OltRead, OltUpdate
from app.domains.inventory.services.olt import OltService

router = APIRouter(prefix="/olts", tags=["inventory:olts"])


def get_service(
    session: AsyncSession = Depends(get_session),
) -> OltService:
    return OltService(session)


@router.get(
    "",
    response_model=Page[OltRead],
    summary="Lista OLTs (paginada)",
)
async def list_olts(
    params: PageParams = Depends(page_params),
    only_active: bool = Query(
        default=False,
        description="Se true, retorna apenas OLTs com active=true.",
    ),
    search: str | None = Query(
        default=None,
        max_length=200,
        description="Filtro `LIKE` em name OU hostname (case-insensitive).",
    ),
    service: OltService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),  # noqa: B008
) -> Page[OltRead]:
    items, total = await service.list_page(
        offset=params.offset,
        limit=params.limit,
        only_active=only_active,
        search=search,
        actor=actor,
    )
    return Page[OltRead](
        items=[OltRead.model_validate(o) for o in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get(
    "/{olt_id}",
    response_model=OltRead,
    summary="Detalhe de uma OLT",
)
async def get_olt(
    olt_id: UUID,
    service: OltService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> OltRead:
    olt = await service.get(olt_id, actor=actor)
    return OltRead.model_validate(olt)


@router.post(
    "",
    response_model=OltRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cria uma OLT",
)
async def create_olt(
    data: OltCreate,
    service: OltService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> OltRead:
    olt = await service.create(data, actor=actor)
    return OltRead.model_validate(olt)


@router.patch(
    "/{olt_id}",
    response_model=OltRead,
    summary="Atualiza parcialmente uma OLT",
)
async def update_olt(
    olt_id: UUID,
    data: OltUpdate,
    service: OltService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> OltRead:
    olt = await service.update(olt_id, data, actor=actor)
    return OltRead.model_validate(olt)


@router.delete(
    "/{olt_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete de uma OLT (libera name e par ip+porta)",
)
async def delete_olt(
    olt_id: UUID,
    service: OltService = Depends(get_service),
    actor: Actor = Depends(get_current_actor),
) -> None:
    await service.soft_delete(olt_id, actor=actor)
    return None
