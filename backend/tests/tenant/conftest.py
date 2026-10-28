"""Fixtures for tests that need the application's own restricted database role (record 0004)."""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.collections import Collection
from app.tenancy import bind_owner

LOGIN = "sapiduct_test_login"
PASSWORD = secrets.token_hex(16)  # a throwaway role on a throwaway test database, new each run


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="module")
async def api_url(database_url: str) -> AsyncIterator[str]:
    """A login that is a member of sapiduct_api (created by the migration), on the test database."""
    admin = create_async_engine(database_url, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    async with admin.connect() as connection:
        await connection.execute(text(f"DROP ROLE IF EXISTS {LOGIN}"))
        await connection.execute(
            text(f"CREATE ROLE {LOGIN} LOGIN PASSWORD '{PASSWORD}' IN ROLE sapiduct_api")
        )
    await admin.dispose()
    yield (
        make_url(database_url)
        .set(username=LOGIN, password=PASSWORD)
        .render_as_string(hide_password=False)
    )
    admin = create_async_engine(database_url, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    async with admin.connect() as connection:
        await connection.execute(text(f"DROP OWNED BY {LOGIN}"))
        await connection.execute(text(f"DROP ROLE {LOGIN}"))
    await admin.dispose()


@pytest.fixture
async def owner_engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    """The database's superuser: bypasses row-level security, so it can seed and clean up."""
    engine = create_async_engine(database_url, poolclass=NullPool)
    yield engine
    async with engine.begin() as connection:
        await connection.execute(
            text("TRUNCATE collection, document, access_token, rate_window, mcp_call CASCADE")
        )
    await engine.dispose()


@pytest.fixture
async def api_engine(api_url: str, owner_engine: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    """The application's role. One connection only, so every test also proves a pooled connection
    does not carry one transaction's owner into the next."""
    engine = create_async_engine(api_url, pool_size=1, max_overflow=0)
    yield engine
    await engine.dispose()


def scoped(engine: AsyncEngine, owner: str | None) -> AsyncSession:
    session = async_sessionmaker(engine, expire_on_commit=False)()
    if owner is not None:
        bind_owner(session, owner)
    return session


async def seed(owner_engine: AsyncEngine, owner: str, name: str) -> Collection:
    async with AsyncSession(owner_engine, expire_on_commit=False) as session:
        row = Collection(owner_id=owner, name=name)
        session.add(row)
        await session.commit()
        return row
