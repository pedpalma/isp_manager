# Testes de integração via TestClient: exercitam middleware + handlers reais.

from uuid import UUID


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except (ValueError, TypeError):
        return False


def test_response_has_request_id_header(client):
    r = client.get("/ok")
    assert r.status_code == 200
    rid = r.headers.get("x-request-id")
    assert rid and _is_uuid(rid)


def test_inbound_valid_request_id_is_preserved(client):
    incoming = "11111111-1111-4111-8111-111111111111"
    r = client.get("/ok", headers={"X-Request-ID": incoming})
    assert r.headers.get("x-request-id") == incoming


def test_inbound_garbage_request_id_is_replaced(client):
    r = client.get("/ok", headers={"X-Request-ID": "not-a-uuid"})
    rid = r.headers.get("x-request-id")
    assert rid != "not-a-uuid"
    assert _is_uuid(rid)


def test_request_id_available_to_handler(client):
    # O id visto pelo handler deve ser o mesmo devolvido no header.
    r = client.get("/whoami")
    assert r.json()["request_id"] == r.headers.get("x-request-id")


def test_app_exception_becomes_structured_json(client):
    r = client.get("/notfound")
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "ONU não encontrada."
    assert body["error"]["details"] == {"serial": "ABC123"}
    assert body["error"]["request_id"] == r.headers.get("x-request-id")


def test_conflict_status_code(client):
    r = client.get("/conflict")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"


def test_validation_error_is_422(client):
    r = client.get("/needint", params={"n": "abc"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["details"], list)


def test_unhandled_exception_is_500_json(client):
    r = client.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["request_id"] == r.headers.get("x-request-id")
