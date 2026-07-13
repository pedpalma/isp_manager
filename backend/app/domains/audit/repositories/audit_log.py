# Repositório do audit_log.

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.audit.models.audit_log import AuditLog


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # write
    def add(self, entry: AuditLog) -> None:
        """Adiciona à sessão. Commit é responsabilidade do service."""
        self._session.add(entry)

    async def flush(self) -> None:
        await self._session.flush()

    # read
    async def get_by_id(self, audit_log_id: UUID) -> AuditLog | None:
        stmt = select(AuditLog).where(AuditLog.audit_log_id == audit_log_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self,
        *,
        app_user_id: UUID | None = None,
        olt_id: UUID | None = None,
        onu_id: UUID | None = None,
        provisioning_order_id: UUID | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        action: str | None = None,
        result: str | None = None,
        request_id: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[Sequence[AuditLog], int]:
        """Lista paginada com filtros; ordena por created_at DESC (idx dedicado)."""
        base_stmt: Select[tuple[AuditLog]] = select(AuditLog)
        base_stmt = self._apply_filters(
            base_stmt,
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

        # Total
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = int((await self._session.execute(count_stmt)).scalar_one() or 0)

        # Items
        items_stmt = base_stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
        items = (await self._session.execute(items_stmt)).scalars().all()

        return items, total

    @staticmethod
    def _apply_filters(
        stmt: Select[tuple[AuditLog]],
        *,
        app_user_id: UUID | None,
        olt_id: UUID | None,
        onu_id: UUID | None,
        provisioning_order_id: UUID | None,
        entity_type: str | None,
        entity_id: UUID | None,
        action: str | None,
        result: str | None,
        request_id: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> Select[tuple[AuditLog]]:
        if app_user_id is not None:
            stmt = stmt.where(AuditLog.app_user_id == app_user_id)
        if olt_id is not None:
            stmt = stmt.where(AuditLog.olt_id == olt_id)
        if onu_id is not None:
            stmt = stmt.where(AuditLog.onu_id == onu_id)
        if provisioning_order_id is not None:
            stmt = stmt.where(AuditLog.provisioning_order_id == provisioning_order_id)
        if entity_type is not None:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            stmt = stmt.where(AuditLog.entity_id == entity_id)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        if result is not None:
            stmt = stmt.where(AuditLog.result == result)
        if request_id is not None:
            stmt = stmt.where(AuditLog.request_id == request_id)
        if created_from is not None:
            stmt = stmt.where(AuditLog.created_at >= created_from)
        if created_to is not None:
            stmt = stmt.where(AuditLog.created_at <= created_to)
        return stmt
