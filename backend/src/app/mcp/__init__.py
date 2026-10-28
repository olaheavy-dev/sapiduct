"""MCP servers for collections (records 0005, 0006, 0009).

`build_mcp(settings)` returns the guarded ASGI app to mount at `settings.mcp_path_prefix` and the
lifespan FastMCP needs, which `create_app` combines with its own.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Any

from starlette.types import ASGIApp

from app.mcp.guard import McpGuard
from app.mcp.server import build_server
from app.settings import Settings


@dataclass(frozen=True, slots=True)
class Mcp:
    asgi: ASGIApp
    lifespan: Callable[[Any], AbstractAsyncContextManager[Any]]


def build_mcp(settings: Settings) -> Mcp:
    server = build_server(settings)
    # Stateless: no session ids, so any worker answers any request. JSON responses, not streams:
    # none of the tools streams, so no long-lived connection is held open per call. FastMCP's own
    # host and origin protection is off because the guard checks Origin (and the app's trusted
    # hosts check Host) before anything reaches it.
    inner = server.http_app(
        path="/", stateless_http=True, json_response=True, host_origin_protection=False
    )
    return Mcp(asgi=McpGuard(inner, settings), lifespan=inner.lifespan)
