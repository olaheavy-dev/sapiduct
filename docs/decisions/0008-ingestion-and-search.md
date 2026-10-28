# 0008. Ingestion pipeline and search

Status: Proposed (the owner accepts by merging the pull request; each new dependency needs the owner's approval when its issue is built)

## Context

Users upload PDFs, Word files, Markdown and VTT transcripts; Sapiduct must read them safely, split them into cited passages, embed them within a budget, and search them with filtering by collection. Facts as of 2026-10-28:

- The FastAPI layer already provides presigned uploads to S3-compatible storage with an allowed-type list and a signed size limit, a model gateway whose `embeddings()` call runs under the daily budget, PostgreSQL with pgvector 0.8.7 in Compose, and an embedding model default of `openai:text-embedding-3-small` (house-template-fastapi v0.6.1, read 2026-10-28). That model's default vector length is 1,536 and its maximum input is 8,192 tokens ([OpenAI embeddings guide](https://developers.openai.com/api/docs/guides/embeddings)).
- pgvector applies approximate-index filters after the index scan, so a selective filter can return fewer rows than asked for; iterative index scans (0.8.0 and later) keep scanning until enough rows are found; for multitenancy the README recommends list partitioning or separate tables, because a shared approximate index lets one tenant's vectors affect another's recall; `vector` columns can be indexed up to 2,000 dimensions; hybrid search combines Postgres full-text search with vectors, merged for example by Reciprocal Rank Fusion ([pgvector README](https://github.com/pgvector/pgvector)).
- `SELECT ... FOR UPDATE SKIP LOCKED` skips rows that cannot be locked immediately, gives an inconsistent view, and "can be used to avoid lock contention with multiple consumers accessing a queue-like table" ([PostgreSQL 18 SELECT](https://www.postgresql.org/docs/current/sql-select.html)).
- The repository's dependency review accepts only these licences: MIT, MIT-0, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, 0BSD, Zlib, Unlicense, CC0-1.0, CC-BY-4.0, MPL-2.0, BlueOak-1.0.0, Python-2.0 and PSF-2.0 (`.github/workflows/dependency-review.yml`). PyMuPDF is dual-licensed AGPL-3.0 or commercial ([PyPI](https://pypi.org/project/PyMuPDF/)), so it cannot be added.
- Python's `resource.setrlimit` sets per-process limits (`RLIMIT_AS`, `RLIMIT_CPU`, `RLIMIT_NOFILE`, `RLIMIT_NPROC`) on Unix only, and the module "does not attempt to mask platform differences" ([resource](https://docs.python.org/3/library/resource.html)). Docker Compose offers `read_only`, `cap_drop`, `security_opt` (`no-new-privileges`), `mem_limit`, `pids_limit`, `cpus`, `tmpfs` and `user` for hardening a container ([Compose services](https://docs.docker.com/reference/compose-file/services/)).

## Decision

1. **Upload.** The browser PUTs the file to a presigned URL (type allow-list and size cap enforced by the signature; the maximum is set in record 0009). It then calls a `complete` endpoint, which checks that the object exists with the expected size, creates the document as `queued` and enqueues a job. A file that is too large or of an unsupported type is refused before upload, with the reason shown.
2. **Queue.** A `jobs` table in Postgres: a worker claims one job with `FOR UPDATE SKIP LOCKED`, holds a lease (`locked_until`) and retries with a limited number of attempts and growing delay. Delivery is at least once, so processing is idempotent: it replaces the document's chunks in one transaction. No queue library or broker is added.
3. **Worker.** The same image run with a different command, as its own container with `read_only`, `cap_drop: [ALL]`, `no-new-privileges`, `mem_limit`, `pids_limit`, `cpus`, a `tmpfs` for scratch space and a non-root `user`. It connects as the worker database role (record 0004) and needs network access only to Postgres, storage and the model gateway.
4. **Parsing happens in a child process that holds no secrets.** The worker starts `python -m app.parse_child` with a scrubbed environment (no database URL, no keys), a wall-clock timeout, and the file path as its only input. The child's first act is to set `RLIMIT_AS`, `RLIMIT_CPU`, `RLIMIT_NOFILE` and `RLIMIT_NPROC` itself, so no limit depends on how a launcher inherits them (the Python docs do not say), then parses and writes bounded JSON to stdout. The parent validates the size and schema of that output before using it. A hostile file can crash or time out the child; it cannot reach the database credentials. The rlimits are enforced on Linux; the supported way to run the worker locally is the Compose service.
5. **Parsers**, each within the licence allow-list: PDF with `pypdf` (BSD-3-Clause, 6.21.4), Word with `python-docx` (MIT, 1.2.0), VTT with `webvtt-py` (MIT, 0.6.0) and Markdown with a small heading splitter of our own (no dependency). A PDF with no text layer fails with the stated reason; optical character recognition is out of scope. Exact versions are pinned in the spike (issue #8), each one needing the owner's approval.
6. **Chunking** follows the document's structure: Markdown and Word by heading sections (long sections split), PDF by page then paragraph, VTT by groups of cues. Each chunk stores a location (page, heading path or timestamp) for citations and stays well under the embedding model's 8,192-token input. Target size and overlap are set in the spike by measuring retrieval on the open test corpus, not guessed here.
7. **Embeddings** go through `gateway.embeddings()`, so every call is metered and capped. Each chunk stores the model that produced its vector; the column is `vector(1536)` for the default model; changing model is a re-embed job, not an edit.
8. **Search is hybrid and filtered by collection.** A generated `tsvector` column with a GIN index supplies keyword matches; vector distance supplies semantic matches; Reciprocal Rank Fusion merges them. Every query filters by `collection_id`, and row-level security adds the owner.
9. **No vector index at first.** Searches compute exact distances over the collection's own rows, found through an ordinary index on `collection_id`, which avoids the filter-after-scan recall problem. An HNSW index (`vector_cosine_ops`) with `hnsw.iterative_scan` is added only when the measured search time for the largest collection exceeds the budget in record 0010; the pgvector README's partitioning advice is then reconsidered.
10. **Progress and partial availability.** The worker commits chunks in batches and updates `pages_done`, so a large document's finished pages are searchable while it is still parsing, as the prototype shows.
11. **Failures are per document.** A failed document keeps its reason and a retry; it never blocks the queue. Re-indexing replaces chunks; removing a document deletes its chunks, jobs and stored object.
12. **Document text is data.** Tools return passages with their sources as structured data. Sapiduct cannot stop an assistant from obeying instructions written inside a user's own document, and the connect guides say so.

## Consequences

- No new infrastructure: Postgres is the queue, and the worker is one more container from the same image.
- At-least-once delivery and idempotent replacement mean a job can run twice; tests cover that.
- Exact search is simple and correct but its time grows with a collection's size; the spike measures it on the 1,284-document sample and sets the threshold for adding HNSW.
- Four parsing dependencies are new supply-chain surface; Dependabot and the dependency review already cover them.
- Local development on macOS does not enforce every limit the Linux container does.

## Alternatives considered

- **Celery, RQ or arq with Redis:** more features, plus a broker to run. Rejected for now.
- **Procrastinate (Postgres-based queue library):** fits, but it is a dependency for something a table and one SQL clause provide; revisit if the queue needs scheduling or priorities.
- **Parsing inside the request:** large files would hold requests open and block workers. Rejected.
- **PyMuPDF:** strong PDF parsing but AGPL, which the licence allow-list rejects.
- **Heavier document converters (such as Docling or Unstructured):** broader format support and optical character recognition, at the price of large dependency trees and models. Deferred.
- **HNSW from the start:** faster at scale, but filtered approximate search can lose recall and tenancy is exactly the case the README flags.

## Sources

- house-template-fastapi v0.6.1 (storage, model gateway, Compose, embedding default), read 2026-10-28: https://github.com/olaheavy-dev/house-template-fastapi
- OpenAI embeddings guide, read 2026-10-28: https://developers.openai.com/api/docs/guides/embeddings
- pgvector README (0.8.7), read 2026-10-28: https://github.com/pgvector/pgvector
- PostgreSQL 18 documentation, SELECT (locking clause), read 2026-10-28: https://www.postgresql.org/docs/current/sql-select.html
- Python `resource` module (Python 3.15 documentation), read 2026-10-28: https://docs.python.org/3/library/resource.html
- Docker Compose services reference, read 2026-10-28: https://docs.docker.com/reference/compose-file/services/
- Repository licence allow-list: `.github/workflows/dependency-review.yml`.
- Library releases and licences, read 2026-10-28: https://pypi.org/project/pypdf/, https://pypi.org/project/python-docx/, https://pypi.org/project/webvtt-py/, https://pypi.org/project/PyMuPDF/
