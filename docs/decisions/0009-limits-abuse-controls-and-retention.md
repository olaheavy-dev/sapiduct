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

**How the per-token rate is counted.** By counting the token's own rows in `calls` for the last minute and the last day, using an index on `(token_id, created_at)`. This needs no cache or broker and is correct across workers; the cost is one indexed count per call, which the spike (issue #7) measures. The per-address demo limit needs the real client address from the reverse proxy; the header to trust is configured and tested in issue #16, since trusting the wrong one lets anyone spoof it.

**Embedding spend.** At 0.02 dollars per million tokens, a full 2,000-document collection averaging 10,000 tokens per document (an assumption to check in the spike) is 20 million tokens, about 0.40 dollars. Embedding shares the template's daily budget, so an upload burst stops at the cap; documents then wait as `queued` with a message that indexing resumes when the budget resets.

**Running cost the owner approves with this record:** Supabase Pro from $25 a month once real users arrive (record 0007); embeddings at the figures above; chat capped by `LLM_DAILY_BUDGET_USD` (worst case that setting times 30 days, 150 dollars at the template default of 5, which the owner may lower); the existing server for everything else.

## Consequences

- A user can hit a limit, so each one has a plain message and appears in the interface where it applies (the prototype's upload dialog already shows the size limit).
- 429s from the per-token limit are visible in Activity as errors with their own reason.
- Counting `calls` rows couples rate limiting to the activity table and its retention; the retention job must not delete rows younger than the daily window.
- Nothing here sets prices or plans for users; a paid tier is a separate decision.

## Alternatives considered

- **In-memory counters per worker:** cheap but inconsistent across workers and reset by a restart.
- **Redis for rate limiting:** accurate and fast, at the price of a service to run. Deferred.
- **No per-token limit:** a looping assistant could generate thousands of database queries a minute. Rejected.
- **Unlimited retention:** unbounded growth of `calls`. Rejected.

## Sources

- house-template-fastapi v0.6.1 settings, upload limits and price table, read 2026-10-28: `backend/src/app/settings.py`, `backend/src/app/limits.py`, `backend/src/app/storage.py`, `backend/src/app/llm/prices.py`, https://github.com/olaheavy-dev/house-template-fastapi
- Supabase pricing, read 2026-10-28: https://supabase.com/pricing
- The design prototype's sample figures: `.design/sapiduct/prototype/index.html` and `.design/sapiduct/DESIGN_REVIEW.md`.
