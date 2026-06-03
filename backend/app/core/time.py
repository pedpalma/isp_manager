# Utilitários de tempo

from __future__ import annotations

from datetime import UTC, datetime

from app.core.exceptions import ValidationError


def utcnow() -> datetime:
    # Aplica datetime com timezone aware no UTC
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    # Garante que o datetime esteja em UTC e seja aware
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_iso(dt: datetime) -> str:
    # Serializa para ISO-8601 em UTC
    return ensure_utc(dt).isoformat()


def parse_iso(value: str) -> datetime:
    # Lê uma string ISO-8601 e devolver aware em UTC
    try:
        parsed = datetime.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            "Data/hora em formato inválido (esperando ISO-8601).",
            details={"value": str(value)},
        ) from exc
    return ensure_utc(parsed)
