# Utilitários de tempo.

# Convenção do projeto: TUDO em UTC no banco e na lógica. Conversão para o
# fuso do usuário/OLT é responsabilidade da borda (frontend / camada de
# apresentação), nunca do núcleo.

from __future__ import annotations

from datetime import UTC, datetime

from app.core.exceptions import ValidationError


def utcnow() -> datetime:
    """Agora, como datetime timezone-aware em UTC."""
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    """Garante que um datetime esteja em UTC e seja aware.
    - Naive: assume que já está em UTC e apenas anexa o tzinfo.
    - Aware: converte para UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_iso(dt: datetime) -> str:
    """Serializa para ISO-8601 em UTC. Ex.: '2026-06-03T12:00:00+00:00'."""
    return ensure_utc(dt).isoformat()


def parse_iso(value: str) -> datetime:
    """Lê uma string ISO-8601 e devolve datetime aware em UTC.
    Levanta ValidationError se o formato for inválido."""
    try:
        parsed = datetime.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            "Data/hora em formato inválido (esperado ISO-8601).",
            details={"value": str(value)},
        ) from exc
    return ensure_utc(parsed)
