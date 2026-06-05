# Handlers globais para retorno em JSON padronizado
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import ValidationException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPExceptions

from app.api.middleware.request_id import REQUEST_ID_HEADER
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import get_logger, get_request_id

log = get_logger(__name__)


def _error_body(
    *,
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str:Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": get_request_id(),
        }
    }


def _response(status_code: int, body: dict[str:Any]) -> JSONResponse:
    # Repete o request_id no header
    request_id = get_request_id()
    headers = {REQUEST_ID_HEADER: request_id} if request_id else None
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    # Regista todos os handlers no app. Chama em create_app().

    @app.exception_handler(AppException)
    async def handle_app_exception(_request: Request, exc: AppException) -> JSONResponse:
        # Código 5XX loga como erro, se for 4XX loga como info, pois já é esperado
        if exc.status_code >= 500:
            log.error("app_exception", error_code=exc.error_code, message=exc.message)
        else:
            log.info("app_exception", error_code=exc.error_code, message=exc.message)

        return _response(
            exc.status_code,
            _error_body(code=exc.error_code, message=exc.message, details=exc.details),
        )

    @app.exception_handler(ValidationException)
    async def handle_validation_error(_request: Request, exc: ValidationException) -> JSONResponse:
        log.info("request_validation_error", error_count=len(exc.errors()))

        return _response(
            422,
            _error_body(
                code="validation_error",
                message="Falha de validação na requisição.",
                details=exc.errors(),
            ),
        )

    @app.exception_handler(StarletteHTTPExceptions)
    async def handle_http_exception(
        _request: Request, exc: StarletteHTTPExceptions
    ) -> JSONResponse:
        return _response(
            exc.status_code,
            _error_body(code="http_error", message=str(exc.detail())),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_exception")
        message = str(exc) if settings.app.expose_internal_errors else "Erro interno do servidor."

        return _response(
            500,
            _error_body(
                code="internal_error",
                message=message,
            ),
        )
