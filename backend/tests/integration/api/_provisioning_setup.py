# Helpers de teste do domínio provisioning (M18a).

from __future__ import annotations

from uuid import UUID, uuid4

API = "/api/v1"


def _unique(prefix: str) -> str:
    return f"pytest-{prefix}-{uuid4().hex[:8]}"


def setup_provisioning_catalog(real_client, headers: dict[str, str]) -> dict[str, UUID]:
    """Cria manufacturer + olt_model via API e devolve {manufacturer_id, olt_model_id}."""
    mfr_slug = _unique("mfr")
    r = real_client.post(
        f"{API}/manufacturers",
        headers=headers,
        json={"name": mfr_slug, "slug": mfr_slug, "active": True},
    )
    assert r.status_code == 201, r.text
    manufacturer_id = UUID(r.json()["manufacturer_id"])

    olt_model_name = _unique("oltm")
    r = real_client.post(
        f"{API}/olt-models",
        headers=headers,
        json={
            "manufacturer_id": str(manufacturer_id),
            "model": olt_model_name,
            "active": True,
        },
    )
    assert r.status_code == 201, r.text
    olt_model_id = UUID(r.json()["olt_model_id"])

    return {"manufacturer_id": manufacturer_id, "olt_model_id": olt_model_id}


def make_raw_template(
    *,
    scope: str = "onu_provision",
    steps: list[dict] | None = None,
    rollback_map: dict[str, str] | None = None,
) -> dict:
    """Gera um raw_template válido para uso nos testes."""
    return {
        "version": "1",
        "scope": scope,
        "params_schema": {
            "serial": {"type": "string", "required": True},
            "onu_index": {"type": "integer", "required": True},
        },
        "steps": steps
        or [
            {
                "step_key": "authorize_onu",
                "phase": "execute",
                "command_key": "authorize_onu",
                "fail_policy": "abort",
            }
        ],
        "rollback_map": rollback_map
        if rollback_map is not None
        else {"authorize_onu": "deauthorize_onu"},
    }
