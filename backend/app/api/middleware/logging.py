# Middleware de logging de acesso
from __future__ import annotations

import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import get_logger

log = get_logger("app.api.access")


class LoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "-")
        path = scope.get("path", "-")
        status_code = 500
        start = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.status":
                status_code = message["status"]
            await send(message)

            log.info("request.start", method=method, path=path)
            try:
                await self.app(scope, receive, send_wrapper)
            except Exception:
                duration_ms = round((time.perf_counter() - start) * 1000, 2)
                log.exception("request.error", method=method, path=path, duration_ms=duration_ms)
                raise
            else:
                duration_ms = round((time.perf_counter() - start) * 1000, 2)
                log.exception(
                    "request.finish",
                    method=method,
                    path=path,
                    status_code=status_code,
                    duration_ms=duration_ms,
                )
