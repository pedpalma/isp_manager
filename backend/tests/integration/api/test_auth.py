# Testes de integracao dos fluxos de autenticacao.
#
# Helpers exportados (_bootstrap_admin, _login, _unique, _create_user) sao
# reutilizados por test_user_groups.py e test_app_users.py.
#
# Bootstrap: como nao existe admin antes do primeiro login, o helper insere
# um admin direto no banco (mesmo hash argon2 do app), dentro do grupo
# semeado 'Administrador' ({"all": true}), e entao faz login pela API. Todo
# o resto (criar grupos/usuarios) passa pela API ja autenticada.
#
# A conexao sync usa `settings.database.build_app_sync_url()` para falar
# com o MESMO banco que o real_client usa (o conftest fixa POSTGRES_HOST
# para localhost por padrao). Evita criar uma "segunda URL" descolada.

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.domains.auth.security import hash_password

API = "/api/v1"
_PASSWORD = "pytest-Secret123"


def _sync_engine():
    return create_engine(settings.database.build_app_sync_url())


def _unique(prefix: str) -> str:
    return f"pytest-{prefix}-{uuid4().hex[:8]}"


def _bootstrap_admin(real_client) -> tuple[dict[str, str], str]:
    """Cria um admin (pytest-admin-*) no grupo semeado 'Administrador' e
    devolve (headers Bearer, username)."""
    username = _unique("admin")
    engine = _sync_engine()
    try:
        with engine.connect() as conn, conn.begin():
            row = conn.execute(
                text("SELECT user_group_id FROM user_group WHERE name = 'Administrador'")
            ).first()
            assert row is not None, "grupo 'Administrador' do seed 0001 ausente"
            group_id = row[0]
            conn.execute(
                text(
                    """
                    INSERT INTO app_user
                        (user_group_id, username, email, password_hash)
                    VALUES (:g, :u, :e, :h)
                    """
                ),
                {
                    "g": group_id,
                    "u": username,
                    "e": f"{username}@test.local",
                    "h": hash_password(_PASSWORD),
                },
            )
    finally:
        engine.dispose()

    headers = _login(real_client, username, _PASSWORD)
    return headers, username


