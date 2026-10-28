"""Tenant isolation (record 0004): one user's collections are invisible to every other user.

The two layers are tested on their own as well as together, so neither can silently stop working:
the database layer (row-level security) with the application's filters bypassed, and the
application layer (the queries' owner filter) with row-level security bypassed.

These tests connect as `sapiduct_api`, a role that is neither superuser nor BYPASSRLS. The
template's other database tests run as the database's superuser inside a rolled-back
transaction, which row-level security never applies to, so isolation can't be tested there.
Data these tests commit is removed afterwards (a TRUNCATE the table owner may run).
"""

from __future__ import annotations

import secrets
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
from asgi_lifespan import LifespanManager
from pydantic import SecretStr
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth import DEV_USER_HEADER
from app.collections import Collection, Document
from app.main import create_app
from app.settings import Settings
from app.tenancy import bind_owner

pytestmark = pytest.mark.anyio

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
        await connection.execute(text("TRUNCATE collection, document CASCADE"))
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


async def test_the_application_role_cannot_bypass_row_level_security(
    api_engine: AsyncEngine,
) -> None:
    async with api_engine.connect() as connection:
        flags = (
            await connection.execute(
                text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
            )
        ).one()
    assert tuple(flags) == (False, False)


async def test_database_layer_alone_hides_other_owners_rows(
    owner_engine: AsyncEngine, api_engine: AsyncEngine
) -> None:
    await seed(owner_engine, "alice", "Alice's notes")
    await seed(owner_engine, "bob", "Bob's notes")
    # No application filter at all: a bare select, as a forgotten WHERE would be.
    async with scoped(api_engine, "alice") as session:
        names = (await session.scalars(select(Collection.name))).all()
    assert names == ["Alice's notes"]
    async with scoped(api_engine, "bob") as session:
        names = (await session.scalars(select(Collection.name))).all()
    assert names == ["Bob's notes"]


async def test_a_transaction_that_names_no_owner_sees_nothing(
    owner_engine: AsyncEngine, api_engine: AsyncEngine
) -> None:
    await seed(owner_engine, "alice", "Alice's notes")
    async with scoped(api_engine, None) as session:
        assert (await session.scalars(select(Collection))).all() == []


async def test_a_pooled_connection_does_not_carry_the_owner_to_the_next_transaction(
    owner_engine: AsyncEngine, api_engine: AsyncEngine
) -> None:
    await seed(owner_engine, "alice", "Alice's notes")
    async with scoped(api_engine, "alice") as session:
        assert len((await session.scalars(select(Collection))).all()) == 1
        await session.commit()
    # The pool has one connection, so this reuses it: the owner must be gone.
    async with scoped(api_engine, None) as session:
        assert (await session.scalars(select(Collection))).all() == []


async def test_an_owner_cannot_write_a_row_for_someone_else(api_engine: AsyncEngine) -> None:
    async with scoped(api_engine, "alice") as session:
        session.add(Collection(owner_id="bob", name="Planted"))
        with pytest.raises(DBAPIError, match="row-level security"):
            await session.commit()


async def test_an_owner_cannot_move_a_row_to_someone_else(
    owner_engine: AsyncEngine, api_engine: AsyncEngine
) -> None:
    await seed(owner_engine, "alice", "Alice's notes")
    async with scoped(api_engine, "alice") as session:
        row = (await session.scalars(select(Collection))).one()
        row.owner_id = "bob"
        with pytest.raises(DBAPIError, match="row-level security"):
            await session.commit()


async def test_a_document_cannot_point_at_another_owners_collection(
    owner_engine: AsyncEngine,
) -> None:
    # Even the superuser, who bypasses row-level security, is stopped by the composite key.
    bobs = await seed(owner_engine, "bob", "Bob's notes")
    async with AsyncSession(owner_engine) as session:
        session.add(
            Document(
                collection_id=bobs.id, owner_id="alice", name="x.pdf", kind="pdf", size_bytes=1
            )
        )
        with pytest.raises(IntegrityError, match="fk_document_collection_owner"):
            await session.commit()


async def test_deleting_a_collection_deletes_its_documents(
    owner_engine: AsyncEngine, api_engine: AsyncEngine
) -> None:
    mine = await seed(owner_engine, "alice", "Alice's notes")
    async with scoped(api_engine, "alice") as session:
        session.add(
            Document(
                collection_id=mine.id, owner_id="alice", name="a.pdf", kind="pdf", size_bytes=3
            )
        )
        await session.commit()
        await session.delete((await session.scalars(select(Collection))).one())
        await session.commit()
    async with AsyncSession(owner_engine) as session:
        assert (await session.scalars(select(Document))).all() == []


async def test_application_layer_alone_filters_by_owner(
    owner_engine: AsyncEngine, database_url: str
) -> None:
    """With row-level security bypassed (the superuser), the queries' own owner filter holds."""
    await seed(owner_engine, "alice", "Alice's notes")
    await seed(owner_engine, "bob", "Bob's notes")
    settings = Settings(_env_file=None, app_env="test", database_url=SecretStr(database_url))
    app = create_app(settings)
    async with LifespanManager(app) as manager:
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            listed = (
                await client.get("/v1/collections", headers={DEV_USER_HEADER: "alice"})
            ).json()
    assert [c["name"] for c in listed["items"]] == ["Alice's notes"]


