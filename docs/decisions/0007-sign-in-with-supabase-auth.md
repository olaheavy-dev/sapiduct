# 0007. Sign in with GitHub or Google through Supabase Auth

Status: Proposed (the owner accepts by merging the pull request; the paid plan is a running cost and needs the owner's approval)

## Context

The owner decided on 2026-10-28 that sign-in is GitHub or Google only, with no email-and-password. Facts as of 2026-10-28:

- Supabase Auth lists GitHub and Google among its social providers ([Social login](https://supabase.com/docs/guides/auth/social-login.md)). GitHub needs an OAuth app whose callback URL is `https://<project-ref>.supabase.co/auth/v1/callback`; Google needs a web OAuth client with the same callback as its redirect URI, and its scopes are `openid` plus the email and profile scopes added by default ([GitHub](https://supabase.com/docs/guides/auth/social-login/auth-github.md), [Google](https://supabase.com/docs/guides/auth/social-login/auth-google.md)). A server-side or PKCE flow needs a callback route that exchanges the code for a session, and a `redirectTo` URL on the redirect allow list (GitHub page).
- The Free plan includes social OAuth providers and 50,000 monthly active users, and free projects are paused after one week of inactivity; Pro is from $25 a month, includes 100,000 monthly active users, and is never paused for inactivity ([Pricing](https://supabase.com/pricing)).
- To verify a token on a backend, fetch the public keys from `<issuer>/.well-known/jwks.json`, match the token's `kid` and `alg`, and check `exp`, `iss` and `sub`; the endpoint returns no keys unless the project uses asymmetric signing keys; verifying locally with the legacy shared secret is strongly discouraged; keys should not be cached in an application for longer than about ten minutes ([JWTs](https://supabase.com/docs/guides/auth/jwts.md)).
- The token carries `aud` (`authenticated` for signed-in users), `role`, `sub`, `is_anonymous`, `app_metadata` and an `amr` list whose entries have a `method` such as `oauth` or `password` ([JWT fields](https://supabase.com/docs/guides/auth/jwt-fields.md)). The page does not say that `app_metadata.provider` is a guaranteed indicator of the sign-in provider.
- A new OAuth sign-in is linked to an existing user with the same email automatically; Supabase avoids linking to an unverified email because it enables pre-account takeover; manual linking is beta and must be enabled ([Identity linking](https://supabase.com/docs/guides/auth/auth-identity-linking.md)).
- The pages read do **not** say how to switch the email provider off, which GitHub scopes are requested or what happens when a GitHub user has no public or verified email, or the Google consent screen's publishing status and test-user limits.

## Decision

1. **Providers:** GitHub and Google through a hosted Supabase project. The sign-in page offers those two buttons and nothing else.
2. **Plan:** development runs on the Free plan; before any real user is invited the project moves to Pro, because a paused project cannot sign anyone in. The running cost (from $25 a month) is the owner's decision. Self-hosting Supabase Auth is not chosen now: it adds an operated service for one person.
3. **Verification in the backend.** The API verifies the access token locally with the project's JWKS, accepting a signed token only when the project uses asymmetric signing keys. It checks signature, `exp`, `iss` (equal to the configured project issuer), `aud` equal to `authenticated`, `is_anonymous` false and a UUID `sub`, which becomes `owner_id` (record 0004). Keys are cached for at most ten minutes, with a way to purge the cache. A new dependency for JWT verification (PyJWT with its crypto extra, MIT, version 2.15.1 on 2026-09-28 on PyPI) needs the owner's approval, and `authenticate()` keeps failing closed without a valid token.
4. **GitHub or Google only, enforced in Sapiduct and not only in the dashboard.** Because the docs read here do not say how to turn email sign-in off, the backend refuses a token unless its `amr` list contains a method `oauth` and the provider is GitHub or Google. How to read the provider reliably (`app_metadata.provider`, `amr`, or another claim) is **not established by the documentation**; the auth issue (#9) must prove it with real tokens from each provider, including after a token refresh, and records the result before this check is relied on.
5. **Identity linking:** rely on Supabase's automatic linking by verified email and never turn on linking to unverified emails. Manual linking (beta) stays off, so the prototype's "Link Google" button is not built in the first version.
6. **Callback and redirects.** The web app has `/auth/callback`, which exchanges the code for a session using PKCE; `?next=` accepts same-site paths only; the redirect allow list contains the production and local origins and nothing else.
7. **Session to API.** The web app keeps the session on the server side of Next.js and attaches the access token to API calls through the existing proxy hook (`backendCredentials`); the browser never sends the token to the API itself.
8. **What Sapiduct stores about a person:** the owner id only. Name, avatar and email are read from the token for display and not copied into the database.
9. **Account deletion** removes the user's data first (record 0004), then asks Supabase to delete the user with a server-held admin credential, which never reaches the browser or the repository. The exact admin call is read from the docs in issue #9.
10. **Failure states:** a cancelled or failed provider sign-in returns to `/sign-in` with a message naming the provider.

## Consequences

- Sign-in depends on a hosted service and a monthly fee once real users arrive; if the project is paused or down, nobody can sign in, though MCP calls (which use Sapiduct's own tokens, record 0006) keep working.
- Two OAuth apps (GitHub, Google) and their secrets exist outside the repository; the Google consent screen may need verification before the public can use it (the page warns extra scopes can trigger it), which the issue checks.
- The provider check in decision 4 is a risk until the spike proves it; if no claim is reliable, the fallback is to ask Supabase's Auth server to validate the token (`GET /auth/v1/user`) and read the identities, at the cost of a network call per request.

## Alternatives considered

- **Keycloak, self-hosted:** full control and OAuth for MCP clients later, but a heavy service to run and upgrade for one person.
- **A hosted auth product with prebuilt components:** quick to ship, but the owner wants designed auth pages.
- **Our own email-and-password:** security-critical code to maintain for little gain, and the owner chose provider sign-in.
- **Email sign-in left on in Supabase:** blocked in the backend by decision 4, but a user could still create a Supabase account directly; turning the provider off is preferred if the docs show how.

## Sources

- Supabase documentation, read 2026-10-28: https://supabase.com/docs/guides/auth/social-login.md, https://supabase.com/docs/guides/auth/social-login/auth-github.md, https://supabase.com/docs/guides/auth/social-login/auth-google.md, https://supabase.com/docs/guides/auth/jwts.md, https://supabase.com/docs/guides/auth/jwt-fields.md, https://supabase.com/docs/guides/auth/auth-identity-linking.md, https://supabase.com/docs/guides/auth/auth-email.md
- Supabase pricing (Free and Pro plans), read 2026-10-28: https://supabase.com/pricing
- PyJWT release and licence, read 2026-10-28: https://pypi.org/project/PyJWT/
- This repository's sign-in hook (`backendCredentials`) and API proxy, read 2026-10-28: `frontend/src/lib/auth.ts`, `frontend/src/lib/api/proxy.ts`.
