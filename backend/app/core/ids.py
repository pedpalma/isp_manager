# Geração e validação de identificadores (UUID v4).

from __future__ import annotations

import uuid
from uuid import UUID

from app.core.exceptions import ValidationError


def new_id() -> UUID:
    """Gera um novo UUID v4. Use quando a aplicação precisa criar o id (em vez
    de deixar o DEFAULT gen_random_uuid() do Postgres fazer)."""
    return uuid.uuid4()


def new_id_str() -> str:
    """Igual a new_id(), mas já em string. Conveniência para logs/headers."""
    return str(uuid.uuid4())


def parse_id(value: str | UUID) -> UUID:
    """Converte uma entrada em UUID, levantando ValidationError se inválida.
    Aceita UUID já pronto (passa direto) ou string."""
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValidationError(
            "Identificador inválido.",
            details={"value": str(value)},
        ) from exc


def is_valid_id(value: str | UUID) -> bool:
    """True se `value` é um UUID válido. Não levanta exceção."""
    try:
        parse_id(value)
    except ValidationError:
        return False
    return True
