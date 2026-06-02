# Sessão síncrona do SQLAlchemy exclusiva para o Celery
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Tanto a engine quanto o sessionmaker são criados com Lazy pelo worker
_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def _ensure_factory() -> sessionmaker[Session]:
    # Garante inicialização do Engine + sessionmaker
    global _engine, _SessionFactory
    if _SessionFactory is None:
        _engine = create_engine(
            settings.database.buid_app_sync_url(),
            pool_pre_ping=True,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            pool_recycle=settings.database.pool_recycle,
            echo=settings.database.echo_sql,
            future=True,
        )
        _SessionFactory = sessionmaker(
            bind=_engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    return _SessionFactory


@contextmanager
def session_scope() -> Iterator[Session]:
    # Commit se der certo, rollback se der erro
    factory = _ensure_factory()
    db = factory()

    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def dispose_sync_engine() -> None:
    # Descarta o engine
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionFactory = None
