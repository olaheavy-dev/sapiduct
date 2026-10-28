# 0008. Ingestion pipeline and search

Status: Proposed (the owner accepts by merging the pull request; each new dependency needs the owner's approval when its issue is built)

## Context

Users upload PDFs, Word files, Markdown, plain text, HTML and VTT transcripts; Sapiduct must read them safely, split them into cited passages, embed them within a budget, and search them with filtering by collection. Facts as of 2026-10-28:

- The FastAPI layer already provides presigned uploads to S3-compatible storage with an allowed-type list and a signed size limit, a model gateway whose `embeddings()` call runs under the daily budget, PostgreSQL with pgvector 0.8.7 in Compose, and an embedding model default of `openai:text-embedding-3-small` (house-template-fastapi v0.6.1, read 2026-10-28). That model's default vector length is 1,536 and its maximum input is 8,192 tokens ([OpenAI embeddings guide](https://developers.openai.com/api/docs/guides/embeddings)).
- pgvector applies approximate-index filters after the index scan, so a selective filter can return fewer rows than asked for; iterative index scans (0.8.0 and later) keep scanning until enough rows are found; for multitenancy the README recommends list partitioning or separate tables, because a shared approximate index lets one tenant's vectors affect another's recall; `vector` columns can be indexed up to 2,000 dimensions; hybrid search combines Postgres full-text search with vectors, merged for example by Reciprocal Rank Fusion ([pgvector README](https://github.com/pgvector/pgvector)).
- `SELECT ... FOR UPDATE SKIP LOCKED` skips rows that cannot be locked immediately, gives an inconsistent view, and "can be used to avoid lock contention with multiple consumers accessing a queue-like table" ([PostgreSQL 18 SELECT](https://www.postgresql.org/docs/current/sql-select.html)).
- The repository's dependency review accepts only these licences: MIT, MIT-0, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, 0BSD, Zlib, Unlicense, CC0-1.0, CC-BY-4.0, MPL-2.0, BlueOak-1.0.0, Python-2.0 and PSF-2.0 (`.github/workflows/dependency-review.yml`). PyMuPDF is dual-licensed AGPL-3.0 or commercial ([PyPI](https://pypi.org/project/PyMuPDF/)), so it cannot be added.
- On Linux, `/proc/<pid>/environ` holds a process's initial environment, and access to it is decided by a `PTRACE_MODE_READ_FSCREDS` check ([proc_pid_environ(5)](https://man7.org/linux/man-pages/man5/proc_pid_environ.5.html)), so a process cannot rely on scrubbing a child's own environment to keep its own secrets from that child. Compose gives each service only the services it shares a network with, and an `internal: true` network is "externally isolated" ([Compose networks](https://docs.docker.com/reference/compose-file/networks/)); the page does not say in so many words that an internal network blocks all outbound traffic.
- Python's `resource.setrlimit` sets per-process limits (`RLIMIT_AS`, `RLIMIT_CPU`, `RLIMIT_NOFILE`, `RLIMIT_NPROC`) on Unix only, and the module "does not attempt to mask platform differences" ([resource](https://docs.python.org/3/library/resource.html)). Docker Compose offers `read_only`, `cap_drop`, `security_opt` (`no-new-privileges`), `mem_limit`, `pids_limit`, `cpus`, `tmpfs` and `user` for hardening a container ([Compose services](https://docs.docker.com/reference/compose-file/services/)).

## Decision

1. **Upload.** The browser PUTs the file to a presigned URL (type allow-list and size cap enforced by the signature; the maximum is set in record 0009). It then calls a `complete` endpoint, which checks that the object exists with the expected size, creates the document as `queued` and enqueues a job. A file that is too large or of an unsupported type is refused before upload, with the reason shown.
2. **Queue.** A `jobs` table in Postgres: a worker claims one job with `FOR UPDATE SKIP LOCKED`, holds a lease (`locked_until`) and retries with a limited number of attempts and growing delay. Delivery is at least once, so processing is idempotent under the publication rules in decision 10. No queue library or broker is added.
3. **Worker.** The same image run with a different command, as its own container with `read_only`, `cap_drop: [ALL]`, `no-new-privileges`, `mem_limit`, `pids_limit`, `cpus`, a `tmpfs` for scratch space and a non-root `user`. It connects as the worker database role (record 0004) and needs network access only to Postgres, storage, the model gateway and the parser service.
4. **Parsing happens in its own container, the parser service, that holds no credentials.** A child process of the worker would share its user and process namespace, and on Linux a process's initial environment is readable through `/proc/<pid>/environ` under a ptrace-style permission check, so scrubbing the child's own environment does not keep the worker's secrets from a compromised parser. So the parser is a separate service:
   - It sits on a Compose network shared only with the worker, marked `internal: true`, and on no network with Postgres or storage, so it can neither reach the database nor, as far as Compose promises, the outside; the spike (issue #8) **tests** that it cannot reach the database, storage or the internet, because the Compose page does not promise the last one.
   - It has no database URL, keys or tokens in its environment or files. It runs `read_only`, `cap_drop: [ALL]`, `no-new-privileges`, with `mem_limit`, `pids_limit`, `cpus`, a `tmpfs` for scratch space and a non-root `user`, and restarts if it dies.
   - The worker sends it the file's bytes (bounded by the file-size limit in record 0009) and gets back bounded JSON. For each request the service starts a fresh subprocess that sets `RLIMIT_AS`, `RLIMIT_CPU`, `RLIMIT_NOFILE` and `RLIMIT_NPROC` as its first act (the Python docs do not say how a launcher's limits are inherited, so the process sets its own) and enforces a wall-clock timeout.
   - The worker validates the size and schema of the reply before using it. A hostile file can crash or time out the parser; it holds nothing to steal, and its output is checked. The rlimits are enforced on Linux; the supported way to run the worker and parser locally is Compose.
5. **Parsers**, each within the licence allow-list: PDF with `pypdf` (BSD-3-Clause, 6.21.4), Word with `python-docx` (MIT, 1.2.0), VTT with `webvtt-py` (MIT, 0.6.0) and Markdown, plain text (`.txt`) and HTML with small parsers of our own on the standard library (no dependency; HTML drops script, style and navigation content, takes headings from `h1` to `h6` and fetches nothing). A PDF with no text layer fails with the stated reason; optical character recognition is out of scope. The owner approved the three libraries on 2026-10-28; the spike adds them at `pypdf` 6.21.4, `python-docx` 1.2.0 and `webvtt-py` 0.6.0 (the lockfile pins them), and `python-docx` brings `lxml` (BSD-3-Clause).
6. **Chunking** follows the document's structure: Markdown and Word by heading sections (long sections split), PDF by page then paragraph, VTT by groups of cues. Each chunk stores a location (page, heading path or timestamp) for citations and stays well under the embedding model's 8,192-token input. Target size and overlap are set in the spike by measuring retrieval on the open test corpus, not guessed here.
7. **Embeddings** go through `gateway.embeddings()`, so every call is metered and capped. Each chunk stores the model that produced its vector; the column is `vector(1536)` for the default model; changing model is a re-embed job, not an edit.
8. **Search is hybrid and filtered by collection.** A generated `tsvector` column with a GIN index supplies keyword matches; vector distance supplies semantic matches; Reciprocal Rank Fusion merges them. Every query filters by `collection_id`, and row-level security adds the owner.
9. **No vector index at first.** Searches compute exact distances over the collection's own rows, found through an ordinary index on `collection_id`, which avoids the filter-after-scan recall problem. An HNSW index (`vector_cosine_ops`) with `hnsw.iterative_scan` is added only when the measured search time for the largest collection exceeds the budget in record 0010; the pgvector README's partitioning advice is then reconsidered.
10. **Publication, partial availability and re-indexing.** Each document has a `generation` number and a `published_generation`. Chunks are written in batches tagged with the generation being built, with a unique key on `(document_id, generation, position)` so a batch that runs twice does nothing the second time.
   - *First indexing* (there is nothing to replace): each committed batch is published at once, so finished pages are searchable while the document is still parsing, and `pages_done` advances with it. Search shows a document's chunks of its published generation.
   - *Re-indexing* (a retry, or an updated file): the new generation is built hidden. Only when the last batch has committed does one short transaction set `published_generation` to the new generation and delete the old one, so searchers see the old chunks or the new ones, never a mix.
   - *A job that crashes or runs twice:* it resumes from the last committed position of its generation or starts a fresh generation; chunks of an abandoned generation are deleted when the document next reaches `indexed` or `failed`. A first-indexing failure keeps the pages already searchable and marks the document `failed` with the reason, and a retry builds a new generation and swaps as above.
   - Search and the document counts read only `published_generation`; a test covers a first index interrupted halfway, a re-index interrupted halfway, and a batch applied twice.
11. **Failures are per document.** A failed document keeps its reason and a retry; it never blocks the queue. Re-indexing replaces chunks; removing a document deletes its chunks, jobs and stored object.
12. **Document text is data.** Tools return passages with their sources as structured data. Sapiduct cannot stop an assistant from obeying instructions written inside a user's own document, and the connect guides say so.

## Consequences

- No new infrastructure: Postgres is the queue, and the worker is one more container from the same image.
- At-least-once delivery and generation-tagged batches mean a job can run twice without duplicating or mixing chunks; tests cover that.
- A fourth container (the parser service) joins the worker and the API, with its own network and limits.
- Exact search is simple and correct but its time grows with a collection's size; the spike measures it on the 1,284-document sample and sets the threshold for adding HNSW.
- Three parsing libraries (and `lxml`, which `python-docx` needs) are new supply-chain surface; Dependabot and the dependency review already cover them.
- Local development on macOS does not enforce every limit the Linux container does.

## Alternatives considered

- **A separate task-queue system (Celery, RQ, arq):** more features, but a broker or Redis to run and monitor is more than a Postgres table needs for one person. Rejected for now.
- **Procrastinate, a task queue library that uses Postgres (3.10.0, [PyPI](https://pypi.org/project/procrastinate/)):** fits the storage choice, but it is a dependency for something a table and one SQL clause provide; revisit if the queue needs scheduling or priorities.
- **Parsing inside the request:** large files would hold requests open and block workers. Rejected.
- **Parsing in a child process of the credentialed worker:** simpler, but it shares the worker's user and process namespace, so a compromised parser could read the worker's initial environment. Rejected in favour of the parser service.
- **Dropping privileges inside one container** (a different user for the child): possible, but it needs process-level privilege setup the Python and Compose docs read here do not cover. Deferred.
- **PyMuPDF:** strong PDF parsing but AGPL, which the licence allow-list rejects.
- **Broader document converters (Docling 2.144.0, MIT; Unstructured 0.27.35, Apache-2.0, per [PyPI](https://pypi.org/project/docling/)):** both pass the licence list; deferred until formats or scanned PDFs matter, because the four small parsers cover the first build.
- **HNSW from the start:** faster at scale, but filtered approximate search can lose recall and tenancy is exactly the case the README flags.

## Sources

- house-template-fastapi v0.6.1 (storage, model gateway, Compose, embedding default), read 2026-10-28: https://github.com/olaheavy-dev/house-template-fastapi
- OpenAI embeddings guide, read 2026-10-28: https://developers.openai.com/api/docs/guides/embeddings
- pgvector README (0.8.7), read 2026-10-28: https://github.com/pgvector/pgvector
- PostgreSQL 18 documentation, SELECT (locking clause), read 2026-10-28: https://www.postgresql.org/docs/current/sql-select.html
- Python `resource` module (Python 3.15 documentation), read 2026-10-28: https://docs.python.org/3/library/resource.html
- Docker Compose services and networks references, read 2026-10-28: https://docs.docker.com/reference/compose-file/services/, https://docs.docker.com/reference/compose-file/networks/
- Linux `proc_pid_environ(5)`, read 2026-10-28: https://man7.org/linux/man-pages/man5/proc_pid_environ.5.html
- Repository licence allow-list: `.github/workflows/dependency-review.yml`.
- Library releases and licences, read 2026-10-28: https://pypi.org/project/pypdf/, https://pypi.org/project/python-docx/, https://pypi.org/project/webvtt-py/, https://pypi.org/project/PyMuPDF/