@pytest.fixture
async def client(api_url: str, owner_engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    """The whole app, connected as the application's role."""
    settings = Settings(_env_file=None, app_env="test", database_url=SecretStr(api_url))
    app = create_app(settings)
    async with LifespanManager(app) as manager:
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


def as_user(name: str) -> dict[str, str]:
    return {DEV_USER_HEADER: name}


async def test_a_user_cannot_read_change_or_delete_another_users_collection(
    client: httpx.AsyncClient,
) -> None:
    made = await client.post(
        "/v1/collections", json={"name": "Physics notes"}, headers=as_user("alice")
    )
    assert made.status_code == 201
    mine = made.json()["id"]

    assert (await client.get(f"/v1/collections/{mine}", headers=as_user("bob"))).status_code == 404
    renamed = await client.patch(
        f"/v1/collections/{mine}", json={"name": "Hijacked"}, headers=as_user("bob")
    )
    assert renamed.status_code == 404
    assert (
        await client.delete(f"/v1/collections/{mine}", headers=as_user("bob"))
    ).status_code == 404
    # Still there, still alice's, still named what she called it.
    still = await client.get(f"/v1/collections/{mine}", headers=as_user("alice"))
    assert still.status_code == 200
    assert still.json()["name"] == "Physics notes"
    # Bob's own list is empty.
    assert (await client.get("/v1/collections", headers=as_user("bob"))).json()["items"] == []


async def test_names_are_unique_per_user_not_across_users(client: httpx.AsyncClient) -> None:
    first = await client.post("/v1/collections", json={"name": "Notes"}, headers=as_user("alice"))
    assert first.status_code == 201
    same_name_other_user = await client.post(
        "/v1/collections", json={"name": "NOTES"}, headers=as_user("bob")
    )
    assert same_name_other_user.status_code == 201
    duplicate = await client.post(
        "/v1/collections", json={"name": "notes"}, headers=as_user("alice")
    )
    assert duplicate.status_code == 409


async def test_public_ids_are_distinct_and_unguessable(client: httpx.AsyncClient) -> None:
    ids = set()
    for index in range(5):
        made = await client.post(
            "/v1/collections", json={"name": f"Collection {index}"}, headers=as_user("alice")
        )
        ids.add(made.json()["public_id"])
    assert len(ids) == 5
    assert all(len(public_id) == 16 for public_id in ids)


async def test_lists_page_with_a_cursor_and_never_cross_owners(client: httpx.AsyncClient) -> None:
    for index in range(7):
        await client.post(
            "/v1/collections", json={"name": f"Alice {index}"}, headers=as_user("alice")
        )
    await client.post("/v1/collections", json={"name": "Bob 0"}, headers=as_user("bob"))

    seen: list[str] = []
    cursor: str | None = None
    while True:
        params: dict[str, str | int] = {"limit": 3}
        if cursor:
            params["cursor"] = cursor
        body = (await client.get("/v1/collections", params=params, headers=as_user("alice"))).json()
        seen += [item["name"] for item in body["items"]]
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert seen == [f"Alice {index}" for index in range(6, -1, -1)]  # newest first, none of Bob's


async def test_a_bad_cursor_is_a_400(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/v1/collections", params={"cursor": "not-a-cursor"}, headers=as_user("alice")
    )
    assert response.status_code == 400


async def test_an_unknown_collection_id_is_a_404_not_a_500(client: httpx.AsyncClient) -> None:
    missing = uuid.uuid4()
    response = await client.get(f"/v1/collections/{missing}", headers=as_user("alice"))
    assert response.status_code == 404


async def test_requests_without_a_user_are_refused(client: httpx.AsyncClient) -> None:
    assert (await client.get("/v1/collections")).status_code == 401


async def test_names_are_trimmed_before_their_length_is_checked(client: httpx.AsyncClient) -> None:
    for name in ("   ", " a ", "ab", "x" * 81):
        response = await client.post(
            "/v1/collections", json={"name": name}, headers=as_user("alice")
        )
        assert response.status_code == 422, name
    made = await client.post(
        "/v1/collections", json={"name": "  Notes  "}, headers=as_user("alice")
    )
    assert made.status_code == 201
    assert made.json()["name"] == "Notes"
    renamed = await client.patch(
        f"/v1/collections/{made.json()['id']}", json={"name": "  "}, headers=as_user("alice")
    )
    assert renamed.status_code == 422


async def test_the_database_refuses_a_blank_name_even_without_the_api(
    owner_engine: AsyncEngine,
) -> None:
    async with AsyncSession(owner_engine) as session:
        session.add(Collection(owner_id="alice", name="  "))
        with pytest.raises(IntegrityError, match="ck_collection_name"):
            await session.commit()


async def test_the_application_role_can_use_every_runtime_table(
    owner_engine: AsyncEngine,
) -> None:
    """The model budget and agent checkpoints are not tenant tables, but the API reads and writes
    them with the same login; a restricted role that lacked them would fail on the first model
    call. Alembic's own version table stays out of reach."""
    async with owner_engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    "SELECT tablename, "
                    "has_table_privilege(:login, format('public.%I', tablename), "
                    "'SELECT,INSERT,UPDATE,DELETE') "
                    "FROM pg_tables WHERE schemaname = 'public'"
                ),
                {"login": LOGIN},
            )
        ).all()
    allowed = {str(name): bool(granted) for name, granted in rows}
    assert allowed.pop("alembic_version") is False
    missing = sorted(name for name, granted in allowed.items() if not granted)
    assert missing == []
    assert {"llm_call", "llm_spend_day", "llm_spend_user_day", "collection", "document"} <= set(
        allowed
    )
