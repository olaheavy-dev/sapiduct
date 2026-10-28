# 0004. Data model and tenant isolation

Status: Proposed (the owner accepts by merging the pull request)

## Context

Every user owns many collections; each collection has exactly one MCP server; each collection has documents, which are split into passages that tools search. One deployment serves every user, so one mistake in one query could show a user another user's documents. The first spike (issue #6) exists to prove this cannot happen.

Facts that shape the choice:

- The backend gives each request one `AsyncSession` that commits explicitly, on one connection pool, with Alembic migrations on two branches (the template's and the project's) ([`backend/src/app/db.py`](../../backend/src/app/db.py), read 2026-10-28).
- PostgreSQL row-level security (RLS) denies all access by default once enabled, applies to ordinary roles, and is bypassed by superusers, roles with `BYPASSRLS` and, unless `FORCE ROW LEVEL SECURITY` is set, by the table's owner. Policies that consult other tables can leak under concurrent access, so row-local policy expressions are preferred ([PostgreSQL 18 docs, 5.9 Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html), read 2026-10-28, PostgreSQL 18.6).
- Sign-in is by GitHub or Google through Supabase Auth, so a user is identified by the id in the verified token and Sapiduct needs no users table of its own (record 0007, to follow).

## Decision

1. **Tables.** Each tenant table carries `owner_id` (the signed-in user's id) directly, even where it could be derived through a join, so policies depend only on the row itself:
   - `collections`: `id` (uuid), `owner_id`, `name`, `mode` (`knowledge` or `course`), `public_id` (the random, unguessable id used in the MCP URL), timestamps. A user's collection names are unique per user.
   - `documents`: `id`, `collection_id`, `owner_id`, `name`, `kind`, `size_bytes`, `status` (`queued`, `parsing`, `indexed`, `failed`), `failure_reason`, `pages_total`, `pages_done`, `storage_key`, `content_hash`, timestamps.
   - `chunks`: `id`, `document_id`, `collection_id`, `owner_id`, `position`, `text`, `location` (page or timestamp), a text-search vector and the embedding (record 0008).
   - `access_tokens`: see record 0006.
   - `calls` (activity): `id`, `collection_id`, `owner_id`, `token_id`, `tool`, `arguments` (capped), `status`, `latency_ms`, `result_summary`, `created_at`.
   - `jobs` (ingestion queue): see record 0008.
2. **Two layers of isolation, both tested.**
   - *Application layer:* every query goes through helpers that take the owner id and filter on it; there is no query path without it.
   - *Database layer:* RLS is enabled **and forced** on every tenant table, with one policy per table, `owner_id = current_setting('app.owner_id', true)::uuid`, for both `USING` and `WITH CHECK`. The application role is neither a superuser nor `BYPASSRLS`. `current_setting(name, true)` returns NULL when the setting is missing, so a forgotten setting matches no rows and fails closed ([PostgreSQL 18 docs, 9.28 System Administration Functions](https://www.postgresql.org/docs/current/functions-admin.html)).
3. **How the owner is set.** The owner id is set for the transaction, not the connection (`set_config(name, value, true)` applies only during the current transaction, per the same page), so a pooled connection never carries one user's id to another request. The mechanism that re-applies it after each commit is chosen in the tenant-isolation spike (issue #6); the requirement is a test that fails if any statement runs without it.
4. **The MCP path uses the same layers.** After a token is verified (record 0006), the server sets the owner id from the token's collection and filters on that collection as well.
5. **Pagination.** Every list is keyset-paginated on `(created_at desc, id desc)` with a cursor, through the template's `Page[T]` helper; totals and status counts come from the database, not from the page being shown.
6. **Deletion.** Deleting a collection deletes its documents, chunks, tokens, activity, jobs and stored files in one transaction plus a storage cleanup job; deleting an account does the same for every collection. A foreign key with `ON DELETE CASCADE` carries the database part.

## Consequences

- A cross-tenant test suite is part of the definition of done for issue #6: user B cannot read, list, change or delete user A's rows through any endpoint or MCP tool, and the tests fail when either layer is removed.
- Policies stay row-local, which avoids the sub-select race the PostgreSQL docs warn about, at the cost of repeating `owner_id` on child tables.
- Migrations and the application must connect as different roles from the table owner, or tables must be forced; the spike verifies which this repository's Compose and production setup gives.
- RLS does not protect truncation or referential-integrity checks (the PostgreSQL docs say both bypass it), so deletes by cascade are tested explicitly.

## Alternatives considered

- **Application-level scoping only:** simplest, but one forgotten filter is a data leak. Rejected as the only layer.
- **RLS only:** removes the forgotten-filter risk but makes every mistake in the setting mechanism a silent empty result. Rejected as the only layer.
- **One schema or database per user:** strong isolation, but migrations, pooling and cost grow with the number of users. Rejected for a solo-run service.
- **Policies that join to `collections` for ownership:** avoids the repeated column, but the docs warn about races with sub-selects. Rejected.

## Sources

- PostgreSQL 18 documentation, Row Security Policies (PostgreSQL 18.6), read 2026-10-28: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- This repository's database session code, read 2026-10-28: `backend/src/app/db.py` (house-template-fastapi v0.6.1).
- PostgreSQL 18 documentation, System Administration Functions (`current_setting`, `set_config`), read 2026-10-28: https://www.postgresql.org/docs/current/functions-admin.html
- Template pagination (`Page[T]`, limits 1 to 100): `house-template-fastapi` README, read 2026-10-28: https://github.com/olaheavy-dev/house-template-fastapi
