# Rotas de leitura de audit_log

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_admin
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session
from app.domains.audit.schemas.audit_log import AuditLogRead
from app.domains.audit.services.audit_log import AuditLogService

router = APIRouter(prefix="/audit-log", tags=["audit:log"])


def get_audit_log_service(
    session: AsyncSession = Depends(get_session),
) -> AuditLogService:
    return AuditLogService(session)


@router.get("", response_model=Page[AuditLogRead], summary="Lista audit_log")
async def list_audit_log(
    app_user_id: UUID | None = Query(default=None),
    olt_id: UUID | None = Query(default=None),
    onu_id: UUID | None = Query(default=None),
    provisioning_order_id: UUID | None = Query(default=None),
    entity_type: str | None = Query(default=None, max_length=64),
    entity_id: UUID | None = Query(default=None),
    action: str | None = Query(default=None, max_length=64),
    result: str | None = Query(default=None, max_length=32),
    request_id: str | None = Query(default=None, max_length=128),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    params: PageParams = Depends(page_params),
    current: CurrentUser = Depends(require_admin),
    service: AuditLogService = Depends(get_audit_log_service),
) -> Page[AuditLogRead]:
    return await service.list_page(
        params=params,
        actor=current.to_actor(),
        app_user_id=app_user_id,
        olt_id=olt_id,
        onu_id=onu_id,
        provisioning_order_id=provisioning_order_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        result=result,
        request_id=request_id,
        created_from=created_from,
        created_to=created_to,
    )


@router.get(
    "/{audit_log_id}",
    response_model=AuditLogRead,
    summary="Detalhe de um registro de auditoria",
)
async def get_audit_log(
    audit_log_id: UUID,
    current: CurrentUser = Depends(require_admin),
    service: AuditLogService = Depends(get_audit_log_service),
) -> AuditLogRead:
    return await service.get(audit_log_id, actor=current.to_actor())
