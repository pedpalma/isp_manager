from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# Engine e sessionmaker globais do módulo, inicializados no startup.
_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine() -> AsyncEngine:

    # Cria o engine async e o sessionmaker.

    global _engine, _sessionmaker

    if _engine is not None:
        return _engine

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
    # Fecha o engine e drena o pool. Chamado no shutdown do lifespan
    global _engine, _sessionmaker

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None


def get_engine() -> AsyncEngine:
    # Retorna o engine. Erro se chamado antes de init_engine
    if _engine is None:
        raise RuntimeError("Engine não inicializado. init_engine() deve ser chamada no startup.")
    return _engine


async def get_session() -> AsyncIterator[AsyncSession]:

    # Dependency da FastAPI para injetar uma AsyncSession por request.

    if _sessionmaker is None:
        raise RuntimeError(
            "Sessionmaker não inicializado. init_engine() deve ser chamada no startup."
        )

    async with _sessionmaker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
