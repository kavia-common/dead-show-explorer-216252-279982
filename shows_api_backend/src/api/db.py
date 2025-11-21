import logging
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from src.api.config import get_settings

logger = logging.getLogger(__name__)

# Global SQLAlchemy base for ORM models
Base = declarative_base()

_engine: Optional[AsyncEngine] = None
# Use module globals dict for late assignment to avoid linter false positives on global statements
_async_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _build_async_dsn(sync_dsn: str) -> str:
    """
    Convert a sync Postgres DSN to an async one if needed.
    Example: postgresql:// -> postgresql+asyncpg://
    """
    if sync_dsn.startswith("postgresql+asyncpg://"):
        return sync_dsn
    if sync_dsn.startswith("postgres://"):
        # modern sqlalchemy expects postgresql scheme
        sync_dsn = "postgresql://" + sync_dsn[len("postgres://") :]
    if sync_dsn.startswith("postgresql://"):
        return "postgresql+asyncpg://" + sync_dsn[len("postgresql://") :]
    return sync_dsn


# PUBLIC_INTERFACE
async def get_engine() -> AsyncEngine:
    """Return a singleton AsyncEngine configured from environment settings."""
    global _engine
    if _engine is None:
        settings = get_settings()
        async_dsn = _build_async_dsn(str(settings.DATABASE_URL))
        # Create engine with safe defaults
        _engine = create_async_engine(
            async_dsn,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
        )
        # assign to module-level factory
        globals()["_async_session_factory"] = async_sessionmaker(
            bind=_engine,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
            class_=AsyncSession,
        )
        logger.info("Async database engine initialized")
    return _engine


# PUBLIC_INTERFACE
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an AsyncSession.
    Ensures session is closed after request.
    """
    factory = globals().get("_async_session_factory")
    if factory is None:
        await get_engine()
        factory = globals().get("_async_session_factory")
    assert factory is not None  # for type checkers
    session: AsyncSession = factory()
    try:
        yield session
    except Exception:
        # On any error, attempt rollback but avoid leaking details
        try:
            await session.rollback()
        except Exception:
            logger.debug("Failed to rollback session", exc_info=False)
        raise
    finally:
        try:
            await session.close()
        except Exception:
            logger.debug("Failed to close session", exc_info=False)


# PUBLIC_INTERFACE
async def init_models() -> None:
    """
    Create tables if they do not exist.
    Intended for development or initial bootstrap; production should use migrations.
    """
    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables ensured (create_all)")
