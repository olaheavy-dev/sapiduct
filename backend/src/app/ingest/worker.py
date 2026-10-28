"""The ingestion worker: claim a job, parse the document, write its chunks (record 0008).

`run_once` handles at most one job. Delivery is at least once (a job whose lease runs out is
claimed again), so every step is safe to repeat: chunks are written under a generation number with
a unique key per position, and search reads only the published generation.

- *First indexing:* the new generation is published as soon as it starts, so finished batches are
  searchable while the rest is still being written.
- *Re-indexing:* the new generation is built hidden, and one transaction publishes it and deletes
  the old chunks, so a searcher sees the old text or the new, never a mix.
- *A failed document* keeps its reason and never blocks the queue: a file that cannot be read
  fails at once (retrying cannot help); an unexpected error is retried with a growing delay, then
  fails. Chunks of an abandoned generation are deleted when the document next settles.

Parsing runs in a thread here. Record 0008 moves it to the credential-free parser service; that
needs a Compose change the owner has not approved yet, so the worker calls `_parse_and_chunk`
in-process for now.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.collections import Document
from app.ingest.chunking import chunk
from app.ingest.models import Chunk, IngestJob
from app.ingest.parsers import parse
from app.ingest.types import Chunk as ParsedChunk
from app.ingest.types import Limits, ParseError
from app.settings import Settings
from app.storage import ObjectNotFound, Storage
from app.tenancy import bind_owner

log = structlog.get_logger()

_CLAIM = text(
    "SELECT job_id, owner_id, document_id, collection_id, attempts FROM claim_ingest_job(:lease)"
)
_LIVE = text("status IN ('queued', 'running')")


@dataclass(frozen=True, slots=True)
class Claimed:
    job_id: uuid.UUID
    owner_id: str
    document_id: uuid.UUID
    collection_id: uuid.UUID
    attempts: int  # also the claim's fencing token: each claim of a job adds one
    lease_seconds: int = 300


class LeaseLost(Exception):
    """This worker's claim was taken over (its lease ran out and another worker claimed the job).
    It must stop at once and write nothing more."""


async def _hold(session: AsyncSession, job: Claimed) -> None:
    """Fence a transaction to this worker's claim, and renew the lease.

    The update matches only the job's current claim (running, and the attempt number this worker
    was given). It also locks the row until the transaction ends, so nobody can claim the job
    between this check and the writes that follow. A worker that lost its claim matches nothing
    and stops (PostgreSQL docs, UPDATE and explicit row locks).
    """
    held = await session.scalar(
        update(IngestJob)
        .where(
            IngestJob.id == job.job_id,
            IngestJob.status == "running",
            IngestJob.attempts == job.attempts,
        )
        .values(locked_until=func.now() + func.make_interval(0, 0, 0, 0, 0, 0, job.lease_seconds))
        .returning(IngestJob.id)
    )
    if held is None:
        raise LeaseLost


async def enqueue(session: AsyncSession, document: Document) -> bool:
    """Ask for a document to be (re)indexed. False when a job for it is already waiting."""
    inserted = await session.scalar(
        pg_insert(IngestJob)
        .values(
            id=uuid.uuid4(),
            document_id=document.id,
            collection_id=document.collection_id,
            owner_id=document.owner_id,
        )
        .on_conflict_do_nothing(index_elements=["document_id"], index_where=_LIVE)
        .returning(IngestJob.id)
    )
    return inserted is not None


async def claim(sessionmaker: async_sessionmaker[AsyncSession], lease: int) -> Claimed | None:
    async with sessionmaker() as session:
        row = (await session.execute(_CLAIM, {"lease": lease})).first()
        await session.commit()
    if row is None:
        return None
    return Claimed(row[0], row[1], row[2], row[3], row[4], lease_seconds=lease)


def _parse_and_chunk(kind: str, data: bytes, settings: Settings) -> list[ParsedChunk]:
    limits = Limits(max_pages=settings.ingest_max_pages, max_chars=settings.ingest_max_chars)
    return chunk(
        parse(kind, data, limits),
        target_chars=settings.ingest_chunk_chars,
        overlap_chars=settings.ingest_chunk_overlap_chars,
    )


async def _write_batch(
    sessionmaker: async_sessionmaker[AsyncSession],
    job: Claimed,
    generation: int,
    batch: list[ParsedChunk],
) -> None:
    async with sessionmaker() as session:
        bind_owner(session, job.owner_id)
        await _hold(session, job)
        await session.execute(
            pg_insert(Chunk)
            .values(
                [
                    {
                        "id": uuid.uuid4(),
                        "document_id": job.document_id,
                        "collection_id": job.collection_id,
                        "owner_id": job.owner_id,
                        "generation": generation,
                        "position": c.position,
                        "text": c.text,
                        "location": c.location,
                    }
                    for c in batch
                ]
            )
            .on_conflict_do_nothing(constraint="uq_chunk_position")
        )
        await session.commit()


async def _start(
    sessionmaker: async_sessionmaker[AsyncSession], job: Claimed, settings: Settings
) -> tuple[str, str, int] | None:
    """Open a new generation. Returns (object key, kind, generation), or None if the document is
    gone."""
    async with sessionmaker() as session:
        bind_owner(session, job.owner_id)
        await _hold(session, job)
        doc = await session.scalar(
            select(Document).where(
                Document.id == job.document_id, Document.owner_id == job.owner_id
            )
        )
        if doc is None:
            await session.execute(
                update(IngestJob).where(IngestJob.id == job.job_id).values(status="done")
            )
            await session.commit()
            return None
        if job.attempts > settings.ingest_max_attempts:
            raise ParseError("Processing was interrupted too many times.")
        if doc.object_key is None:
            raise ParseError("The uploaded file could not be found.")
        generation = doc.generation + 1
        doc.generation = generation
        doc.status = "parsing"
        doc.failure_reason = None
        if doc.published_generation == 0:
            # Nothing is searchable yet: publish the new generation at once so finished batches
            # can be found. Anything already published (a finished index, or the finished
            # batches of an earlier attempt) stays until the new generation replaces it.
            doc.published_generation = generation
            await session.execute(
                delete(Chunk).where(Chunk.document_id == doc.id, Chunk.generation != generation)
            )
        result = (doc.object_key, doc.kind, generation)
        await session.commit()
    return result


async def _finish(
    sessionmaker: async_sessionmaker[AsyncSession], job: Claimed, generation: int
) -> None:
    """Publish the generation, drop every other one, and close the job: one transaction."""
    async with sessionmaker() as session:
        bind_owner(session, job.owner_id)
        await _hold(session, job)
        await session.execute(
            update(Document)
            .where(Document.id == job.document_id)
            .values(
                published_generation=generation,
                status="indexed",
                failure_reason=None,
                indexed_at=func.coalesce(Document.indexed_at, func.now()),
            )
        )
        await session.execute(
            delete(Chunk).where(
                Chunk.document_id == job.document_id, Chunk.generation != generation
            )
        )
        await session.execute(
            update(IngestJob)
            .where(IngestJob.id == job.job_id)
            .values(status="done", locked_until=None)
        )
        await session.commit()


async def _give_up(
    sessionmaker: async_sessionmaker[AsyncSession], job: Claimed, reason: str
) -> None:
    async with sessionmaker() as session:
        bind_owner(session, job.owner_id)
        await _hold(session, job)
        published = (
            select(Document.published_generation)
            .where(Document.id == job.document_id)
            .scalar_subquery()
        )
        await session.execute(
            update(Document)
            .where(Document.id == job.document_id)
            .values(status="failed", failure_reason=reason)
        )
        # Keep what is searchable (a partial first index, or the old text of a failed re-index);
        # drop the rest.
        await session.execute(
            delete(Chunk).where(Chunk.document_id == job.document_id, Chunk.generation != published)
        )
        await session.execute(
            update(IngestJob)
            .where(IngestJob.id == job.job_id)
            .values(status="failed", last_error=reason, locked_until=None)
        )
        await session.commit()


async def _retry(
    sessionmaker: async_sessionmaker[AsyncSession],
    job: Claimed,
    settings: Settings,
    error_name: str,
) -> None:
    if job.attempts >= settings.ingest_max_attempts:
        await _give_up(sessionmaker, job, "Processing failed after several tries.")
        return
    async with sessionmaker() as session:
        bind_owner(session, job.owner_id)
        await _hold(session, job)
        await session.execute(
            update(Document).where(Document.id == job.document_id).values(status="queued")
        )
        await session.execute(
            update(IngestJob)
            .where(IngestJob.id == job.job_id)
            .values(
                status="queued",
                locked_until=None,
                last_error=error_name,
                run_after=func.now()
                + func.make_interval(
                    0, 0, 0, 0, 0, 0, job.attempts * settings.ingest_retry_seconds
                ),
            )
        )
        await session.commit()


async def _process(
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: Storage,
    settings: Settings,
    job: Claimed,
) -> None:
    started = await _start(sessionmaker, job, settings)
    if started is None:
        return
    key, kind, generation = started
    try:
        data = await storage.get(key)
    except ObjectNotFound:
        raise ParseError("The uploaded file could not be found.") from None
    if len(data) > settings.ingest_max_file_bytes:
        raise ParseError("The file is larger than the limit.")
    chunks = await asyncio.to_thread(_parse_and_chunk, kind, data, settings)
    size = settings.ingest_batch_size
    for first in range(0, len(chunks), size):
        await _write_batch(sessionmaker, job, generation, chunks[first : first + size])
    await _finish(sessionmaker, job, generation)


async def run_once(
    sessionmaker: async_sessionmaker[AsyncSession], storage: Storage, settings: Settings
) -> bool:
    """Handle at most one job. True when there was one, whatever became of it."""
    job = await claim(sessionmaker, settings.ingest_lease_seconds)
    if job is None:
        return False
    try:
        try:
            await _process(sessionmaker, storage, settings, job)
        except ParseError as error:
            await _give_up(sessionmaker, job, str(error))
        except LeaseLost:
            raise
        except Exception as error:
            log.warning("ingest_job_failed", job_id=str(job.job_id), error=type(error).__name__)
            await _retry(sessionmaker, job, settings, type(error).__name__)
    except LeaseLost:
        # Another worker owns the job now; whatever it does is what counts.
        log.warning("ingest_lease_lost", job_id=str(job.job_id))
    return True
