"""Renderiza o dictConfig do uvicorn como JSON em stdout.

Usado pelo entrypoint do container da API. Fluxo:

python /app/scripts/render_uvicorn_log_config.py > /tmp/uvicorn_log.json
exec uvicorn app.main:app ... --log-config /tmp/uvicorn_log.json

O script falha rápido se as Settings não puderem ser carregadas (ex.: variável
obrigatória faltando no .env).
"""

from __future__ import annotations

import json
import sys

from app.core.logging import get_uvicorn_log_config


def main() -> int:
    json.dump(get_uvicorn_log_config(), sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
