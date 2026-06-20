#!/usr/bin/env python
# Seed idempotente do admin inicial.

# Resolve o gargalo de bootstrap: com enforcement ligado, sem um admin
# ninguém cria o primeiro admin pela API. Este script cria (ou confirma) um
# app_user administrador, parametrizado por variáveis de ambiente, e pode
# rodar tanto em dev quanto em prod. Idempotente: rodar de novo nao duplica
# nem sobrescreve a senha de um admin já existente.

# O grupo 'Administrador' ({"all": true}) já vem do seed da migration 0001,
# então aqui é garantido o usuário apontando para ele.

# Uso:
# ADMIN_USERNAME=admin ADMIN_PASSWORD='trocar-no-primeiro-login' \
# ADMIN_EMAIL=admin@local python -m scripts.seed_admin

# Variáveis:
# ADMIN_USERNAME (default: "admin")
# ADMIN_PASSWORD (obrigatória)
# ADMIN_EMAIL (default: "<username>@local")
# ADMIN_GROUP_NAME (default: "Administrador")
# ADMIN_MUST_CHANGE_PASSWORD (default: "true")

from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.domains.auth.security import hash_password


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    username = os.environ.get("ADMIN_USERNAME", "admin").strip()
    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        print("ERRO: ADMIN_PASSWORD não definida.", file=sys.stderr)
        return 2
    email = os.environ.get("ADMIN_EMAIL", f"{username}@local").strip()
    group_name = os.environ.get("ADMIN_GROUP_NAME", "Administrador").strip()
    must_change = _env_bool("ADMIN_MUST_CHANGE_PASSWORD", True)

    engine = create_engine(settings.database.build_app_sync_url())
    try:
        with engine.connect() as conn, conn.begin():
            group_row = conn.execute(
                text("SELECT user_group_id FROM user_group WHERE name = :n"),
                {"n": group_name},
            ).first()
            if group_row is None:
                print(
                    f"ERRO: grupo '{group_name}' não existe. "
                    "Confirme que a migration 0001 (com o seed) foi aplicada.",
                    file=sys.stderr,
                )
                return 3
            group_id = group_row[0]

            existing = conn.execute(
                text("SELECT app_user_id FROM app_user WHERE username = :u"),
                {"u": username},
            ).first()
            if existing is not None:
                print(
                    f"OK: usuário '{username}' já existe "
                    f"(app_user_id={existing[0]}). Nada a fazer (idempotente)."
                )
                return 0

            conn.execute(
                text(
                    """
                    INSERT INTO app_user
                        (user_group_id, username, email, password_hash,
                        must_change_password)
                    VALUES (:g, :u, :e, :h, :m)
                    """
                ),
                {
                    "g": group_id,
                    "u": username,
                    "e": email,
                    "h": hash_password(password),
                    "m": must_change,
                },
            )
        print(f"OK: admin '{username}' criado no grupo '{group_name}'.")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
