# 0005. Serve MCP with FastMCP, stateless, on its own host

Status: Proposed (the owner accepts by merging the pull request; the host name needs the owner's approval because it changes infrastructure)

## Context

Each collection needs a hosted MCP server that real clients (Claude Desktop, Cursor and similar) can call with a token, and that scales without sticky sessions. Facts as of 2026-10-28:

- FastMCP is at 4.1.4 (released 2026-10-26); 4.1.3 was released 2026-10-20 ([PyPI](https://pypi.org/project/fastmcp/)). It builds on the MCP Python SDK v2 (2.3.0 on 2026-10-02) ([PyPI](https://pypi.org/project/mcp/)). Its documentation says unversioned pages describe FastMCP 4 and `/v3/` pages FastMCP 3 ([FastMCP: AI-assisted development](https://gofastmcp.com/getting-started/ai-assisted-development.md)).
- FastMCP 4 states that one server negotiates both protocol eras per connection, the older handshake era and the newer sessionless one, and that sessionless connections can be answered by any replica behind an ordinary load balancer ([What's new in FastMCP 4](https://gofastmcp.com/getting-started/whats-new.md)).
- The MCP specification revision 2026-07-28 removed protocol sessions and the GET stream from Streamable HTTP; every request is its own POST, carries `MCP-Protocol-Version`, `Mcp-Method` and `Mcp-Name` headers that servers must check against the body, and servers must validate the `Origin` header and answer an invalid one with 403 ([Streamable HTTP, 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md)). Authorization is optional; HTTP implementations that support it should conform to the authorization specification ([Authorization, 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization.md)). The site lists revisions 2026-07-28, 2025-11-25, 2025-06-18, 2025-03-26 and 2024-11-05, plus a draft ([modelcontextprotocol.io](https://modelcontextprotocol.io/llms.txt)).
- FastMCP mounts inside FastAPI with `mcp.http_app(path=...)`, passing `mcp_app.lifespan` (or `combine_lifespans` when the app has its own) to FastAPI; an application-wide `CORSMiddleware` can break OAuth discovery routes; authentication is off unless a provider is passed ([FastAPI integration](https://gofastmcp.com/integrations/fastapi.md), [Authentication](https://gofastmcp.com/servers/auth/authentication.md)).
- The web app's `/api/*` proxy deliberately drops `Authorization` and cookies ([`frontend/src/lib/api/proxy.ts`](../../frontend/src/lib/api/proxy.ts)), so MCP traffic cannot go through it.

## Decision

1. **FastMCP 4 runs inside the existing FastAPI process**, mounted with `http_app`, with the lifespans combined. One process means one deployment, one database pool and the same logging, tracing and budget code as the rest of the API.
2. **Pin an exact version.** `fastmcp` is added at an exact version (and its transitive `mcp` and `fastmcp-slim` versions follow from it). The spike (issue #7) picks the newest 4.x release that is at least a week old on the day it starts, reads that version's release notes, and records the choice in the pull request. Dependabot may propose updates; they are reviewed like any change.
3. **Stateless, and both protocol eras accepted.** The server runs stateless HTTP, so any worker can answer any request, and accepts handshake-era clients too, since FastMCP 4 does that from one server and many clients in use will not have moved to the newest revision yet. The record for the guides (issue #12) lists which era each tested client used.
4. **The MCP URL is on its own host**, `mcp.<product host>` (for example `mcp.sapiduct.olaheavy.dev`), with the path `/<public_id>`. The reverse proxy sends that host straight to the API container. This keeps the web proxy out of the path, keeps MCP's cross-origin policy separate from the web app's, and lets rate limits and access logs be read per host. **The alternative, a `/mcp/*` path on the web host routed by the reverse proxy, is equivalent in function; the host is chosen for isolation.** The prototype shows the path form and changes to match when this is accepted.
5. **Origin validation.** The server rejects a request whose `Origin` header is present and not on an allowlist with 403, as the specification requires. Requests with no `Origin` (typical for desktop clients) pass to token authentication. The allowlist starts with the web app's origin; whether a browser-based tester such as MCPJam's hosted app calls servers directly from the browser (and so needs to be listed) is not confirmed and is checked in issue #7.
6. **Bounded results.** Each tool has a stated maximum result size: `search` takes a `limit` up to a maximum, `list_sources` takes `limit` and `cursor` and returns the total and a next cursor, and `get_document` returns at most a stated number of characters with a continuation offset. The numbers are set in record 0009. A tool never returns an unbounded list.
7. **Read-only tools.** `search`, `get_document` and `list_sources` read only; none of them changes or deletes anything.
8. **Every call is recorded** in the `calls` table (record 0004) after the response is sent, with arguments capped in size, so the Activity tab and the limits both read one source.
9. **Authentication** is described in record 0006. FastMCP's own token-verification layer is given a custom verifier that looks tokens up in the database.

## Consequences

- The API process serves two kinds of traffic; a heavy tool call and a web request share a pool. The limits record sets timeouts and per-token limits.
- A new host name needs DNS and a certificate in the infrastructure repository, which is owner-only.
- The FastMCP 4 line is two weeks old at its newest minor, so the pin and the release-note check matter.
- Mounting under a path and OAuth discovery routes interact in FastMCP; because tokens are not OAuth (record 0006), that does not apply now, but it must be re-read before OAuth is added.
- The prototype's `/mcp/<id>` URLs, the guides and the IA's routing note change when this record is accepted.

## Alternatives considered

- **A separate MCP service:** isolates load, but a second deployment, a second database pool and duplicated auth code are heavy for one person.
- **The official `mcp` SDK alone:** fewer dependencies, but FastMCP supplies the authentication hooks, FastAPI mounting and both protocol eras that this service needs, and it is built on that SDK.
- **A path on the web host:** see decision 4.
- **Session-based (handshake-only) server:** needs sticky sessions or shared session state. Rejected.

## Sources

- FastMCP releases and requirements, read 2026-10-28: https://pypi.org/project/fastmcp/ and https://pypi.org/project/mcp/
- FastMCP documentation (FastMCP 4), read 2026-10-28: https://gofastmcp.com/getting-started/whats-new.md, https://gofastmcp.com/integrations/fastapi.md, https://gofastmcp.com/servers/auth/authentication.md, https://gofastmcp.com/getting-started/ai-assisted-development.md
- MCP specification 2026-07-28, read 2026-10-28: https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http.md, https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization.md, https://modelcontextprotocol.io/llms.txt
- This repository's web proxy, read 2026-10-28: `frontend/src/lib/api/proxy.ts`.