def _login(real_client, username: str, password: str) -> dict[str, str]:
    resp = real_client.post(f"{API}/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_group(real_client, admin_headers, *, permissions=None, active=True) -> str:
    name = _unique("grp")
    resp = real_client.post(
        f"{API}/user-groups",
        headers=admin_headers,
        json={"name": name, "permissions_json": permissions or {}, "active": active},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["user_group_id"]


def _create_user(
    real_client,
    admin_headers,
    group_id,
    *,
    active=True,
    must_change=False,
    password=_PASSWORD,
) -> tuple[str, str]:
    username = _unique("user")
    resp = real_client.post(
        f"{API}/app-users",
        headers=admin_headers,
        json={
            "user_group_id": group_id,
            "username": username,
            "email": f"{username}@test.local",
            "password": password,
            "active": active,
            "must_change_password": must_change,
        },
    )
    assert resp.status_code == 201, resp.text
    return username, password


# Login
def test_login_success(real_client):
    headers, _ = _bootstrap_admin(real_client)
    assert headers["Authorization"].startswith("Bearer ")


def test_login_returns_tokens_and_flags(real_client):
    username = _unique("admin")
    engine = _sync_engine()
    try:
        with engine.connect() as conn, conn.begin():
            row = conn.execute(
                text("SELECT user_group_id FROM user_group WHERE name = 'Administrador'")
            ).first()
            assert row is not None, "grupo 'Administrador' do seed 0001 ausente"
            gid = row[0]
            conn.execute(
                text(
                    "INSERT INTO app_user (user_group_id, username, email, password_hash) "
                    "VALUES (:g, :u, :e, :h)"
                ),
                {
                    "g": gid,
                    "u": username,
                    "e": f"{username}@test.local",
                    "h": hash_password(_PASSWORD),
                },
            )
    finally:
        engine.dispose()

    resp = real_client.post(f"{API}/auth/login", json={"username": username, "password": _PASSWORD})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["must_change_password"] is False


def test_login_wrong_password(real_client):
    _, username = _bootstrap_admin(real_client)
    resp = real_client.post(
        f"{API}/auth/login", json={"username": username, "password": "errada-12345"}
    )
    assert resp.status_code == 401


def test_login_unknown_user(real_client):
    resp = real_client.post(
        f"{API}/auth/login",
        json={"username": _unique("ghost"), "password": _PASSWORD},
    )
    assert resp.status_code == 401


def test_login_inactive_user(real_client):
    admin_headers, _ = _bootstrap_admin(real_client)
    gid = _create_group(real_client, admin_headers)
    username, password = _create_user(real_client, admin_headers, gid, active=False)
    resp = real_client.post(f"{API}/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 401


# Refresh
def test_refresh_returns_new_access(real_client):
    username = _unique("admin")
    engine = _sync_engine()
    try:
        with engine.connect() as conn, conn.begin():
            row = conn.execute(
                text("SELECT user_group_id FROM user_group WHERE name = 'Administrador'")
            ).first()
            assert row is not None, "grupo 'Administrador' do seed 0001 ausente"
            gid = row[0]
            conn.execute(
                text(
                    "INSERT INTO app_user (user_group_id, username, email, password_hash) "
                    "VALUES (:g, :u, :e, :h)"
                ),
                {
                    "g": gid,
                    "u": username,
                    "e": f"{username}@test.local",
                    "h": hash_password(_PASSWORD),
                },
            )
    finally:
        engine.dispose()

    login = real_client.post(
        f"{API}/auth/login", json={"username": username, "password": _PASSWORD}
    ).json()
    resp = real_client.post(f"{API}/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]


def test_refresh_garbage_token(real_client):
    resp = real_client.post(f"{API}/auth/refresh", json={"refresh_token": "nao.e.um.jwt"})
    assert resp.status_code == 401


# Logout
def test_logout_revokes_session(real_client):
    headers, _ = _bootstrap_admin(real_client)
    # antes: /me funciona
    assert real_client.get(f"{API}/auth/me", headers=headers).status_code == 200
    # logout
    assert real_client.post(f"{API}/auth/logout", headers=headers).status_code == 204
    # depois: o mesmo access token nao serve mais (sessao revogada)
    assert real_client.get(f"{API}/auth/me", headers=headers).status_code == 401


# Me
def test_me_returns_profile_and_permissions(real_client):
    headers, username = _bootstrap_admin(real_client)
    resp = real_client.get(f"{API}/auth/me", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["username"] == username
    assert body["permissions"].get("all") is True


def test_me_without_token(real_client):
    assert real_client.get(f"{API}/auth/me").status_code == 401


# Change password
def test_change_password_wrong_current(real_client):
    admin_headers, _ = _bootstrap_admin(real_client)
    gid = _create_group(real_client, admin_headers)
    username, password = _create_user(real_client, admin_headers, gid)
    headers = _login(real_client, username, password)
    resp = real_client.post(
        f"{API}/auth/change-password",
        headers=headers,
        json={"current_password": "nao-confere", "new_password": "novaSenha123"},
    )
    assert resp.status_code == 401


def test_change_password_success_revokes_and_allows_new(real_client):
    admin_headers, _ = _bootstrap_admin(real_client)
    gid = _create_group(real_client, admin_headers)
    username, password = _create_user(real_client, admin_headers, gid)
    headers = _login(real_client, username, password)

    new_password = "novaSenha123"
    resp = real_client.post(
        f"{API}/auth/change-password",
        headers=headers,
        json={"current_password": password, "new_password": new_password},
    )
    assert resp.status_code == 204, resp.text
    # sessao antiga revogada
    assert real_client.get(f"{API}/auth/me", headers=headers).status_code == 401
    # senha nova funciona
    assert (
        real_client.post(
            f"{API}/auth/login", json={"username": username, "password": new_password}
        ).status_code
        == 200
    )
    # senha antiga nao funciona mais
    assert (
        real_client.post(
            f"{API}/auth/login", json={"username": username, "password": password}
        ).status_code
        == 401
    )
