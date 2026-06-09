# Testes de integração das rotas de OltModel.

from uuid import uuid4

from fastapi.testclient import TestClient


def _unique() -> str:
    return uuid4().hex[:8]


def _create_manufacturer(client: TestClient) -> str:
    """Helper: cria um fabricante com slug pytest- e devolve o UUID."""
    slug = f"pytest-{_unique()}"
    res = client.post(
        "/api/v1/manufacturers",
        json={"name": f"Test {slug}", "slug": slug},
    )
    assert res.status_code == 201, res.text
    return res.json()["manufacturer_id"]


def test_create_olt_model_with_existing_manufacturer(real_client: TestClient) -> None:
    mid = _create_manufacturer(real_client)
    model = f"pytest-{_unique()}"

    res = real_client.post(
        "/api/v1/olt-models",
        json={"manufacturer_id": mid, "model": model},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["manufacturer_id"] == mid
    assert body["model"] == model
    assert body["active"] is True


def test_create_olt_model_with_unknown_manufacturer_returns_404(
    real_client: TestClient,
) -> None:
    res = real_client.post(
        "/api/v1/olt-models",
        json={"manufacturer_id": str(uuid4()), "model": f"pytest-{_unique()}"},
    )
    assert res.status_code == 404
    body = res.json()
    assert body["error"]["code"] == "not_found"
    assert "manufacturer_id" in body["error"]["details"]


def test_create_olt_model_duplicate_returns_409(real_client: TestClient) -> None:
    mid = _create_manufacturer(real_client)
    model = f"pytest-{_unique()}"

    r1 = real_client.post(
        "/api/v1/olt-models",
        json={"manufacturer_id": mid, "model": model},
    )
    assert r1.status_code == 201

    r2 = real_client.post(
        "/api/v1/olt-models",
        json={"manufacturer_id": mid, "model": model},
    )
    assert r2.status_code == 409
    body = r2.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["details"]["model"] == model


def test_list_olt_models_filtered_by_manufacturer(real_client: TestClient) -> None:
    mid_a = _create_manufacturer(real_client)
    mid_b = _create_manufacturer(real_client)

    model_a = f"pytest-{_unique()}"
    model_b = f"pytest-{_unique()}"
    real_client.post(
        "/api/v1/olt-models",
        json={"manufacturer_id": mid_a, "model": model_a},
    )
    real_client.post(
        "/api/v1/olt-models",
        json={"manufacturer_id": mid_b, "model": model_b},
    )

    res = real_client.get(
        "/api/v1/olt-models",
        params={"manufacturer_id": mid_a, "page_size": 200},
    )
    assert res.status_code == 200
    models = {item["model"] for item in res.json()["items"]}
    assert model_a in models
    assert model_b not in models


def test_patch_olt_model_changes_model_name(real_client: TestClient) -> None:
    mid = _create_manufacturer(real_client)
    model_old = f"pytest-{_unique()}"
    create = real_client.post(
        "/api/v1/olt-models",
        json={"manufacturer_id": mid, "model": model_old},
    )
    olt_model_id = create.json()["olt_model_id"]

    model_new = f"pytest-{_unique()}"
    patch = real_client.patch(
        f"/api/v1/olt-models/{olt_model_id}",
        json={"model": model_new},
    )
    assert patch.status_code == 200
    assert patch.json()["model"] == model_new
