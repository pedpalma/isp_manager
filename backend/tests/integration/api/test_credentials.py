# Testes de integração das rotas de Credential.

# Tocam o banco via `real_client` (TestClient com lifespan, conecta no
# Postgres do compose). Cada teste cria recursos com prefixo `pytest-` +
# sufixo aleatório; o cleanup automático no fim da sessão (conftest)
# remove tudo.

from uuid import UUID, uuid4

from fastapi.testclient import TestClient


def _unique() -> str:
    return uuid4().hex[:8]


def _password_payload(label_suffix: str | None = None) -> dict:
    """Payload válido mínimo para auth_type=password."""
    suffix = label_suffix or _unique()
    return {
        "label": f"pytest-{suffix}",
        "username": "admin",
        "secret_ref": "OLT_LAB_PASSWORD",
        "auth_type": "password",
    }


def _ssh_key_payload(label_suffix: str | None = None) -> dict:
    """Payload válido mínimo para auth_type=ssh_key."""
    suffix = label_suffix or _unique()
    return {
        "label": f"pytest-{suffix}",
        "username": "admin",
        "secret_ref": "OLT_LAB_PASSPHRASE",
        "auth_type": "ssh_key",
        "private_key_ref": "OLT_LAB_PRIVATE_KEY",
    }


# Listagem
def test_list_returns_paginated_envelope(real_client: TestClient) -> None:
    res = real_client.get("/api/v1/credentials")
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
    assert "has_next" in body
    assert "has_prev" in body


def test_list_with_search_filters_by_label(real_client: TestClient) -> None:
    payload = _password_payload()
    created = real_client.post("/api/v1/credentials", json=payload)
    assert created.status_code == 201, created.text

    res = real_client.get("/api/v1/credentials", params={"search": payload["label"]})
    assert res.status_code == 200
    body = res.json()
    labels = {item["label"] for item in body["items"]}
    assert payload["label"] in labels


def test_list_with_only_active_filter(real_client: TestClient) -> None:
    payload = _password_payload()
    create = real_client.post("/api/v1/credentials", json=payload)
    cid = create.json()["credential_id"]

    # Desativa.
    patch = real_client.patch(f"/api/v1/credentials/{cid}", json={"active": False})
    assert patch.status_code == 200
    assert patch.json()["active"] is False

    # only_active=true não deve incluir o desativado.
    listing = real_client.get(
        "/api/v1/credentials",
        params={"only_active": "true", "search": payload["label"]},
    )
    assert listing.status_code == 200
    found = {item["label"] for item in listing.json()["items"]}
    assert payload["label"] not in found


# Detalhe
def test_get_unknown_id_returns_404(real_client: TestClient) -> None:
    res = real_client.get(f"/api/v1/credentials/{uuid4()}")
    assert res.status_code == 404
    body = res.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["details"]["credential_id"]


# Criação
def test_create_password_does_not_expose_pointers(real_client: TestClient) -> None:
    payload = _password_payload()
    res = real_client.post("/api/v1/credentials", json=payload)
    assert res.status_code == 201, res.text
    body = res.json()

    # Campos esperados no Read.
    assert UUID(body["credential_id"])
    assert body["label"] == payload["label"]
    assert body["username"] == payload["username"]
    assert body["auth_type"] == "password"
    assert body["active"] is True
    assert body["last_validated_at"] is None
    assert body["created_at"] and body["updated_at"]

    # Os ponteiros NÃO podem aparecer no Read (D3).
    forbidden = {"secret_ref", "enable_secret_ref", "private_key_ref"}
    leaked = forbidden.intersection(body.keys())
    assert not leaked, f"Ponteiros vazaram no Read: {leaked}"


def test_create_default_auth_type_is_password(real_client: TestClient) -> None:
    payload = _password_payload()
    del payload["auth_type"]  # omite -> default do schema
    res = real_client.post("/api/v1/credentials", json=payload)
    assert res.status_code == 201
    assert res.json()["auth_type"] == "password"


def test_create_ssh_key_with_private_key_succeeds(real_client: TestClient) -> None:
    payload = _ssh_key_payload()
    res = real_client.post("/api/v1/credentials", json=payload)
    assert res.status_code == 201, res.text
    assert res.json()["auth_type"] == "ssh_key"


def test_get_after_create_does_not_expose_pointers(real_client: TestClient) -> None:
    payload = _ssh_key_payload()
    created = real_client.post("/api/v1/credentials", json=payload)
    cid = created.json()["credential_id"]

    res = real_client.get(f"/api/v1/credentials/{cid}")
    assert res.status_code == 200
    body = res.json()
    for forbidden_field in ("secret_ref", "enable_secret_ref", "private_key_ref"):
        assert forbidden_field not in body, f"GET /credentials/{{id}} expôs '{forbidden_field}'"


