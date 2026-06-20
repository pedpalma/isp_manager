# Testes de integração das rotas /user-groups (somente admin).

from __future__ import annotations

from tests.integration.api.test_auth import (
    API,
    _bootstrap_admin,
    _create_group,
    _create_user,
    _login,
    _unique,
)


def test_create_and_get_group(real_client):
    admin_headers, _ = _bootstrap_admin(real_client)
    gid = _create_group(real_client, admin_headers, permissions={"view_olt": True})
    resp = real_client.get(f"{API}/user-groups/{gid}", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["permissions_json"] == {"view_olt": True}
    assert body["active"] is True


def test_list_groups_contains_created(real_client):
    admin_headers, _ = _bootstrap_admin(real_client)
    gid = _create_group(real_client, admin_headers)
    resp = real_client.get(f"{API}/user-groups", headers=admin_headers, params={"page_size": 100})
    assert resp.status_code == 200, resp.text
    ids = [g["user_group_id"] for g in resp.json()["items"]]
    assert gid in ids


def test_create_group_duplicate_name_conflicts(real_client):
    admin_headers, _ = _bootstrap_admin(real_client)
    name = _unique("grp")
    first = real_client.post(
        f"{API}/user-groups",
        headers=admin_headers,
        json={"name": name, "permissions_json": {}, "active": True},
    )
    assert first.status_code == 201, first.text
    second = real_client.post(
        f"{API}/user-groups",
        headers=admin_headers,
        json={"name": name, "permissions_json": {}, "active": True},
    )
    assert second.status_code == 409


def test_update_group_permissions_and_active(real_client):
    admin_headers, _ = _bootstrap_admin(real_client)
    gid = _create_group(real_client, admin_headers)
    resp = real_client.patch(
        f"{API}/user-groups/{gid}",
        headers=admin_headers,
        json={"permissions_json": {"all": True}, "active": False},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["permissions_json"] == {"all": True}
    assert body["active"] is False


def test_get_missing_group_404(real_client):
    admin_headers, _ = _bootstrap_admin(real_client)
    resp = real_client.get(
        f"{API}/user-groups/00000000-0000-0000-0000-000000000000",
        headers=admin_headers,
    )
    assert resp.status_code == 404


def test_non_admin_forbidden_on_groups(real_client):
    admin_headers, _ = _bootstrap_admin(real_client)
    # grupo sem permissão "all" -> usuário nao-admin
    gid = _create_group(real_client, admin_headers, permissions={"view_olt": True})
    username, password = _create_user(real_client, admin_headers, gid)
    user_headers = _login(real_client, username, password)
    resp = real_client.get(f"{API}/user-groups", headers=user_headers)
    assert resp.status_code == 403
