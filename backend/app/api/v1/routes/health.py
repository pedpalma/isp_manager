from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class HealthDBResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    details: str | None = None


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@router.get(
    "/health/db",
    response_model=HealthDBResponse,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthDBResponse},
    },
)
async def health_db(session: AsyncSession = Depends(get_session)) -> HealthDBResponse:  # noqa: B008
    try:
        result = await session.execute(text("SELECT 1"))
        result.scalar_one()
        return HealthDBResponse(status="ok")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailble",
        ) from exc
