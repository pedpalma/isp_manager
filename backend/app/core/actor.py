# Actor = quem está executando uma ação no sistema
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Actor:
    """Quem está agindo. `frozen=True` impede mutação acidental dentro de
    serviços (o ator é dado da requisição, não estado mutável)."""

    actor_id: UUID | None
    username: str
    is_system: bool


def system_actor() -> Actor:
    """Ator usado quando não há usuário autenticado.
    Também serve para ações automáticas internas,
    como tasks de coleta periódica que rodam sem usuário humano envolvido."""
    return Actor(actor_id=None, username="system", is_system=True)
