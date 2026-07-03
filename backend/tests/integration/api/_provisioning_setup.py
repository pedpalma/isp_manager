# Helpers compartilhados para testes de integração do domínio provisioning.

# Oos recursos criados usam prefixo pytest- para que o cleanup do conftest
# remova sem tocar em dados semeados.

from __future__ import annotations

from typing import Any
from uuid import uuid4

from tests.integration.api._olt_mock import setup_inventory

API = "/api/v1"


def _unique(prefix: str) -> str:
    return f"pytest-{prefix}-{uuid4().hex[:8]}"


def make_raw_template(
    *,
    scope: str = "onu_provision",
    steps: list[dict[str, Any]] | None = None,
    rollback_map: dict[str, str] | None = None,
    params_schema: dict[str, Any] | None = None,
    version: str = "1",
) -> dict[str, Any]:
    """Gera um raw_template válido para reuso nos testes."""
    if steps is None:
        steps = [
            {
                "step_key": "authorize_onu",
                "phase": "execution",
                "command_key": "authorize_onu",
                "fail_policy": "abort",
            }
        ]
    if rollback_map is None:
        rollback_map = {"authorize_onu": "deauthorize_onu"}
    if params_schema is None:
        params_schema = {}

    return {
        "version": version,
        "scope": scope,
        "params_schema": params_schema,
        "steps": steps,
        "rollback_map": rollback_map,
    }


def setup_provisioning_catalog(real_client, headers: dict[str, str]) -> dict[str, Any]:
    """Cria manufacturer + olt_model isolados para testes de CATÁLOGO."""
    mfr_slug = _unique("mfr")
    r = real_client.post(
        f"{API}/manufacturers",
        headers=headers,
        json={"name": mfr_slug, "slug": mfr_slug, "active": True},
    )
    assert r.status_code == 201, r.text
    manufacturer_id = r.json()["manufacturer_id"]

    olt_model_name = _unique("oltm")
    r = real_client.post(
        f"{API}/olt-models",
        headers=headers,
        json={
            "manufacturer_id": manufacturer_id,
            "model": olt_model_name,
            "active": True,
        },
    )
    assert r.status_code == 201, r.text
    olt_model_id = r.json()["olt_model_id"]

    return {
        "manufacturer_id": manufacturer_id,
        "olt_model_id": olt_model_id,
    }


def setup_full_provisioning_chain(real_client, headers: dict[str, str]) -> dict[str, Any]:
    """Monta cadeia completa para testes de POST /provisioning-orders."""
    inv = setup_inventory(real_client, headers)

    # line_profile
    line_name = _unique("lp")
    r = real_client.post(
        f"{API}/line-profiles",
        headers=headers,
        json={
            "olt_id": str(inv["olt_id"]),
            "name": line_name,
            "download_kbps": 100000,
            "upload_kbps": 50000,
            "active": True,
        },
    )
    assert r.status_code == 201, r.text
    line_profile = r.json()

    # service_profile
    svc_name = _unique("sp")
    r = real_client.post(
        f"{API}/service-profiles",
        headers=headers,
        json={
            "olt_id": str(inv["olt_id"]),
            "name": svc_name,
            "active": True,
        },
    )
    assert r.status_code == 201, r.text
    service_profile = r.json()

    # vlan
    vlan_number = 100
    r = real_client.post(
        f"{API}/vlans",
        headers=headers,
        json={
            "olt_id": str(inv["olt_id"]),
            "name": _unique("vlan"),
            "vlan_number": vlan_number,
            "active": True,
        },
    )
    assert r.status_code == 201, r.text
    vlan = r.json()

    # provisioning_template (usa o manufacturer/olt_model DA OLT)
    template_name = _unique("tpl")
    raw_tpl = make_raw_template()
    r = real_client.post(
        f"{API}/provisioning-templates",
        headers=headers,
        json={
            "manufacturer_id": str(inv["manufacturer_id"]),
            "olt_model_id": str(inv["olt_model_id"]),
            "template_scope": "onu_provision",
            "name": template_name,
            "version": "1",
            "raw_template": raw_tpl,
            "active": True,
        },
    )
    assert r.status_code == 201, r.text
    template = r.json()

    for step in raw_tpl.get("steps", []):
        r = real_client.post(
            f"{API}/normalized-commands",
            headers=headers,
            json={
                "manufacturer_id": str(inv["manufacturer_id"]),
                "olt_model_id": str(inv["olt_model_id"]),
                "command_key": step["command_key"],
                "template_string": f"echo pytest-{step['command_key']}",
                "timeout_ms": 5000,
                "requires_privileged": False,
                "active": True,
            },
        )
        assert r.status_code == 201, r.text

    # comandos de rollback_map também precisam existir
    for rollback_cmd in raw_tpl.get("rollback_map", {}).values():
        r = real_client.post(
            f"{API}/normalized-commands",
            headers=headers,
            json={
                "manufacturer_id": str(inv["manufacturer_id"]),
                "olt_model_id": str(inv["olt_model_id"]),
                "command_key": rollback_cmd,
                "template_string": f"echo pytest-rollback-{rollback_cmd}",
                "timeout_ms": 5000,
                "requires_privileged": False,
                "active": True,
            },
        )
        # 409 aceitável se o mesmo command_key já foi cadastrado no loop acima
        assert r.status_code in (201, 409), r.text

    return {
        **inv,
        "line_profile_id": line_profile["line_profile_id"],
        "service_profile_id": service_profile["service_profile_id"],
        "vlan_id": vlan["vlan_id"],
        "vlan_number": vlan_number,
        "provisioning_template_id": template["provisioning_template_id"],
    }


def build_snapshot(chain: dict[str, Any], *, custom_id: str | None = None) -> dict[str, Any]:
    """Monta o dict que vai em body['snapshot'] do POST /provisioning-orders."""
    return {
        "line_profile_id": chain["line_profile_id"],
        "service_profile_id": chain["service_profile_id"],
        "vlan_id": chain["vlan_id"],
        "onu_index": 1,
        "custom_id": custom_id or _unique("cust")[:32],
    }


def seed_pending_onu(
    engine, chain: dict[str, Any], *, serial: str, state: str = "detected"
) -> None:
    """Insere um pending_onu direto via sync engine (helper para testes).

    Necessário porque a validação V6 (serial reconhecido) exige serial
    presente em onu OU em pending_onu ATIVO."""
    from sqlalchemy import text

    with engine.connect() as conn, conn.begin():
        conn.execute(
            text(
                """
                INSERT INTO pending_onu (
                    olt_id, pon_port_id, serial, state,
                    first_seen_at, last_seen_at, discovery_source
                ) VALUES (
                    :olt, :pon, :serial, :state,
                    NOW(), NOW(), 'pytest-seed'
                )
                """
            ),
            {
                "olt": str(chain["olt_id"]),
                "pon": str(chain["pon_port_id"]),
                "serial": serial,
                "state": state,
            },
        )
