"""The MCP door (records 0005, 0006, 0009): tokens, scoping, limits.

Like the tenancy tests, these run the whole app as the application's restricted database role, so
row-level security applies. Requests are JSON-RPC posts through httpx, in process.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.auth import DEV_USER_HEADER
from app.collections import Document
from app.main import create_app
from app.settings import Settings

pytestmark = pytest.mark.anyio

MCP_HEADERS = {"accept": "application/json, text/event-stream", "content-type": "application/json"}


@dataclass
class Setup:
    client: httpx.AsyncClient
    engine: AsyncEngine


def build_settings(url: str, **extra: Any) -> Settings:
    return Settings(_env_file=None, app_env="test", database_url=SecretStr(url), **extra)


@pytest.fixture
async def setup(api_url: str, owner_engine: AsyncEngine) -> AsyncIterator[Setup]:
    app = create_app(build_settings(api_url, mcp_rate_per_minute=5))
    async with LifespanManager(app) as manager:
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield Setup(client, owner_engine)


async def make_collection(s: Setup, owner: str, name: str = "Physics notes") -> dict[str, Any]:
    made = await s.client.post(
        "/v1/collections", json={"name": name}, headers={DEV_USER_HEADER: owner}
    )
    assert made.status_code == 201, made.text
    return dict(made.json())


async def make_token(s: Setup, owner: str, collection_id: str) -> dict[str, Any]:
    made = await s.client.post(
        f"/v1/collections/{collection_id}/tokens", headers={DEV_USER_HEADER: owner}
    )
    assert made.status_code == 201, made.text
    return dict(made.json())


async def public_id(s: Setup, collection_id: str) -> str:
    async with AsyncSession(s.engine) as session:
        return str(
            await session.scalar(
                text("SELECT public_id FROM collection WHERE id = :i"), {"i": collection_id}
            )
        )


async def add_document(s: Setup, owner: str, collection_id: str, name: str) -> None:
    async with AsyncSession(s.engine) as session:
        session.add(
            Document(
                collection_id=collection_id, owner_id=owner, name=name, kind="pdf", size_bytes=10
            )
        )
        await session.commit()


def call(tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments or {}},
    }


async def post(
    s: Setup, pid: str, body: dict[str, Any], token: str | None, **headers: str
) -> httpx.Response:
    sent = {**MCP_HEADERS, **headers}
    if token is not None:
        sent["authorization"] = f"Bearer {token}"
    return await s.client.post(f"/mcp/{pid}", json=body, headers=sent)


def result_of(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    text_body = response.text
    if response.headers["content-type"].startswith("text/event-stream"):
        text_body = next(
            line[5:].strip() for line in text_body.splitlines() if line.startswith("data:")
        )
    payload = json.loads(text_body)
    assert "error" not in payload, payload
    return dict(payload["result"]["structuredContent"])


async def test_a_token_reads_its_own_collection(setup: Setup) -> None:
    mine = await make_collection(setup, "alice")
    await add_document(setup, "alice", mine["id"], "lecture-1.pdf")
    token = await make_token(setup, "alice", mine["id"])
    pid = await public_id(setup, mine["id"])

    listed = result_of(await post(setup, pid, call("list_sources"), token["token"]))
    assert [s["name"] for s in listed["sources"]] == ["lecture-1.pdf"]
    assert listed["total"] == 1


async def test_a_token_does_not_open_another_collection_of_the_same_owner(setup: Setup) -> None:
    first = await make_collection(setup, "alice", "First")
    second = await make_collection(setup, "alice", "Second")
    token = await make_token(setup, "alice", first["id"])
    response = await post(
        setup, await public_id(setup, second["id"]), call("list_sources"), token["token"]
    )
    assert response.status_code == 401


async def test_one_owners_token_never_reads_another_owners_documents(setup: Setup) -> None:
    alice = await make_collection(setup, "alice")
    bob = await make_collection(setup, "bob")
    await add_document(setup, "bob", bob["id"], "bobs-secret.pdf")
    token = await make_token(setup, "alice", alice["id"])
    listed = result_of(
        await post(setup, await public_id(setup, alice["id"]), call("list_sources"), token["token"])
    )
    assert listed["sources"] == []
    # Even with a document id that exists, in a collection that is not the token's.
    async with AsyncSession(setup.engine) as session:
        bobs_id = await session.scalar(text("SELECT id FROM document"))
    got = await post(
        setup,
        await public_id(setup, alice["id"]),
        call("get_document", {"document_id": str(bobs_id)}),
        token["token"],
    )
    assert got.status_code == 200
    assert "bobs-secret" not in got.text


@pytest.mark.parametrize(
    "authorization",
    [None, "Basic abc", "Bearer", "Bearer nope", "Bearer sap_" + "x" * 200, "Bearer sap_unknown"],
)
async def test_a_missing_or_malformed_token_gets_the_same_401(
    setup: Setup, authorization: str | None
) -> None:
    mine = await make_collection(setup, "alice")
    headers = dict(MCP_HEADERS)
    if authorization:
        headers["authorization"] = authorization
    response = await setup.client.post(
        f"/mcp/{await public_id(setup, mine['id'])}", json=call("list_sources"), headers=headers
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"error": "unauthorized"}


async def test_a_token_in_the_query_string_is_ignored(setup: Setup) -> None:
    mine = await make_collection(setup, "alice")
    token = await make_token(setup, "alice", mine["id"])
    pid = await public_id(setup, mine["id"])
    response = await setup.client.post(
        f"/mcp/{pid}?token={token['token']}", json=call("list_sources"), headers=MCP_HEADERS
    )
    assert response.status_code == 401


async def test_a_revoked_token_stops_working(setup: Setup) -> None:
    mine = await make_collection(setup, "alice")
    token = await make_token(setup, "alice", mine["id"])
    pid = await public_id(setup, mine["id"])
    assert (await post(setup, pid, call("list_sources"), token["token"])).status_code == 200
    revoked = await setup.client.delete(
        f"/v1/collections/{mine['id']}/tokens/{token['id']}", headers={DEV_USER_HEADER: "alice"}
    )
    assert revoked.status_code == 204
    assert (await post(setup, pid, call("list_sources"), token["token"])).status_code == 401


async def test_an_expired_token_stops_working(setup: Setup) -> None:
    mine = await make_collection(setup, "alice")
    token = await make_token(setup, "alice", mine["id"])
    async with AsyncSession(setup.engine) as session:
        await session.execute(text("UPDATE access_token SET ends_at = now() - interval '1 second'"))
        await session.commit()
    pid = await public_id(setup, mine["id"])
    assert (await post(setup, pid, call("list_sources"), token["token"])).status_code == 401


async def test_rotation_keeps_the_old_token_for_the_overlap_then_caps_at_two(
    setup: Setup,
) -> None:
    mine = await make_collection(setup, "alice")
    old = await make_token(setup, "alice", mine["id"])
    new = await make_token(setup, "alice", mine["id"])
    pid = await public_id(setup, mine["id"])
    assert (await post(setup, pid, call("list_sources"), old["token"])).status_code == 200
    assert (await post(setup, pid, call("list_sources"), new["token"])).status_code == 200
    third = await setup.client.post(
        f"/v1/collections/{mine['id']}/tokens", headers={DEV_USER_HEADER: "alice"}
    )
    assert third.status_code == 409


async def test_a_disallowed_origin_is_refused_and_an_unknown_id_is_a_404(setup: Setup) -> None:
    mine = await make_collection(setup, "alice")
    token = await make_token(setup, "alice", mine["id"])
    pid = await public_id(setup, mine["id"])
    evil = await post(
        setup, pid, call("list_sources"), token["token"], origin="https://evil.example"
    )
    assert evil.status_code == 403
    assert (await post(setup, "short", call("list_sources"), token["token"])).status_code == 404


async def test_the_rate_limit_admits_exactly_the_limit_under_concurrency(setup: Setup) -> None:
    mine = await make_collection(setup, "alice")
    token = await make_token(setup, "alice", mine["id"])
    pid = await public_id(setup, mine["id"])
    responses = await asyncio.gather(
        *(post(setup, pid, call("list_sources"), token["token"]) for _ in range(12))
    )
    statuses = sorted(r.status_code for r in responses)
    assert statuses.count(200) == 5  # the per-minute limit this fixture sets
    assert statuses.count(429) == 7
    assert all(r.headers.get("retry-after") for r in responses if r.status_code == 429)


async def test_the_token_is_stored_only_as_a_digest_and_shown_once(setup: Setup) -> None:
    mine = await make_collection(setup, "alice")
    token = await make_token(setup, "alice", mine["id"])
    async with AsyncSession(setup.engine) as session:
        stored = (await session.execute(text("SELECT token_hash, last4 FROM access_token"))).one()
    assert token["token"].encode() not in bytes(stored[0])
    assert len(bytes(stored[0])) == 32
    assert stored[1] == token["token"][-4:]
    listed = await setup.client.get(
        f"/v1/collections/{mine['id']}/tokens", headers={DEV_USER_HEADER: "alice"}
    )
    assert token["token"] not in listed.text
    assert "token" not in listed.json()["items"][0]


async def test_a_user_cannot_manage_another_users_tokens(setup: Setup) -> None:
    mine = await make_collection(setup, "alice")
    token = await make_token(setup, "alice", mine["id"])
    bob = {DEV_USER_HEADER: "bob"}
    assert (
        await setup.client.post(f"/v1/collections/{mine['id']}/tokens", headers=bob)
    ).status_code == 404
    assert (
        await setup.client.get(f"/v1/collections/{mine['id']}/tokens", headers=bob)
    ).status_code == 404
    assert (
        await setup.client.delete(f"/v1/collections/{mine['id']}/tokens/{token['id']}", headers=bob)
    ).status_code == 404


async def test_tool_calls_are_recorded_without_the_token(setup: Setup) -> None:
    mine = await make_collection(setup, "alice")
    token = await make_token(setup, "alice", mine["id"])
    pid = await public_id(setup, mine["id"])
    await post(setup, pid, call("search", {"query": "entropy"}), token["token"])
    async with AsyncSession(setup.engine) as session:
        rows = (await session.execute(text("SELECT tool, status, arguments FROM mcp_call"))).all()
    assert [(r[0], r[1]) for r in rows] == [("search", "ok")]
    assert token["token"] not in rows[0][2]


async def test_a_real_mcp_client_lists_the_tools_and_reads_a_collection(
    api_url: str, owner_engine: AsyncEngine
) -> None:
    """FastMCP's own client over the whole path: handshake, tool listing, a tool call."""
    import httpx2
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport

    app = create_app(build_settings(api_url))
    async with LifespanManager(app) as manager:
        transport = httpx.ASGITransport(app=manager.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as web:
            s = Setup(web, owner_engine)
            mine = await make_collection(s, "alice")
            await add_document(s, "alice", mine["id"], "lecture-1.pdf")
            token = await make_token(s, "alice", mine["id"])
            pid = await public_id(s, mine["id"])

        def factory(
            headers: dict[str, str] | None = None,
            timeout: httpx2.Timeout | None = None,
            auth: httpx2.Auth | None = None,
            **extra: Any,
        ) -> httpx2.AsyncClient:
            return httpx2.AsyncClient(
                follow_redirects=bool(extra.get("follow_redirects", False)),
                transport=httpx2.ASGITransport(app=manager.app),
                headers=headers,
                timeout=timeout or httpx2.Timeout(30),
                auth=auth,
            )

        mcp_transport = StreamableHttpTransport(
            f"http://test/mcp/{pid}",
            headers={"Authorization": f"Bearer {token['token']}"},
            httpx_client_factory=factory,
        )
        async with Client(mcp_transport) as client:
            tools = await client.list_tools()
            assert {t.name for t in tools} == {"search", "get_document", "list_sources"}
            assert all(t.annotations and t.annotations.read_only_hint for t in tools)
            listed = await client.call_tool("list_sources", {})
            assert listed.data["sources"][0]["name"] == "lecture-1.pdf"


def tool_error(response: httpx.Response) -> bool:
    """True when the tool answered with an error result (the call itself still returns 200)."""
    assert response.status_code == 200, response.text
    text_body = response.text
    if response.headers["content-type"].startswith("text/event-stream"):
        text_body = next(
            line[5:].strip() for line in text_body.splitlines() if line.startswith("data:")
        )
    payload = json.loads(text_body)
    return "error" in payload or bool(payload.get("result", {}).get("isError"))


async def ready(s: Setup, owner: str = "alice") -> tuple[dict[str, Any], str, str]:
    mine = await make_collection(s, owner)
    token = await make_token(s, owner, mine["id"])
    return mine, await public_id(s, mine["id"]), str(token["token"])


async def test_list_sources_pages_through_every_document_once(setup: Setup) -> None:
    mine, pid, token = await ready(setup)
    for n in range(7):
        await add_document(setup, "alice", mine["id"], f"doc-{n}.pdf")
    seen: list[str] = []
    cursor: str | None = None
    for _ in range(5):
        arguments: dict[str, Any] = {"limit": 3}
        if cursor:
            arguments["cursor"] = cursor
        page = result_of(await post(setup, pid, call("list_sources", arguments), token))
        assert page["total"] == 7
        seen += [s["name"] for s in page["sources"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert sorted(seen) == [f"doc-{n}.pdf" for n in range(7)]
    assert len(set(seen)) == 7


@pytest.mark.parametrize("limit", [0, -1, 26, 1000])
async def test_list_sources_refuses_a_limit_outside_its_bounds(setup: Setup, limit: int) -> None:
    _, pid, token = await ready(setup)
    response = await post(setup, pid, call("list_sources", {"limit": limit}), token)
    assert tool_error(response)


async def test_a_forged_cursor_is_refused_not_trusted(setup: Setup) -> None:
    _, pid, token = await ready(setup)
    response = await post(setup, pid, call("list_sources", {"cursor": "not-a-cursor"}), token)
    assert tool_error(response)


@pytest.mark.parametrize("arguments", [{"query": ""}, {"query": "   "}, {"query": "x" * 501}])
async def test_search_refuses_an_empty_or_oversized_query(
    setup: Setup, arguments: dict[str, Any]
) -> None:
    _, pid, token = await ready(setup)
    assert tool_error(await post(setup, pid, call("search", arguments), token))


async def test_search_never_returns_more_than_its_maximum(setup: Setup) -> None:
    mine, pid, token = await ready(setup)
    for n in range(15):
        await add_document(setup, "alice", mine["id"], f"doc-{n}.pdf")
    got = result_of(await post(setup, pid, call("search", {"query": "entropy"}), token))
    assert len(got["results"]) == 5  # the default
    assert tool_error(await post(setup, pid, call("search", {"query": "e", "limit": 11}), token))


async def test_get_document_is_bounded_and_continues_with_an_offset(setup: Setup) -> None:
    mine, pid, token = await ready(setup)
    await add_document(setup, "alice", mine["id"], "big.pdf")
    async with AsyncSession(setup.engine) as session:
        document_id = str(await session.scalar(text("SELECT id FROM document")))
    first = result_of(
        await post(setup, pid, call("get_document", {"document_id": document_id}), token)
    )
    assert len(first["text"]) == 20000
    assert first["next_offset"] == 20000
    second = result_of(
        await post(
            setup,
            pid,
            call("get_document", {"document_id": document_id, "offset": first["next_offset"]}),
            token,
        )
    )
    assert second["offset"] == 20000
    assert tool_error(await post(setup, pid, call("get_document", {"document_id": "nope"}), token))


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("get_document", {"document_id": "00000000-0000-0000-0000-000000000000"}),
        ("get_document", {"document_id": "not-a-uuid"}),
        ("search", {"query": "   "}),
        ("list_sources", {"limit": 0}),
        ("list_sources", {"cursor": "forged"}),
    ],
)
async def test_a_rejected_tool_call_is_recorded_as_an_error(
    setup: Setup, tool: str, arguments: dict[str, Any]
) -> None:
    _, pid, token = await ready(setup)
    await post(setup, pid, call(tool, arguments), token)
    async with AsyncSession(setup.engine) as session:
        rows = (await session.execute(text("SELECT tool, status FROM mcp_call"))).all()
    assert [tuple(r) for r in rows] == [(tool, "error")]


async def test_an_unexpected_failure_inside_a_tool_is_recorded_without_its_detail(
    setup: Setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, pid, token = await ready(setup)

    async def broken(*_: Any, **__: Any) -> None:
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(AsyncSession, "scalar", broken)
    response = await post(
        setup, pid, call("get_document", {"document_id": str(uuid.uuid4())}), token
    )
    assert "secret internal detail" not in response.text
    async with AsyncSession(setup.engine) as session:
        rows = (
            await session.execute(text("SELECT tool, status, result_summary FROM mcp_call"))
        ).all()
    assert [tuple(r) for r in rows] == [("get_document", "error", "RuntimeError")]


async def test_a_rate_limited_request_is_not_written_as_a_call(setup: Setup) -> None:
    _, pid, token = await ready(setup)
    for _ in range(7):  # the fixture's limit is 5 a minute
        await post(setup, pid, call("list_sources"), token)
    async with AsyncSession(setup.engine) as session:
        calls = await session.scalar(text("SELECT count(*) FROM mcp_call"))
    assert calls == 5


async def test_the_token_never_appears_in_the_logs(
    setup: Setup, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    _, pid, token = await ready(setup)
    await post(setup, pid, call("list_sources"), token)
    await post(setup, pid, call("list_sources"), token + "x")
    out = capsys.readouterr()
    assert token not in caplog.text + out.out + out.err
