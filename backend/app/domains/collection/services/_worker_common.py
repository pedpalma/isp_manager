# Módulo de suporte ao worker de coleta.
# Extração da logica compartilhada entre discovery_worker e signal_reading_worker:
# - carga de OLT + credencial + resolução de secret
# - construção de OltConnectionConfig
# - advisory lock por olt_id contra colisão entre jobs concorrentes na mesma OLT.
# Importação por discovery_worker e signal_reading_worker.
# Não expõem nada que dependa de domain collection ou optical; são puro suporte.

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.adapters.olt.base import OltConnectionConfig
from app.adapters.secrets.factory import get_secret_store
from app.core.exceptions import ConfigurationError
from app.domains.inventory.models.credential import Credential
from app.domains.inventory.models.olt import Olt

log = structlog.get_logger(__name__)


class OltLockUnavailable(Exception):
    """Outro job esta segurando o advisory lock daquela OLT.
    Worker traduz para FAILED com error_message clara."""


def acquire_olt_advisory_lock(db: Session, olt_id: UUID) -> None:
    """Tenta obter advisory lock TRANSACIONAL por olt_id.
    Lock vive até o fim da transação corrente; libera automático no
    commit/rollback. Evita que discovery + signal_reading concorram
    pela mesma sessão SSH na mesma OLT."""
    row = db.execute(
        text("SELECT pg_try_advisory_xact_lock(hashtext(:olt_id))"),
        {"olt_id": str(olt_id)},
    ).first()
    if row is None or not bool(row[0]):
        raise OltLockUnavailable(f"OLT {olt_id} esta com outro job de coleta ativo.")


def load_olt_and_credential(db: Session, olt_id: UUID) -> tuple[Olt, Credential]:
    """Carrega OLT viva + credencial ativa. Levanta ConfigurationError
    quando qualquer um deles esta indisponível (500 genérico no caller)."""
    olt_stmt = select(Olt).where(Olt.olt_id == olt_id, Olt.deleted_at.is_(None))
    olt = db.execute(olt_stmt).scalar_one_or_none()
    if olt is None:
        raise ConfigurationError(
            f"OLT {olt_id} não encontrada ou inativa.",
            details={"olt_id": str(olt_id)},
        )

    cred_stmt = select(Credential).where(
        Credential.credential_id == olt.credential_id,
        Credential.active.is_(True),
    )
    credential = db.execute(cred_stmt).scalar_one_or_none()
    if credential is None:
        raise ConfigurationError(
            f"Credencial {olt.credential_id} inativa ou inexistente.",
            details={"credential_id": str(olt.credential_id)},
        )
    return olt, credential


def build_connection_config(olt: Olt, credential: Credential) -> OltConnectionConfig:
    """Resolve segredo via secret_store e monta OltConnectionConfig."""
    secret_store = get_secret_store()
    password = secret_store.resolve(credential.secret_ref)
    return OltConnectionConfig(
        host=str(olt.ip),
        port=int(olt.management_port),
        protocol=str(olt.access_protocol.value)
        if hasattr(olt.access_protocol, "value")
        else str(olt.access_protocol),
        username=credential.username,
        password=password,
    )
