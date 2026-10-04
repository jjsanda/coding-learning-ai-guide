from collections.abc import AsyncIterator

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from codeguide.auth import hash_token, new_instructor_token
from codeguide.db import get_db
from codeguide.main import create_app
from codeguide.models import Base, Instructor


@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(
    db_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with db_factory() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
def _reset_rate_limiters() -> None:
    # The rate limiters are process-global; clear them so per-test request
    # volume doesn't accumulate across the suite (all tests share a client IP).
    from codeguide.api import auth, submissions

    auth._join_limiter._events.clear()
    submissions.rate_limiter._events.clear()


@pytest_asyncio.fixture
async def client(
    db_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()

    async def _get_db() -> AsyncIterator[AsyncSession]:
        async with db_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def instructor_token(db_session: AsyncSession) -> str:
    token = new_instructor_token()
    db_session.add(
        Instructor(
            name="Test Instructor",
            email="instructor@example.edu",
            token_hash=hash_token(token),
        )
    )
    await db_session.commit()
    return token


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
