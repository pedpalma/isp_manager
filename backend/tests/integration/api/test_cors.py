"""Testes de CORS (Marco 7).

Constroem a aplicação real via create_app() para validar a fiação efetiva do
CORSMiddleware (origens, credenciais, métodos, e exposição do X-Request-ID),
em vez de uma app sintética. A origem permitida é lida do settings, então o
teste continua válido para qualquer CORS_ORIGINS configurado.

Não usamos o context manager do TestClient de propósito: assim o lifespan
(init_engine/dispose_engine) não roda e os testes não dependem de banco. As
rotas exercitadas aqui (/health liveness e o preflight OPTIONS) não tocam no DB.
"""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def _allowed_origin() -> str:
    origins = settings.app.cors_origins_list
    assert origins, "CORS_ORIGINS deveria ter ao menos uma origem em ambiente de teste"
    return origins[0]


def test_preflight_allowed_origin_is_accepted() -> None:
    origin = _allowed_origin()
    res = _client().options(
        "/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == origin
    assert res.headers.get("access-control-allow-credentials") == "true"
    # Métodos liberados aparecem na resposta do preflight.
    assert "GET" in res.headers.get("access-control-allow-methods", "")


def test_preflight_disallowed_origin_gets_no_allow_origin() -> None:
    res = _client().options(
        "/health",
        headers={
            "Origin": "http://attacker.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    # Starlette responde 400 a um preflight de origem não permitida...
    assert res.status_code == 400
    # ...e, o que mais importa, NÃO devolve o cabeçalho que autorizaria a leitura.
    assert "access-control-allow-origin" not in res.headers


def test_simple_request_sets_allow_origin_and_exposes_request_id() -> None:
    origin = _allowed_origin()
    res = _client().get("/health", headers={"Origin": origin})

    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    assert res.headers.get("access-control-allow-origin") == origin
    # O id de correlação está presente e é LEGÍVEL pelo navegador (expose-headers).
    assert res.headers.get("x-request-id")
    assert "x-request-id" in res.headers.get("access-control-expose-headers", "").lower()


def test_request_without_origin_has_no_cors_headers_but_keeps_request_id() -> None:
    # Sem cabeçalho Origin não há contexto CORS: nenhum Access-Control-Allow-Origin.
    res = _client().get("/health")

    assert res.status_code == 200
    assert "access-control-allow-origin" not in res.headers
    # O RequestIDMiddleware continua agindo independentemente do CORS.
    assert res.headers.get("x-request-id")
