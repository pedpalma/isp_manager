# Handlers globais de exceção.
#
# Padroniza TODA resposta de erro no formato:
#   {
#     "error": {
#       "code": "not_found",
#       "message": "...",
#       "details": {...} | null,
#       "request_id": "..."        # correlaciona com os logs
#     }
#   }
#
# Cobre quatro casos:
#   - AppException            -> erros de negócio (status/código vêm da exceção)
#   - RequestValidationError  -> corpo/query inválidos (Pydantic/FastAPI) -> 422
#   - HTTPException           -> HTTPException levantada manualmente
#   - Exception               -> qualquer coisa não tratada -> 500 genérico
#
# Em dev (settings.app.expose_internal_errors == True) o 500 expõe a mensagem
# real; em prod, devolve texto genérico e o detalhe fica só no log.

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import get_logger, get_request_id

log = get_logger(__name__)


def _error_body(
    *,
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": get_request_id(),
        }
    }


def _response(status_code: int, body: dict[str, Any]) -> JSONResponse:
    # O header X-Request-ID é adicionado pelo RequestIDMiddleware em TODA
    # resposta (inclusive as de erro). Não duplicar aqui; o corpo já carrega
    # o request_id em error.request_id.
    return JSONResponse(status_code=status_code, content=body)


def register_error_handlers(app: FastAPI) -> None:
    """Registra todos os handlers no app. Chamado em create_app()."""

    @app.exception_handler(AppException)
    async def handle_app_exception(_request: Request, exc: AppException) -> JSONResponse:
        # 5xx é problema nosso: loga como erro. 4xx é esperado: loga como info.
        if exc.status_code >= 500:
            log.error("app_exception", error_code=exc.error_code, message=exc.message)
        else:
            log.info("app_exception", error_code=exc.error_code, message=exc.message)
        return _response(
            exc.status_code,
            _error_body(code=exc.error_code, message=exc.message, details=exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        log.info("request_validation_error", error_count=len(exc.errors()))
        return _response(
            422,
            _error_body(
                code="validation_error",
                message="Falha de validação na requisição.",
                # exc.errors() é serializável (list de dicts) e mostra qual campo falhou.
                details=exc.errors(),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _response(
            exc.status_code,
            _error_body(code="http_error", message=str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        # Loga o stack trace completo SEMPRE; expõe ao cliente só em dev.
        log.exception("unhandled_exception")
        message = str(exc) if settings.app.expose_internal_errors else "Erro interno do servidor."
        return _response(
            500,
            _error_body(code="internal_error", message=message),
        )
