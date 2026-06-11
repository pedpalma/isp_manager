# Hierarquia de exceções da aplicação.

# As rotas NUNCA montam JSONResponse de erro na mão: elas levantam essas
# exceções e o handler global padroniza a resposta.

from __future__ import annotations

from typing import Any


class AppException(Exception):
    """Raiz de todas as exceções de negócio da aplicação."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.__class__.__name__
        self.details = details
        super().__init__(self.message)


class NotFoundError(AppException):
    """Recurso solicitado não existe. Ex.: ONU com serial X não encontrada."""

    status_code = 404
    error_code = "not_found"


class ValidationError(AppException):
    """Entrada inválida segundo regra de negócio (além da validação do Pydantic).
    Ex.: PON informada não pertence ao slot informado."""

    status_code = 422
    error_code = "validation_error"


class ConflictError(AppException):
    """Conflito de estado. Ex.: serial já provisionado, chave de idempotência
    já usada, violação de unicidade esperada."""

    status_code = 409
    error_code = "conflict"


class AuthenticationError(AppException):
    """Credenciais ausentes ou inválidas (quem é você?)."""

    status_code = 401
    error_code = "authentication_error"


class AuthorizationError(AppException):
    """Autenticado, mas sem permissão para a ação (você não pode isso)."""

    status_code = 403
    error_code = "authorization_error"


class ExternalServiceError(AppException):
    """Falha ao falar com sistema externo (OLT, IXC, Vault). Útil para separar
    'erro nosso' de 'erro de dependência' na auditoria."""

    status_code = 502
    error_code = "external_service_error"


class ConfigurationError(AppException):
    """Configuração ausente ou inconsistente detectada em runtime."""

    status_code = 500
    error_code = "configuration_error"


class BadRequestError(AppException):
    """Requisição malformada em nível de negócio: referencia um recurso
    que não existe ou que está em estado inutilizável para a operação.
    Distingue-se do 422 do Pydantic (formato do payload) e do 409 de
    conflito (colisão com estado existente). Ex.: olt_model_id ou
    credential_id inexistente; credencial referenciada está inativa.
    """

    status_code = 400
    error_code = "bad_request"
