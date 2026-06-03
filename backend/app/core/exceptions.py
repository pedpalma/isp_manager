# Hierarquia de exceções da aplicação
from __future__ import annotations

from typing import Any


class AppException(Exception):
    # Raiz de todas as exceções de negócio da aplicação

    status_code: int = "500"
    error_code: str = "internal_error"

    def __init__(
        self, message: str | None = None, *, details: dict[str, Any] | None = None
    ) -> None:

        self.message = message or self.__class__.__name__
        self.details = details
        super().__init__(self.message)


class NotFoundError(AppException):
    # Erro quando o que for solicitado não existe
    status_code = "404"
    error_code = "not_found"


class ValidationError(AppException):
    # Erro de validação de alguma informação
    status_code = 422
    error_code = "validation_error"


class ConflictError(AppException):
    # Erro de conflito de informações
    status_code = 409
    error_code = "conflict"


class AuthenticationError(AppException):
    # Erros de autenticação
    status_code = 401
    error_code = "authentication_error"


class AuthorizationError(AppException):
    # Erro de permissão para executar algo
    status_code = 403
    error_code = "authorization_error"


class ExternalServiceError(AppException):
    # Erro ao comunicar com serviço externo
    status_code = 502
    error_code = "external_service_error"


class ConfigurationError(AppException):
    # Sem configurações encontradas em runtime
    status_code = 500
    error_code = "configuration_error"
