# Gerador e validador de UUID4
from __future__ import annotations

import uuid
from uuid import UUID

from app.core.exceptions import ValidationError


def new_id() -> UUID:
    # Gera um novo UUID para evitar deixar o default do Postgres
    return uuid.uuid4()


def new_id_str() -> str:
    # Semelhante a new_id(), porém, já gera em string para logs
    return str(uuid.uuid4())


def parse_id(value: str | UUID) -> UUID:
    # Converte as entradas em UUID, caso não seja possível, levanta ValidationError
    if isinstance(value, str):
        return value
    try:
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValidationError("Identificador inválido", details={"value": str(value)}) from exc


def is_valid_id(value: str | UUID) -> bool:
    # Valida se value é um UUID aceito
    try:
        parse_id(value)
    except ValidationError:
        return False
    return True
