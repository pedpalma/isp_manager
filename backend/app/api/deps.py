# Dependências compartilhadas entre rotas (`Depends(...)` do FastAPI).
from __future__ import annotations

from app.core.actor import Actor, system_actor


def get_current_actor() -> Actor:
    """Devolve o ator atual da requisição. este helper vai:
    1) ler `Authorization: Bearer ...` da requisição,
    2) validar o JWT,
    3) construir um `Actor` real com `actor_id` e `username` do token.

    Os services não precisam saber de nada disso: continuam recebendo
    `actor: Actor` e a fonte de verdade da identidade vive AQUI.
    """
    return system_actor()
