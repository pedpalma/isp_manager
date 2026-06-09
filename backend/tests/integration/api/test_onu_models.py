# Testes de integração das rotas de OnuModel.

from uuid import uuid4

from fastapi.testclient import TestClient


def _unique() -> str:
    return uuid4().hex[:8]


def _create_manufacturer(client: TestClient) -> str:
    slug = f"pytest-{_unique()}"
    res = client.post(
        "/api/v1/manufacturers",
        json={"name": f"Test {slug}", "slug": slug},
    )
    assert res.status_code == 201, res.text
    return res.json()["manufacturer_id"]


def test_create_onu_model_with_vendor_id_and_capabilities(
    real_client: TestClient,
) -> None:
    mid = _create_manufacturer(real_client)
    model = f"pytest-{_unique()}"
    vendor_id = f"pyt{_unique()[:4]}"

    res = real_client.post(
        "/api/v1/onu-models",
        json={
            "manufacturer_id": mid,
            "model": model,
            "vendor_id": vendor_id,
            "category": "residencial",
            "capabilities_json": {"wifi": True, "fxs": 2, "catv": False},
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["vendor_id"] == vendor_id
    assert body["category"] == "residencial"
    assert body["capabilities_json"] == {"wifi": True, "fxs": 2, "catv": False}


def test_create_onu_model_without_vendor_id(real_client: TestClient) -> None:
    # vendor_id é opcional. A unicidade parcial no banco só vale quando
    # estiver preenchido.
    mid = _create_manufacturer(real_client)
    model = f"pytest-{_unique()}"

    res = real_client.post(
        "/api/v1/onu-models",
        json={"manufacturer_id": mid, "model": model},
    )
    assert res.status_code == 201
    assert res.json()["vendor_id"] is None


def test_create_two_onu_models_without_vendor_id_is_allowed(
    real_client: TestClient,
) -> None:
    # A unicidade parcial (WHERE vendor_id IS NOT NULL) NÃO impede dois
    # registros com vendor_id NULL. Tem que funcionar.
    mid = _create_manufacturer(real_client)

    r1 = real_client.post(
        "/api/v1/onu-models",
        json={"manufacturer_id": mid, "model": f"pytest-{_unique()}"},
    )
    r2 = real_client.post(
        "/api/v1/onu-models",
        json={"manufacturer_id": mid, "model": f"pytest-{_unique()}"},
    )
    assert r1.status_code == 201
    assert r2.status_code == 201


def test_create_onu_model_duplicate_vendor_id_returns_409(
    real_client: TestClient,
) -> None:
    mid = _create_manufacturer(real_client)
    vendor_id = f"pyt{_unique()[:4]}"

    r1 = real_client.post(
        "/api/v1/onu-models",
        json={
            "manufacturer_id": mid,
            "model": f"pytest-{_unique()}",
            "vendor_id": vendor_id,
        },
    )
    assert r1.status_code == 201

    r2 = real_client.post(
        "/api/v1/onu-models",
        json={
            "manufacturer_id": mid,
            "model": f"pytest-{_unique()}",
            "vendor_id": vendor_id,
        },
    )
    assert r2.status_code == 409
    body = r2.json()
    assert body["error"]["code"] == "conflict"
    # No caso de vendor_id duplicado, o erro de domínio específico é
    # OnuModelVendorIdConflict; o detail tem `vendor_id`.
    assert body["error"]["details"]["vendor_id"] == vendor_id


def test_create_onu_model_duplicate_model_returns_409(real_client: TestClient) -> None:
    mid = _create_manufacturer(real_client)
    model = f"pytest-{_unique()}"

    r1 = real_client.post(
        "/api/v1/onu-models",
        json={"manufacturer_id": mid, "model": model},
    )
    assert r1.status_code == 201

    r2 = real_client.post(
        "/api/v1/onu-models",
        json={"manufacturer_id": mid, "model": model},
    )
    assert r2.status_code == 409
    assert r2.json()["error"]["details"]["model"] == model


def test_create_onu_model_with_unknown_manufacturer_returns_404(
    real_client: TestClient,
) -> None:
    res = real_client.post(
        "/api/v1/onu-models",
        json={
            "manufacturer_id": str(uuid4()),
            "model": f"pytest-{_unique()}",
        },
    )
    assert res.status_code == 404


def test_list_onu_models_filtered_by_category(real_client: TestClient) -> None:
    mid = _create_manufacturer(real_client)
    cat = f"pytest-{_unique()}"  # categoria única para este teste

    real_client.post(
        "/api/v1/onu-models",
        json={
            "manufacturer_id": mid,
            "model": f"pytest-{_unique()}",
            "category": cat,
        },
    )
    real_client.post(
        "/api/v1/onu-models",
        json={
            "manufacturer_id": mid,
            "model": f"pytest-{_unique()}",
            "category": "outra-categoria",
        },
    )

    res = real_client.get(
        "/api/v1/onu-models",
        params={"category": cat, "page_size": 200},
    )
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["category"] == cat
