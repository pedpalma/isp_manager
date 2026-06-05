# Middleware de Request ID.

# Responsabilidade:
# - Ler o header X-Request-ID se vier de um proxy/nginx (preserva a correlação
#   ponta a ponta); senão, gerar um UUID4 novo.
# - Amarrar o request_id no contexto do structlog (toda linha de log do request
#   passa a incluí-lo automaticamente).
# - Devolver o request_id no header X-Request-ID da resposta.
# - Limpar o contexto ao fim, para não vazar para o próximo request no mesmo
#   worker do uvicorn.


from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.ids import is_valid_id, new_id_str
from app.core.logging import bind_request_id, clear_request_context

REQUEST_ID_HEADER = "x-request-id"
_MAX_INBOUND_LEN = 128  # limite defensivo para header vindo de fora


class RequestIDMiddleware:
    """Middleware ASGI puro (não BaseHTTPMiddleware) para preservar streaming e
    não interferir no corpo da resposta."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = self._resolve_request_id(scope)
        bind_request_id(request_id)

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.append((REQUEST_ID_HEADER.encode("latin-1"), request_id.encode("latin-1")))
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            # Sempre limpa, mesmo se a aplicação levantar exceção.
            clear_request_context()

    @staticmethod
    def _resolve_request_id(scope: Scope) -> str:
        for name, value in scope.get("headers", []):
            if name == REQUEST_ID_HEADER.encode("latin-1"):
                candidate = value.decode("latin-1").strip()
                # Aceita UUID válido vindo do proxy; senão ignora e gera o nosso.
                if candidate and len(candidate) <= _MAX_INBOUND_LEN and is_valid_id(candidate):
                    return candidate
                break
        return new_id_str()
