"""The door in front of every collection's MCP server (records 0005, 0006, 0009).

A pure ASGI middleware (not Starlette's BaseHTTPMiddleware, which would buffer the streamed
responses MCP uses). For each request to `{prefix}/{public_id}` it, in this order:

1. refuses an `Origin` that is present and not allowed, with 403 (the MCP specification requires
   it, to stop DNS-rebinding from a web page);
2. reads the bearer token from the Authorization header only, never the query string;
3. looks the token up by its SHA-256 digest together with the collection's public id, through the
   one SECURITY DEFINER function, so a token works for exactly one collection;
4. admits the call against the per-minute and per-day limits in one atomic upsert per window,
   committed before the tool runs;
5. hands FastMCP the request with the tenant attached to the request state.

A missing, malformed, unknown, revoked, expired or wrong-collection token all get the same 401, so
a response never says which collection exists. Nothing here logs or stores the token.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import MutableMapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.types import ASGIApp, Receive, Scope, Send

from app.mcp.limits import admit
from app.mcp.tokens import MAX_TOKEN_LENGTH, PREFIX, digest_of
from app.settings import Settings

PUBLIC_ID = re.compile(r"^[A-Za-z0-9_-]{16}$")
_RESOLVE = text("SELECT owner_id, collection_id, token_id FROM resolve_access_token(:h, :p)")


@dataclass(frozen=True, slots=True)
class Tenant:
    """Who a request is for, once its token is accepted."""

    owner_id: str
    collection_id: uuid.UUID
    token_id: uuid.UUID
    public_id: str


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope["headers"]:
        if key == name:
            return str(value.decode("latin-1"))
    return None


def _bearer(scope: Scope) -> str | None:
    value = _header(scope, b"authorization")
    if value is None:
        return None
    scheme, _, token = value.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token.startswith(PREFIX) or len(token) > MAX_TOKEN_LENGTH:
        return None
    return token


async def _respond(
    send: Send, status: int, body: dict[str, Any], headers: list[tuple[bytes, bytes]] | None = None
) -> None:
    payload = json.dumps(body).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(payload)).encode()),
                (b"cache-control", b"no-store"),
                *(headers or []),
            ],
        }
    )
    await send({"type": "http.response.body", "body": payload})


class McpGuard:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings
        self.allowed_origins = frozenset(settings.mcp_allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        root = scope.get("root_path", "")
        path = scope["path"]
        relative = path[len(root) :] if root and path.startswith(root) else path
        segment = relative.strip("/")
        if not PUBLIC_ID.match(segment):
            await _respond(send, 404, {"error": "not_found"})
            return
        origin = _header(scope, b"origin")
        if origin is not None and origin not in self.allowed_origins:
            await _respond(send, 403, {"error": "origin_not_allowed"})
            return
        token = _bearer(scope)
        if token is None:
            await self._unauthorized(send)
            return
        tenant = await self._admit(scope, send, token, segment)
        if tenant is None:
            return
        # FastMCP serves a single endpoint at "/": move the public id into the root path.
        inner = dict(scope)
        inner["root_path"] = f"{root}/{segment}"
        inner["path"] = f"{root}/{segment}/"
        inner["raw_path"] = inner["path"].encode()
        state: MutableMapping[str, Any] = dict(scope.get("state") or {})
        state["tenant"] = tenant
        state["sessionmaker"] = scope["app"].state.sessionmaker
        inner["state"] = state
        await self.app(inner, receive, send)

    async def _unauthorized(self, send: Send) -> None:
        await _respond(send, 401, {"error": "unauthorized"}, [(b"www-authenticate", b"Bearer")])

    async def _admit(self, scope: Scope, send: Send, token: str, public_id: str) -> Tenant | None:
        app = scope["app"]
        sessionmaker: async_sessionmaker[AsyncSession] = app.state.sessionmaker
        async with sessionmaker() as session:
            row = (await session.execute(_RESOLVE, {"h": digest_of(token), "p": public_id})).first()
            if row is None:
                await session.rollback()
                await self._unauthorized(send)
                return None
            owner_id, collection_id, token_id = row
            await session.execute(
                text("SELECT set_config('app.owner_id', :o, true)"), {"o": owner_id}
            )
            admission = await admit(
                session,
                token_id,
                owner_id,
                per_minute=self.settings.mcp_rate_per_minute,
                per_day=self.settings.mcp_rate_per_day,
            )
            if not admission.admitted:
                await session.rollback()
                await _respond(
                    send,
                    429,
                    {"error": "rate_limited"},
                    [(b"retry-after", str(admission.retry_after).encode())],
                )
                return None
            # Committed before the tool runs (record 0009), so the count survives a crash or a
            # slow tool and a parallel request sees it.
            await session.commit()
        return Tenant(owner_id, collection_id, token_id, public_id)
