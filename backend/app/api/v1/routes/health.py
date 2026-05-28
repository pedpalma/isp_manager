import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    # Liveness response

    status: Literal["ok"] = "ok"


class HealthDBResponse(BaseModel):
    # Readiness response (banco

    status: Literal["ok"]
    database: Literal["reachable"] = "reachable"


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
)
async def health() -> HealthResponse:
    return HealthResponse()


@router.get(
    "/health/db",
    response_model=HealthDBResponse,
    summary="Readiness probe (banco de dados)",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Banco indisponível.",
        },
    },
)
async def health_db(session: AsyncSession = Depends(get_session)) -> HealthDBResponse:  # noqa: B008
    try:
        result = await session.execute(text("SELECT 1"))
        result.scalar_one()
        return HealthDBResponse(status="ok")
    except Exception:
        # Loga o erro real internamente; resposta pública é genérica para
        # não vazar detalhes de infraestrutura.
        logger.exception("Database health check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from None
