# 0009. Limits, abuse controls and retention

Status: Proposed (the owner accepts by merging the pull request; the numbers are the owner's to change, and the model-spend caps are a running cost)

## Context

Anyone with a GitHub or Google account can sign in, upload files and create tokens, so every resource needs a ceiling, and every ceiling needs a number. Facts as of 2026-10-28:

- The FastAPI layer meters every model and embedding call against a daily budget, `LLM_DAILY_BUDGET_USD` (default 5), with an optional per-user budget, `LLM_USER_DAILY_BUDGET_USD`; uploads are limited by `STORAGE_MAX_UPLOAD_BYTES` and an allowed-type list; agent loops stop after `AGENT_MAX_STEPS` (default 25); ordinary request bodies are capped at 1 MiB (`backend/src/app/settings.py`, `limits.py`, `storage.py`, house-template-fastapi v0.6.1).
- The template's price table lists `openai:text-embedding-3-small` at 0.02 US dollars per million input tokens, checked on 27 October 2026 (`backend/src/app/llm/prices.py`).
- Supabase Pro is from $25 a month and Free projects pause after a week of inactivity ([Pricing](https://supabase.com/pricing), read 2026-10-28; record 0007).
- Records 0004 to 0008 leave these numbers open: maximum documents per collection, upload size, page-size maximums, the token rotation overlap, the activity retention period and the per-token rate.

## Decision

Every number below is a **setting with this default**, read from configuration and never hard-coded; the interface shows the ones a user can run into. They are proposals sized for a one-person service and are meant to be revised from measurement.

| Limit | Default | Reason |
| --- | --- | --- |
| Collections per user | 10 | Bounds one account's footprint; the owner can raise it per user later. |
| Documents per collection | 2,000 | Above the 1,284-document prototype sample, so the large-collection design has room; the spike (issue #8) measures search at this size. |
| File size | 25 MB | The figure the prototype shows; bounds parse time and memory. |
| Pages per PDF | 1,000 | Above the 842-page example in the prototype. |
| File types | PDF, Word (.docx), Markdown, VTT | The four parsers in record 0008. |
| Stored bytes per user | 1 GB | Bounds storage cost per account. |
| Documents being processed at once, per user | 3 | One user's batch cannot starve everyone else's queue. |
| Queued jobs per user | 500 | Bounds a flood; a larger batch is added in parts. |
| Parser child | 120 s wall clock, 1 GiB address space, 90 s CPU | Applied by the child in record 0008. |
| Token rotation overlap | 1 hour | Long enough to update a client's config, short enough to retire a leaked token. |
| Active tokens per collection | 1, plus the old one during the overlap | The prototype shows one token. |
| MCP calls per token | 60 per minute and 10,000 per day, answered with HTTP 429 and a `Retry-After` header | Keeps a runaway assistant loop from hammering the database. |
| Tool results | `search` at most 10 (default 5); `list_sources` at most 25 (default 10); `get_document` at most 20,000 characters per call, with an offset to continue | Keeps results within an assistant's context. |
| Activity retention | 30 days, deleted daily; stored arguments capped at 1 KB | Matches the prototype's sample and bounds the `calls` table. |
| Playground chat (issue #24) | 20 messages and 0.25 US dollars per user per day, one message per two seconds, 5 model steps per message | Spends the template's per-user budget; built last and needs the owner's approval. |
| Demo collection (read-only, no sign-in) | 20 calls per minute per client address | An unauthenticated surface needs its own limit. |

**How the per-token rate is admitted, atomically.** Counting rows in `calls` cannot enforce a ceiling when workers run in parallel: several can each see 59 calls and admit a 60th before any new row is visible. So admission is one atomic statement per window against a small counter table, `rate_windows(token_id, owner_id, window, window_start, count)` with a unique key on `(token_id, window, window_start)`, and a row-level-security policy like the other tenant tables (record 0004):

```sql
INSERT INTO rate_windows (token_id, owner_id, window, window_start, count)
VALUES (:token, :owner, :window, :start, 1)
ON CONFLICT (token_id, window, window_start)
DO UPDATE SET count = rate_windows.count + 1 WHERE rate_windows.count < :limit
RETURNING count;
```

PostgreSQL guarantees an atomic insert-or-update outcome for `ON CONFLICT DO UPDATE`, even under high concurrency, and `RETURNING` yields a row only when one was inserted or updated, so no returned row means the limit is reached ([PostgreSQL 18 INSERT](https://www.postgresql.org/docs/current/sql-insert.html), read 2026-10-28). The day window is admitted first, then the minute window, in one short transaction that is **committed before the tool runs**; if either returns no row the transaction is rolled back, so a rejected call leaves both counters unchanged, and the answer is HTTP 429 with `Retry-After` set to the seconds until that window ends. Fixed windows allow a burst of up to twice the minute limit across a window boundary; that is accepted for a ceiling meant to stop runaway loops, not to meter usage. Old rows are deleted daily, so the table stays small and rate limiting does not depend on the activity table or its retention. Issue #7's spike must include a test that fires many concurrent requests at one token and shows that exactly the limit is admitted.

The per-address demo limit uses the same table keyed by client address, and needs the real client address from the reverse proxy; the header to trust is configured and tested in issue #16, since trusting the wrong one lets anyone spoof it.

**Embedding spend.** At 0.02 dollars per million tokens, a full 2,000-document collection averaging 10,000 tokens per document (an assumption to check in the spike) is 20 million tokens, about 0.40 dollars. Embedding shares the template's daily budget, so an upload burst stops at the cap; documents then wait as `queued` with a message that indexing resumes when the budget resets.

**Running cost the owner approves with this record:** Supabase Pro from $25 a month once real users arrive (record 0007); embeddings at the figures above; chat capped by `LLM_DAILY_BUDGET_USD` (worst case that setting times 30 days, 150 dollars at the template default of 5, which the owner may lower); the existing server for everything else.

## Consequences

- A user can hit a limit, so each one has a plain message and appears in the interface where it applies (the prototype's upload dialog already shows the size limit).
- 429s from the per-token limit are visible in Activity as errors with their own reason.
- Admission costs one short transaction with one or two upserts per MCP call; the spike (issue #7) measures it against the search budget in record 0010.
- Nothing here sets prices or plans for users; a paid tier is a separate decision.

## Alternatives considered

- **In-memory counters per worker:** cheap but inconsistent across workers and reset by a restart.
- **Counting recent rows in `calls`:** simple, but concurrent requests can all admit a call at the same count, so it cannot enforce a ceiling. Rejected.
- **Redis for rate limiting:** accurate and fast, at the price of a service to run. Deferred.
- **No per-token limit:** a looping assistant could generate thousands of database queries a minute. Rejected.
- **Unlimited retention:** unbounded growth of `calls`. Rejected.

## Spike findings (issue #7)

- The `rate_window` counter was tested with 12 simultaneous calls against a limit of 5: exactly 5 were admitted and 7 answered 429 with `Retry-After`.
- The column is named `span`, not `window`, because `window` is a reserved word in PostgreSQL.

## Sources

- house-template-fastapi v0.6.1 settings, upload limits and price table, read 2026-10-28: `backend/src/app/settings.py`, `backend/src/app/limits.py`, `backend/src/app/storage.py`, `backend/src/app/llm/prices.py`, https://github.com/olaheavy-dev/house-template-fastapi
- Supabase pricing, read 2026-10-28: https://supabase.com/pricing
- PostgreSQL 18 documentation, INSERT (`ON CONFLICT DO UPDATE`, `RETURNING`), read 2026-10-28: https://www.postgresql.org/docs/current/sql-insert.html
- The design prototype's sample figures: `.design/sapiduct/prototype/index.html` and `.design/sapiduct/DESIGN_REVIEW.md`.
