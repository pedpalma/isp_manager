# Ator: quem está executando uma ação no sistema.
#
# Placeholder propositalmente fino até o Marco de Auth. Hoje todo request
# carrega o `system_actor`. Mantemos `actor` como argumento explícito em
# TODOS os services para que, quando o JWT entrar:
#   - O `get_current_actor` em app/api/deps.py passa a extrair do token.
#   - Os services NÃO mudam de assinatura.
#
# É a forma mais barata de não pagar uma refatoração ampla depois.

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
    """Ator usado quando não há usuário autenticado (situação atual até
    o Marco de Auth). Também serve para ações automáticas internas, como
    tasks de coleta periódica que rodam sem usuário humano envolvido."""
    return Actor(actor_id=None, username="system", is_system=True)
