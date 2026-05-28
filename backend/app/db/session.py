from _collections_abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

# Engine e sessionmaker globais do módulo
_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine() -> AsyncEngine:
    # Cria o engine async e o sessionmaker
    global _engine, _sessionmaker

    if _engine is not None:
        return _engine

    settings = get_settings()

    _engine = create_async_engine(
        settings.database.build_app_url(),
        echo=settings.database.echo_sql,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_timeout=settings.database.pool_timeout,
        pool_recycle=settings.database.pool_recycle,
        pool_pre_ping=True,
        connect_args={
            "server_settings": {
                "statement_timeout": str(settings.database.statement_timeout_ms),
                "application_name": settings.app.app_name,
            },
        },
    )

    _sessionmaker = async_sessionmaker(
        bind=_engine,
        expire_on_commit=False,
        autoflush=False,
    )

    return _engine


async def dispose_engine() -> None:
    # Fecha a engine
    global _engine, _sessionmaker

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None


def get_engine() -> AsyncEngine:
    # Retorna a engine
    if _engine is None:
        raise RuntimeError("Engine did not started, call init_engine() on startup.")
    return _engine


async def get_session() -> AsyncIterator[AsyncSession]:
    # FastAPI usa para injetar AssyncSession por request
    if _sessionmaker is None:
        raise RuntimeError("Sessionmaker did not started, call init_engine() on startup.")

    async with _sessionmaker as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
