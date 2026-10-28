# 0006. Access tokens for collection servers

Status: Proposed (the owner accepts by merging the pull request)

## Context

An assistant authenticates to one collection's server with a bearer token the user creates, copies once and can rotate or revoke. The MCP authorization specification (revision 2026-07-28) is optional; when an HTTP server supports it, it should follow an OAuth 2.1-based flow with protected-resource metadata, must receive the token in the `Authorization` header on every request (never in the query string), must accept only tokens issued for it, and must answer invalid or expired tokens with 401 ([Authorization, 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization.md), read 2026-10-28). FastMCP's `TokenVerifier` base class has a `verify_token(self, token: str) -> AccessToken | None` method, and a tool can read the authenticated token at call time with `get_access_token()` or `CurrentAccessToken()` ([FastMCP auth module](https://gofastmcp.com/python-sdk/fastmcp-server-auth-auth.md), [dependency injection](https://gofastmcp.com/servers/dependency-injection.md), read 2026-10-28). Python's documentation says 32 bytes (256 bits) of randomness is believed sufficient for typical token use as of 2015 and provides `token_urlsafe` and a constant-time `compare_digest` ([secrets, Python 3.15 docs](https://docs.python.org/3/library/secrets.html), read 2026-10-28).

## Decision

1. **Format.** `sap_` followed by `secrets.token_urlsafe(32)`. The `sap_` prefix lets secret scanners and users recognise it.
2. **Storage.** Only a SHA-256 digest of the token is stored (`token_hash`, unique), plus a short display prefix and the last four characters for the masked view. The plain token is shown once, at creation or rotation, and is never written to logs or the `calls` table.
   - *Reasoning, not from a cited source:* the token is a random 256-bit value, so an attacker cannot guess it from its digest the way they can guess a human password; a slow password hash would add cost to every MCP call without adding protection.
3. **Verification.** A custom `TokenVerifier` hashes the presented token, looks it up by `token_hash` with a constant-time comparison of the result, and returns the token only if it is neither revoked nor past its end of life, **and** the token's collection matches the `public_id` in the URL. It returns nothing otherwise, which FastMCP answers with 401 and a `WWW-Authenticate: Bearer` header. A valid token used against another collection's URL gets the same 401, so a response never reveals that another collection exists.
4. **Per-call lookup, no cache.** Each call does one indexed lookup, so a revocation takes effect on the next call.
5. **Rotation.** Rotating creates a new token and sets the old token's end of life to now plus an overlap period (its length is set in record 0009 and stated in the dialog). Revoking sets the end of life to now.
6. **Header only.** A token in the query string or request body is not read. The configuration snippets and guides use the `Authorization` header only.
7. **Scope.** A token grants the three read-only tools on exactly one collection. It cannot create, change or delete anything, and cannot be used with the web API.
8. **Deviation from the OAuth flow, stated plainly.** These are Sapiduct-issued bearer tokens, not OAuth access tokens: the server publishes no protected-resource metadata and does not run the browser authorization flow. The specification makes authorization optional and says conforming is a SHOULD for HTTP servers, so this is a documented gap, not a claim of conformance. Clients that only support OAuth discovery will not connect; which tested clients accept a static `Authorization` header is recorded per client in the guides (issue #12). Adding OAuth later is possible and is out of scope for the first build.
9. **Last-used tracking.** `last_used_at` is updated at most once per minute per token, to avoid a write on every call.

## Consequences

- The token model is simple and revocable but is not interoperable with OAuth-only clients.
- Losing a token means rotating it; there is no recovery because only the digest is stored.
- One extra indexed lookup per call; the activity write happens after the response.
- A secret scanner pattern for `sap_` is a template-candidate for the repository's secret scanning.

## Alternatives considered

- **OAuth 2.1 with Supabase as the authorization server:** conforms to the specification but needs discovery metadata, dynamic or pre-registered clients and a consent screen. Deferred.
- **JWT access tokens:** verifiable without a database lookup, but revocation would need a deny list and the per-call lookup is cheap. Rejected for now.
- **API keys per user, not per collection:** a leaked key would expose every collection. Rejected.
- **Storing the token encrypted so it can be shown again:** requires key management and widens what a database leak exposes. Rejected.

## Sources

- MCP authorization, revision 2026-07-28, read 2026-10-28: https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization.md
- FastMCP token verification and dependencies (FastMCP 4 documentation), read 2026-10-28: https://gofastmcp.com/python-sdk/fastmcp-server-auth-auth.md, https://gofastmcp.com/servers/auth/token-verification.md, https://gofastmcp.com/servers/dependency-injection.md
- Python `secrets` module (Python 3.15 documentation), read 2026-10-28: https://docs.python.org/3/library/secrets.html
