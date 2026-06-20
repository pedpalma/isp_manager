# Testes de integração das rotas /app-users (somente admin).

from __future__ import annotations

from tests.integration.api.test_auth import (
    _PASSWORD,
    API,
    _bootstrap_admin,
    _create_group,
    _create_user,
    _login,
    _unique,
)


def test_create_and_get_user(real_client):
    admin_headers, _ = _bootstrap_admin(real_client)
    gid = _create_group(real_client, admin_headers)
    username = _unique("user")
    resp = real_client.post(
        f"{API}/app-users",
        headers=admin_headers,
        json={
            "user_group_id": gid,
            "username": username,
            "email": f"{username}@test.local",
            "password": _PASSWORD,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["username"] == username
    # campos sensíveis nunca aparecem
    assert "password_hash" not in body
    assert "reset_password_token" not in body

    uid = body["app_user_id"]
    got = real_client.get(f"{API}/app-users/{uid}", headers=admin_headers)
    assert got.status_code == 200
    assert got.json()["app_user_id"] == uid


def test_create_user_duplicate_username_conflicts(real_client):
    admin_headers, _ = _bootstrap_admin(real_client)
    gid = _create_group(real_client, admin_headers)
    username, _ = _create_user(real_client, admin_headers, gid)
    resp = real_client.post(
        f"{API}/app-users",
        headers=admin_headers,
        json={
            "user_group_id": gid,
            "username": username,
            "email": f"{_unique('e')}@test.local",
            "password": _PASSWORD,
        },
    )
    assert resp.status_code == 409


def test_create_user_duplicate_email_conflicts(real_client):
    admin_headers, _ = _bootstrap_admin(real_client)
    gid = _create_group(real_client, admin_headers)
    username = _unique("user")
    email = f"{username}@test.local"
    first = real_client.post(
        f"{API}/app-users",
        headers=admin_headers,
        json={"user_group_id": gid, "username": username, "email": email, "password": _PASSWORD},
    )
    assert first.status_code == 201, first.text
    second = real_client.post(
        f"{API}/app-users",
        headers=admin_headers,
        json={
            "user_group_id": gid,
            "username": _unique("user"),
            "email": email,
            "password": _PASSWORD,
        },
    )
    assert second.status_code == 409


def test_create_user_invalid_group_400(real_client):
    admin_headers, _ = _bootstrap_admin(real_client)
    username = _unique("user")
    resp = real_client.post(
        f"{API}/app-users",
        headers=admin_headers,
        json={
            "user_group_id": "00000000-0000-0000-0000-000000000000",
            "username": username,
            "email": f"{username}@test.local",
            "password": _PASSWORD,
        },
    )
    assert resp.status_code == 400


def test_create_user_in_inactive_group_400(real_client):
    admin_headers, _ = _bootstrap_admin(real_client)
    gid = _create_group(real_client, admin_headers, active=False)
    username = _unique("user")
    resp = real_client.post(
        f"{API}/app-users",
        headers=admin_headers,
        json={
            "user_group_id": gid,
            "username": username,
            "email": f"{username}@test.local",
            "password": _PASSWORD,
        },
    )
    assert resp.status_code == 400


def test_update_user_email_and_active(real_client):
    admin_headers, _ = _bootstrap_admin(real_client)
    gid = _create_group(real_client, admin_headers)
    username, _ = _create_user(real_client, admin_headers, gid)
    # localiza o id pelo list com busca
    listed = real_client.get(
        f"{API}/app-users", headers=admin_headers, params={"search": username}
    ).json()
    uid = listed["items"][0]["app_user_id"]

    new_email = f"{_unique('mail')}@test.local"
    resp = real_client.patch(
        f"{API}/app-users/{uid}",
        headers=admin_headers,
        json={"email": new_email, "active": False},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == new_email
    assert body["active"] is False


def test_non_admin_forbidden_on_users(real_client):
    admin_headers, _ = _bootstrap_admin(real_client)
    gid = _create_group(real_client, admin_headers, permissions={"view_olt": True})
    username, password = _create_user(real_client, admin_headers, gid)
    user_headers = _login(real_client, username, password)
    resp = real_client.get(f"{API}/app-users", headers=user_headers)
    assert resp.status_code == 403