# Criação: validações negativas
def test_create_ssh_key_without_private_key_returns_422(real_client: TestClient) -> None:
    # Schema (model_validator) rejeita ANTES de tocar o banco.
    payload = _ssh_key_payload()
    del payload["private_key_ref"]
    res = real_client.post("/api/v1/credentials", json=payload)
    assert res.status_code == 422
    body = res.json()
    assert body["error"]["code"] == "validation_error"


def test_create_missing_required_field_returns_422(real_client: TestClient) -> None:
    payload = _password_payload()
    del payload["secret_ref"]
    res = real_client.post("/api/v1/credentials", json=payload)
    assert res.status_code == 422


def test_create_invalid_auth_type_returns_422(real_client: TestClient) -> None:
    payload = _password_payload()
    payload["auth_type"] = "INVALID_VALUE"
    res = real_client.post("/api/v1/credentials", json=payload)
    assert res.status_code == 422


# PATCH
def test_patch_updates_label_only(real_client: TestClient) -> None:
    payload = _password_payload()
    create = real_client.post("/api/v1/credentials", json=payload)
    cid = create.json()["credential_id"]

    new_label = f"pytest-{_unique()}-renamed"
    patch = real_client.patch(f"/api/v1/credentials/{cid}", json={"label": new_label})
    assert patch.status_code == 200, patch.text
    body = patch.json()
    assert body["label"] == new_label
    # username não foi tocado.
    assert body["username"] == payload["username"]


def test_patch_rotates_secret_ref(real_client: TestClient) -> None:
    # PATCH aceita atualizar secret_ref (rotação de senha).
    # O Read NÃO devolve o secret_ref, então só conseguimos validar que
    # a chamada foi 200 e que outros campos seguem corretos. O fato de
    # o secret_ref não retornar é o próprio teste de segurança.
    payload = _password_payload()
    create = real_client.post("/api/v1/credentials", json=payload)
    cid = create.json()["credential_id"]

    patch = real_client.patch(
        f"/api/v1/credentials/{cid}",
        json={"secret_ref": "OLT_LAB_PASSWORD_ROTATED"},
    )
    assert patch.status_code == 200
    body = patch.json()
    assert "secret_ref" not in body


def test_patch_switch_to_ssh_key_without_private_key_returns_409(
    real_client: TestClient,
) -> None:
    # Estado atual: password, sem private_key_ref.
    # PATCH: muda só auth_type para ssh_key. Estado MESCLADO inválido.
    # Service detecta e lança CredentialAuthMismatch -> 409.
    payload = _password_payload()
    create = real_client.post("/api/v1/credentials", json=payload)
    cid = create.json()["credential_id"]

    patch = real_client.patch(
        f"/api/v1/credentials/{cid}",
        json={"auth_type": "ssh_key"},
    )
    assert patch.status_code == 409, patch.text
    body = patch.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["details"]["auth_type"] == "ssh_key"


def test_patch_switch_to_ssh_key_with_private_key_succeeds(
    real_client: TestClient,
) -> None:
    # Mesmo cenário, mas o cliente envia auth_type E private_key_ref juntos no PATCH.
    # Estado mesclado válido.
    payload = _password_payload()
    create = real_client.post("/api/v1/credentials", json=payload)
    cid = create.json()["credential_id"]

    patch = real_client.patch(
        f"/api/v1/credentials/{cid}",
        json={
            "auth_type": "ssh_key",
            "private_key_ref": "OLT_LAB_PRIVATE_KEY",
        },
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["auth_type"] == "ssh_key"


def test_patch_clearing_private_key_on_ssh_key_returns_409(
    real_client: TestClient,
) -> None:
    # Estado atual: ssh_key com private_key_ref.
    # PATCH: tenta limpar private_key_ref (mandando null). Inválido.
    payload = _ssh_key_payload()
    create = real_client.post("/api/v1/credentials", json=payload)
    cid = create.json()["credential_id"]

    patch = real_client.patch(
        f"/api/v1/credentials/{cid}",
        json={"private_key_ref": None},
    )
    assert patch.status_code == 409
    body = patch.json()
    assert body["error"]["code"] == "conflict"


def test_patch_unknown_id_returns_404(real_client: TestClient) -> None:
    res = real_client.patch(
        f"/api/v1/credentials/{uuid4()}",
        json={"label": "pytest-nope"},
    )
    assert res.status_code == 404
    body = res.json()
    assert body["error"]["code"] == "not_found"


def test_patch_deactivate_then_reactivate(real_client: TestClient) -> None:
    payload = _password_payload()
    create = real_client.post("/api/v1/credentials", json=payload)
    cid = create.json()["credential_id"]

    off = real_client.patch(f"/api/v1/credentials/{cid}", json={"active": False})
    assert off.status_code == 200
    assert off.json()["active"] is False

    on = real_client.patch(f"/api/v1/credentials/{cid}", json={"active": True})
    assert on.status_code == 200
    assert on.json()["active"] is True
