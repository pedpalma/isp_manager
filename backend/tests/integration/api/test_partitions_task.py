# Teste de integração das tasks de gestão de partições.
# ensure_optical_partitions: idempotente; rodar duas vezes não falha.
# drop_old_optical_partitions: drop apenas de partições além da retenção.

from __future__ import annotations

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.tasks.partitions import (
    drop_old_optical_partitions,
    ensure_optical_partitions,
)


def _sync_engine():
    return create_engine(settings.database.build_app_sync_url())


def test_ensure_optical_partitions_is_idempotent():
    r1 = ensure_optical_partitions.apply().get()
    assert r1["months_processed"] >= 1
    # Segunda execução não falha (CREATE TABLE IF NOT EXISTS na função SQL).
    r2 = ensure_optical_partitions.apply().get()
    assert r2["months_processed"] == r1["months_processed"]


def test_drop_old_partitions_creates_and_drops_old_one():
    """Cria manualmente uma partição com sufixo antigo (1900_01) e
    verifica que drop_old_optical_partitions a remove."""
    engine = _sync_engine()
    try:
        with engine.connect() as conn, conn.begin():
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS optical_reading_1900_01
                        PARTITION OF optical_reading
                        FOR VALUES FROM ('1900-01-01') TO ('1900-02-01')
                    """
                )
            )
    finally:
        engine.dispose()

    result = drop_old_optical_partitions.apply().get()
    assert "optical_reading_1900_01" in result["dropped"]

    # Confirma que foi de fato dopada
    engine = _sync_engine()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT 1 FROM pg_class WHERE relname = 'optical_reading_1900_01'")
            ).first()
        assert row is None
    finally:
        engine.dispose()


def test_drop_skips_default_partition():
    """A partição optical_reading_default e safety net e NAO deve ser
    dopada pela task."""
    result = drop_old_optical_partitions.apply().get()
    assert "optical_reading_default" not in result["dropped"]

    engine = _sync_engine()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT 1 FROM pg_class WHERE relname = 'optical_reading_default'")
            ).first()
        assert row is not None
    finally:
        engine.dispose()
