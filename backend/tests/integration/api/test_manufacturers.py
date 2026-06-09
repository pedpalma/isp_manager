# Testes de integração das rotas de Manufacturer.
#
# Tocam o banco via `real_client` (TestClient com lifespan, conecta no
# Postgres do compose). Cada teste cria recursos com prefixo `pytest-` +
# sufixo aleatório; o cleanup automático no fim da sessão (conftest)
# remove tudo. Os 4 fabricantes do seed (huawei, zte, fiberhome, nokia)
# nunca são tocados.

from uuid import UUID, uuid4

from fastapi.testclient import TestClient


def _unique() -> str:
    return uuid4().hex[:8]


# ----- Listagem -----

def test_list_returns_seed_manufacturers(real_client: TestClient) -> None:
    res = real_client.get("/api/v1/manufacturers")
    assert res.status_code == 200, res.text
    body = res.json()
    assert "items" in body and "total" in body and "page" in body
    # Seed insere 4 (huawei, zte, fiberhome, nokia). `>=` é resiliente a
    # outros fabricantes que possam existir.
    slugs = {item["slug"] for item in body["items"]}
    assert {"huawei", "zte", "fiberhome", "nokia"} <= slugs


def test_list_with_search_filters_by_name(real_client: TestClient) -> None:
    res = real_client.get("/api/v1/manufacturers", params={"search": "huawei"})
    assert res.status_code == 200
    body = res.json()
    # Pode haver matches além do seed (acentos, parciais), mas pelo menos
    # huawei tem que estar lá.
    names = {item["name"].lower() for item in body["items"]}
    assert any("huawei" in n for n in names)


def test_list_pagination_respects_page_size(real_client: TestClient) -> None:
    res = real_client.get("/api/v1/manufacturers", params={"page": 1, "page_size": 2})
    assert res.status_code == 200
    body = res.json()
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) <= 2


# ----- Detalhe -----

def test_get_unknown_id_returns_404(real_client: TestClient) -> None:
    res = real_client.get(f"/api/v1/manufacturers/{uuid4()}")
    assert res.status_code == 404
    body = res.json()
    assert body["error"]["code"] == "not_found"
    assert "manufacturer_id" in body["error"]["details"]


# ----- Criação -----

def test_create_then_get_roundtrip(real_client: TestClient) -> None:
    slug = f"pytest-{_unique()}"
    create = real_client.post(
        "/api/v1/manufacturers",
        json={"name": "Test Manufacturer", "slug": slug},
    )
    assert create.status_code == 201, create.text
    created = create.json()
    assert created["slug"] == slug
    assert created["active"] is True
    assert UUID(created["manufacturer_id"])  # parse-check do UUID
    assert created["created_at"] and created["updated_at"]

    fetched = real_client.get(f"/api/v1/manufacturers/{created['manufacturer_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["slug"] == slug


def test_create_duplicate_slug_returns_409(real_client: TestClient) -> None:
    slug = f"pytest-{_unique()}"
    r1 = real_client.post(
        "/api/v1/manufacturers",
        json={"name": "First", "slug": slug},
    )
    assert r1.status_code == 201

    r2 = real_client.post(
        "/api/v1/manufacturers",
        json={"name": "Second", "slug": slug},
    )
    assert r2.status_code == 409
    body = r2.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["details"]["slug"] == slug


def test_create_invalid_slug_returns_422(real_client: TestClient) -> None:
    # Slug com maiúscula viola o regex do Pydantic.
    res = real_client.post(
        "/api/v1/manufacturers",
        json={"name": "X", "slug": "PYTEST-INVALID"},
    )
    assert res.status_code == 422
    body = res.json()
    assert body["error"]["code"] == "validation_error"


# ----- PATCH -----

def test_patch_updates_name_only(real_client: TestClient) -> None:
    slug = f"pytest-{_unique()}"
    create = real_client.post(
        "/api/v1/manufacturers",
        json={"name": "Old Name", "slug": slug},
    )
    assert create.status_code == 201
    mid = create.json()["manufacturer_id"]

    patch = real_client.patch(
        f"/api/v1/manufacturers/{mid}",
        json={"name": "New Name"},
    )
    assert patch.status_code == 200, patch.text
    body = patch.json()
    assert body["name"] == "New Name"
    # Slug não muda porque não foi enviado no PATCH.
    assert body["slug"] == slug


def test_patch_to_deactivate_then_filter_only_active(real_client: TestClient) -> None:
    slug = f"pytest-{_unique()}"
    create = real_client.post(
        "/api/v1/manufacturers",
        json={"name": "Soon Inactive", "slug": slug},
    )
    mid = create.json()["manufacturer_id"]

    patch = real_client.patch(
        f"/api/v1/manufacturers/{mid}",
        json={"active": False},
    )
    assert patch.status_code == 200
    assert patch.json()["active"] is False

    # only_active=true não deve incluir o desativado.
    listing = real_client.get(
        "/api/v1/manufacturers",
        params={"only_active": "true", "search": slug},
    )
    assert listing.status_code == 200
    found_slugs = {item["slug"] for item in listing.json()["items"]}
    assert slug not in found_slugs


def test_patch_slug_conflict_returns_409(real_client: TestClient) -> None:
    slug_a = f"pytest-{_unique()}"
    slug_b = f"pytest-{_unique()}"
    real_client.post(
        "/api/v1/manufacturers",
        json={"name": "A", "slug": slug_a},
    )
    create_b = real_client.post(
        "/api/v1/manufacturers",
        json={"name": "B", "slug": slug_b},
    )
    mid_b = create_b.json()["manufacturer_id"]

    # Tentar trocar o slug de B para o de A já existente.
    patch = real_client.patch(
        f"/api/v1/manufacturers/{mid_b}",
        json={"slug": slug_a},
    )
    assert patch.status_code == 409
    assert patch.json()["error"]["code"] == "conflict"


def test_patch_unknown_id_returns_404(real_client: TestClient) -> None:
    res = real_client.patch(
        f"/api/v1/manufacturers/{uuid4()}",
        json={"name": "x"},
    )
    assert res.status_code == 404
