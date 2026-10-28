"""The ingestion queue and worker (record 0008): claiming, failures, re-indexing, crashes.

Everything runs as a login in `sapiduct_worker`, a role that is not a superuser and not
BYPASSRLS, against a real PostgreSQL and a real object store. Seeding uses the superuser.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.collections import Collection, Document
from app.ingest import worker
from app.ingest.models import Chunk, IngestJob
from app.settings import Settings
from app.storage import Storage
from tests.ingest import samples
from tests.tenant.conftest import scoped, seed

pytestmark = pytest.mark.anyio


@pytest.fixture
async def sessions(
    worker_url: str, owner_engine: AsyncEngine
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(worker_url, pool_size=10, max_overflow=10)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def store(storage_settings: Settings) -> Storage:
    return Storage(storage_settings)


def make_settings(storage_settings: Settings, **extra: Any) -> Settings:
    values = {
        "ingest_retry_seconds": 0,
        "ingest_batch_size": 2,
        "ingest_chunk_chars": 200,
        "ingest_chunk_overlap_chars": 20,
    }
    return storage_settings.model_copy(update={**values, **extra})


async def add_document(
    owner_engine: AsyncEngine,
    store: Storage,
    collection: Collection,
    name: str,
    kind: str,
    data: bytes,
    *,
    queue: bool = True,
) -> Document:
    key = f"{collection.owner_id}/{uuid.uuid4().hex}"
    await store.put(key, data, content_type="application/octet-stream")
    async with AsyncSession(owner_engine, expire_on_commit=False) as session:
        document = Document(
            collection_id=collection.id,
            owner_id=collection.owner_id,
            name=name,
            kind=kind,
            size_bytes=len(data),
            object_key=key,
        )
        session.add(document)
        await session.flush()
        if queue:
            await worker.enqueue(session, document)
        await session.commit()
        return document


def long_markdown(label: str, sections: int = 8) -> bytes:
    body = "\n\n".join(
        f"# {label} section {n}\n\n" + " ".join(f"{label}{n}word{w}." for w in range(40))
        for n in range(sections)
    )
    return body.encode()


async def state(owner_engine: AsyncEngine, document: Document) -> dict[str, Any]:
    async with AsyncSession(owner_engine) as session:
        row = (
            await session.execute(
                select(
                    Document.status,
                    Document.failure_reason,
                    Document.generation,
                    Document.published_generation,
                    Document.indexed_at,
                ).where(Document.id == document.id)
            )
        ).one()
        chunks = (
            await session.execute(
                select(Chunk.generation, Chunk.position).where(Chunk.document_id == document.id)
            )
        ).all()
    return {
        "status": row.status,
        "reason": row.failure_reason,
        "generation": row.generation,
        "published": row.published_generation,
        "indexed": row.indexed_at is not None,
        "chunks": [(g, p) for g, p in chunks],
    }


def published(info: dict[str, Any]) -> list[int]:
    """Positions of the chunks search would see: the published generation only."""
    return sorted(p for g, p in info["chunks"] if g == info["published"])


async def test_a_queued_document_is_parsed_chunked_and_published(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
    storage_settings: Settings,
) -> None:
    settings = make_settings(storage_settings)
    collection = await seed(owner_engine, "alice", "Notes")
    document = await add_document(owner_engine, store, collection, "a.md", "md", long_markdown("a"))
    assert await worker.run_once(sessions, store, settings) is True
    info = await state(owner_engine, document)
    assert (info["status"], info["generation"], info["published"]) == ("indexed", 1, 1)
    assert info["indexed"]
    assert info["reason"] is None
    assert published(info) == list(range(len(info["chunks"])))
    assert len(info["chunks"]) > 4
    async with AsyncSession(owner_engine) as session:
        job = await session.scalar(select(IngestJob))
        locations = (await session.scalars(select(Chunk.location).order_by(Chunk.position))).all()
    assert job is not None
    assert job.status == "done"
    assert locations[0].startswith("a section 0")
    assert await worker.run_once(sessions, store, settings) is False


async def test_a_hostile_file_fails_only_its_own_document_and_the_others_still_run(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
    storage_settings: Settings,
) -> None:
    settings = make_settings(storage_settings)
    collection = await seed(owner_engine, "alice", "Notes")
    good_before = await add_document(
        owner_engine, store, collection, "1.md", "md", long_markdown("x")
    )
    corrupt = await add_document(
        owner_engine, store, collection, "bad.pdf", "pdf", b"%PDF-1.4 not really" + bytes(300)
    )
    bomb = await add_document(
        owner_engine, store, collection, "bomb.docx", "docx", samples.zip_bomb(150)
    )
    good_after = await add_document(
        owner_engine, store, collection, "2.txt", "txt", b"plain text\n\nmore of it"
    )
    handled = 0
    while await worker.run_once(sessions, store, settings):
        handled += 1
    assert handled == 4
    states = {
        d.name: await state(owner_engine, d) for d in (good_before, corrupt, bomb, good_after)
    }
    assert states["1.md"]["status"] == "indexed"
    assert states["2.txt"]["status"] == "indexed"
    assert states["bad.pdf"]["status"] == "failed"
    assert states["bad.pdf"]["reason"]
    assert states["bomb.docx"]["status"] == "failed"
    assert "expands past" in states["bomb.docx"]["reason"]
    assert states["bad.pdf"]["chunks"] == []
    assert states["bomb.docx"]["chunks"] == []


async def test_an_oversized_file_fails_with_that_reason(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
    storage_settings: Settings,
) -> None:
    settings = make_settings(storage_settings, ingest_max_file_bytes=100)
    collection = await seed(owner_engine, "alice", "Notes")
    document = await add_document(owner_engine, store, collection, "big.txt", "txt", b"word " * 500)
    await worker.run_once(sessions, store, settings)
    info = await state(owner_engine, document)
    assert (info["status"], info["reason"]) == ("failed", "The file is larger than the limit.")


async def test_a_missing_stored_file_fails_cleanly(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
    storage_settings: Settings,
) -> None:
    collection = await seed(owner_engine, "alice", "Notes")
    document = await add_document(owner_engine, store, collection, "a.txt", "txt", b"hello")
    async with AsyncSession(owner_engine) as session:
        await session.execute(update(Document).values(object_key="alice/does-not-exist"))
        await session.commit()
    await worker.run_once(sessions, store, make_settings(storage_settings))
    assert (await state(owner_engine, document))[
        "reason"
    ] == "The uploaded file could not be found."


async def test_reindexing_replaces_the_chunks_without_duplicates(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
    storage_settings: Settings,
) -> None:
    settings = make_settings(storage_settings)
    collection = await seed(owner_engine, "alice", "Notes")
    document = await add_document(
        owner_engine, store, collection, "a.md", "md", long_markdown("old")
    )
    await worker.run_once(sessions, store, settings)
    before = await state(owner_engine, document)
    await store.put(
        str(document.object_key), long_markdown("new", sections=3), content_type="text/markdown"
    )
    async with AsyncSession(owner_engine) as session:
        assert await worker.enqueue(session, document) is True
        await session.commit()
    await worker.run_once(sessions, store, settings)
    after = await state(owner_engine, document)
    assert (after["generation"], after["published"]) == (2, 2)
    assert {g for g, _ in after["chunks"]} == {2}  # nothing of generation 1 is left
    assert len(after["chunks"]) < len(before["chunks"])
    assert len(set(after["chunks"])) == len(after["chunks"])
    async with AsyncSession(owner_engine) as session:
        texts = " ".join((await session.scalars(select(Chunk.text))).all())
    assert "new" in texts
    assert "old" not in texts


async def test_asking_twice_for_the_same_document_queues_one_job(
    owner_engine: AsyncEngine, store: Storage
) -> None:
    collection = await seed(owner_engine, "alice", "Notes")
    document = await add_document(owner_engine, store, collection, "a.txt", "txt", b"hello")
    async with AsyncSession(owner_engine) as session:
        assert await worker.enqueue(session, document) is False
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(IngestJob)) == 1


class Crash(RuntimeError):
    pass


def crash_after_batches(monkeypatch: pytest.MonkeyPatch, allowed: int) -> None:
    real = worker._write_batch
    calls = {"n": 0}

    async def flaky(*args: Any, **kwargs: Any) -> None:
        calls["n"] += 1
        if calls["n"] > allowed:
            raise Crash("simulated crash with detail that must not be shown")
        await real(*args, **kwargs)

    monkeypatch.setattr(worker, "_write_batch", flaky)


async def test_a_first_index_interrupted_halfway_keeps_the_finished_batches_searchable(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
    storage_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(storage_settings)
    collection = await seed(owner_engine, "alice", "Notes")
    document = await add_document(owner_engine, store, collection, "a.md", "md", long_markdown("a"))
    with monkeypatch.context() as patch:
        crash_after_batches(patch, allowed=1)
        await worker.run_once(sessions, store, settings)
    halfway = await state(owner_engine, document)
    assert halfway["status"] == "queued"
    assert halfway["published"] == 1
    assert published(halfway) == [0, 1]  # the first batch is searchable
    await worker.run_once(sessions, store, settings)  # the retry finishes it
    done = await state(owner_engine, document)
    assert done["status"] == "indexed"
    assert done["published"] == 2
    assert {g for g, _ in done["chunks"]} == {2}
    assert published(done) == list(range(len(done["chunks"])))


async def test_a_reindex_interrupted_halfway_leaves_the_old_text_in_place(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
    storage_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(storage_settings)
    collection = await seed(owner_engine, "alice", "Notes")
    document = await add_document(
        owner_engine, store, collection, "a.md", "md", long_markdown("old")
    )
    await worker.run_once(sessions, store, settings)
    old = await state(owner_engine, document)
    await store.put(str(document.object_key), long_markdown("new"), content_type="text/markdown")
    async with AsyncSession(owner_engine) as session:
        await worker.enqueue(session, document)
        await session.commit()
    with monkeypatch.context() as patch:
        crash_after_batches(patch, allowed=1)
        await worker.run_once(sessions, store, settings)
    halfway = await state(owner_engine, document)
    assert halfway["published"] == 1  # still the old generation
    assert published(halfway) == published(old)  # search sees exactly the old chunks
    assert any(g == 2 for g, _ in halfway["chunks"])  # the new ones are built but hidden
    await worker.run_once(sessions, store, settings)
    done = await state(owner_engine, document)
    assert done["published"] == 3
    assert {g for g, _ in done["chunks"]} == {3}


async def test_a_batch_applied_twice_writes_nothing_the_second_time(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
) -> None:
    from app.ingest.types import Chunk as Parsed

    collection = await seed(owner_engine, "alice", "Notes")
    document = await add_document(owner_engine, store, collection, "a.txt", "txt", b"x")
    job = await worker.claim(sessions, lease=300)
    assert job is not None
    batch = [Parsed(0, "one", "line 1"), Parsed(1, "two", "line 2")]
    await worker._write_batch(sessions, job, 1, batch)
    await worker._write_batch(sessions, job, 1, batch)
    assert len((await state(owner_engine, document))["chunks"]) == 2


async def test_an_unexpected_failure_is_retried_then_given_up_without_leaking_detail(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
    storage_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(storage_settings, ingest_max_attempts=2)
    collection = await seed(owner_engine, "alice", "Notes")
    document = await add_document(owner_engine, store, collection, "a.txt", "txt", b"hello")

    async def broken(*_: Any, **__: Any) -> bytes:
        raise Crash("secret internal detail")

    monkeypatch.setattr(store, "get", broken)
    await worker.run_once(sessions, store, settings)
    assert (await state(owner_engine, document))["status"] == "queued"
    await worker.run_once(sessions, store, settings)
    info = await state(owner_engine, document)
    assert (info["status"], info["reason"]) == ("failed", "Processing failed after several tries.")
    async with AsyncSession(owner_engine) as session:
        job = await session.scalar(select(IngestJob))
    assert job is not None
    assert job.status == "failed"
    assert "secret" not in (job.last_error or "")


async def test_a_job_whose_lease_ran_out_is_taken_again(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
    storage_settings: Settings,
) -> None:
    settings = make_settings(storage_settings)
    collection = await seed(owner_engine, "alice", "Notes")
    document = await add_document(owner_engine, store, collection, "a.txt", "txt", b"hello")
    taken = await worker.claim(sessions, lease=300)  # a worker that then died
    assert taken is not None
    assert await worker.claim(sessions, lease=300) is None  # leased: nobody else may have it
    async with AsyncSession(owner_engine) as session:
        await session.execute(
            update(IngestJob).values(locked_until=func.now() - text("interval '1 second'"))
        )
        await session.commit()
    assert await worker.run_once(sessions, store, settings) is True
    assert (await state(owner_engine, document))["status"] == "indexed"


async def test_a_job_that_keeps_killing_its_worker_is_eventually_failed(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
    storage_settings: Settings,
) -> None:
    settings = make_settings(storage_settings, ingest_max_attempts=2)
    collection = await seed(owner_engine, "alice", "Notes")
    document = await add_document(owner_engine, store, collection, "a.txt", "txt", b"hello")
    for _ in range(2):  # two workers claim it and die without reporting
        assert await worker.claim(sessions, lease=300) is not None
        async with AsyncSession(owner_engine) as session:
            await session.execute(
                update(IngestJob).values(locked_until=func.now() - text("interval '1 second'"))
            )
            await session.commit()
    await worker.run_once(sessions, store, settings)  # third claim: past the limit
    info = await state(owner_engine, document)
    assert (info["status"], info["reason"]) == (
        "failed",
        "Processing was interrupted too many times.",
    )


async def test_parallel_workers_each_take_a_different_job_exactly_once(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
    storage_settings: Settings,
) -> None:
    settings = make_settings(storage_settings)
    collection = await seed(owner_engine, "alice", "Notes")
    documents = [
        await add_document(owner_engine, store, collection, f"{n}.md", "md", long_markdown(f"d{n}"))
        for n in range(8)
    ]
    results = await asyncio.gather(*(worker.run_once(sessions, store, settings) for _ in range(12)))
    assert results.count(True) == 8
    assert results.count(False) == 4
    async with AsyncSession(owner_engine) as session:
        attempts = (await session.scalars(select(IngestJob.attempts))).all()
    assert attempts == [1] * 8
    for document in documents:
        info = await state(owner_engine, document)
        assert info["status"] == "indexed"
        assert len(set(info["chunks"])) == len(info["chunks"])


async def test_chunks_belong_to_the_right_owner_and_stay_invisible_to_others(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
    storage_settings: Settings,
) -> None:
    settings = make_settings(storage_settings)
    alices = await seed(owner_engine, "alice", "Alice notes")
    bobs = await seed(owner_engine, "bob", "Bob notes")
    await add_document(owner_engine, store, alices, "a.md", "md", long_markdown("a"))
    await add_document(owner_engine, store, bobs, "b.md", "md", long_markdown("b"))
    while await worker.run_once(sessions, store, settings):
        pass
    async with scoped(sessions.kw["bind"], "alice") as session:
        owners = set((await session.scalars(select(Chunk.owner_id))).all())
        text_seen = " ".join((await session.scalars(select(Chunk.text))).all())
    assert owners == {"alice"}
    assert "b0word0" not in text_seen
    assert "a0word0" in text_seen


async def test_only_the_worker_role_may_claim_jobs(
    owner_engine: AsyncEngine, api_url: str, store: Storage
) -> None:
    collection = await seed(owner_engine, "alice", "Notes")
    await add_document(owner_engine, store, collection, "a.txt", "txt", b"hello")
    engine = create_async_engine(api_url)
    try:
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        with pytest.raises(DBAPIError, match="permission denied"):
            await worker.claim(sessionmaker, lease=300)
    finally:
        await engine.dispose()


async def test_the_error_noted_on_a_retried_job_is_only_its_type(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
    storage_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collection = await seed(owner_engine, "alice", "Notes")
    await add_document(owner_engine, store, collection, "a.txt", "txt", b"hello")

    async def broken(*_: Any, **__: Any) -> bytes:
        raise Crash("secret internal detail")

    monkeypatch.setattr(store, "get", broken)
    await worker.run_once(sessions, store, make_settings(storage_settings))
    async with AsyncSession(owner_engine) as session:
        job = await session.scalar(select(IngestJob))
    assert job is not None
    assert job.status == "queued"
    assert job.last_error == "Crash"


async def test_a_first_index_that_finally_fails_keeps_what_was_already_searchable(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
    storage_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(storage_settings, ingest_max_attempts=1)
    collection = await seed(owner_engine, "alice", "Notes")
    document = await add_document(owner_engine, store, collection, "a.md", "md", long_markdown("a"))
    crash_after_batches(monkeypatch, allowed=1)
    await worker.run_once(sessions, store, settings)
    info = await state(owner_engine, document)
    assert info["status"] == "failed"
    assert published(info) == [0, 1]  # the finished batch stays searchable
    assert len(info["chunks"]) == 2  # nothing else is left over


async def test_a_reindex_that_finally_fails_keeps_the_old_text_and_drops_the_hidden_build(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
    storage_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(storage_settings, ingest_max_attempts=1)
    collection = await seed(owner_engine, "alice", "Notes")
    document = await add_document(
        owner_engine, store, collection, "a.md", "md", long_markdown("old")
    )
    await worker.run_once(sessions, store, settings)
    old = await state(owner_engine, document)
    async with AsyncSession(owner_engine) as session:
        await worker.enqueue(session, document)
        await session.commit()
    crash_after_batches(monkeypatch, allowed=1)
    await worker.run_once(sessions, store, settings)
    info = await state(owner_engine, document)
    assert info["status"] == "failed"
    assert sorted(info["chunks"]) == sorted(old["chunks"])


async def test_many_workers_claiming_at_once_never_miss_or_double_a_job(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
) -> None:
    collection = await seed(owner_engine, "alice", "Notes")
    for n in range(20):
        await add_document(owner_engine, store, collection, f"{n}.txt", "txt", b"hello")
    claims = await asyncio.gather(*(worker.claim(sessions, lease=300) for _ in range(20)))
    assert all(c is not None for c in claims)  # a claimer blocked on a locked row would get None
    assert len({c.job_id for c in claims if c}) == 20


async def test_a_claim_does_not_wait_behind_a_job_another_worker_has_locked(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
) -> None:
    collection = await seed(owner_engine, "alice", "Notes")
    first = await add_document(owner_engine, store, collection, "1.txt", "txt", b"one")
    second = await add_document(owner_engine, store, collection, "2.txt", "txt", b"two")
    async with AsyncSession(owner_engine) as holder:
        # Another worker is mid-claim on the oldest job: its row is locked and uncommitted.
        await holder.execute(
            text("SELECT id FROM ingest_job WHERE document_id = :d FOR UPDATE"),
            {"d": first.id},
        )
        taken = await asyncio.wait_for(worker.claim(sessions, lease=300), timeout=5)
        await holder.rollback()
    assert taken is not None
    assert taken.document_id == second.id


async def test_a_worker_that_lost_its_claim_can_change_nothing(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
    storage_settings: Settings,
) -> None:
    from app.ingest.types import Chunk as Parsed

    settings = make_settings(storage_settings)
    collection = await seed(owner_engine, "alice", "Notes")
    document = await add_document(owner_engine, store, collection, "a.md", "md", long_markdown("a"))
    slow = await worker.claim(sessions, lease=300)
    assert slow is not None
    assert await worker._start(sessions, slow, settings) is not None  # generation 1, then it stalls
    async with AsyncSession(owner_engine) as session:
        await session.execute(
            update(IngestJob).values(locked_until=func.now() - text("interval '1 second'"))
        )
        await session.commit()
    await worker.run_once(sessions, store, settings)  # another worker finishes the job
    done = await state(owner_engine, document)
    assert (done["status"], done["generation"], done["published"]) == ("indexed", 2, 2)

    stale = [
        worker._start(sessions, slow, settings),
        worker._write_batch(sessions, slow, 1, [Parsed(0, "stale", "p. 1")]),
        worker._finish(sessions, slow, 1),
        worker._give_up(sessions, slow, "stale failure"),
        worker._retry(sessions, slow, settings, "Crash"),
    ]
    for attempt in stale:
        with pytest.raises(worker.LeaseLost):
            await attempt
    assert await state(owner_engine, document) == done  # not one row changed


async def test_a_stale_worker_found_out_midway_stops_quietly(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
    storage_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(storage_settings)
    collection = await seed(owner_engine, "alice", "Notes")
    document = await add_document(owner_engine, store, collection, "a.md", "md", long_markdown("a"))

    async def takeover(*_: Any, **__: Any) -> None:
        async with AsyncSession(owner_engine) as session:  # someone else took the job
            await session.execute(update(IngestJob).values(attempts=IngestJob.attempts + 1))
            await session.commit()
        raise worker.LeaseLost

    monkeypatch.setattr(worker, "_write_batch", takeover)
    assert await worker.run_once(sessions, store, settings) is True
    info = await state(owner_engine, document)
    assert info["status"] == "parsing"  # untouched by the stale worker's error handling


async def test_a_retry_of_a_partial_first_index_keeps_the_earlier_batches_searchable(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
    storage_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(storage_settings)
    collection = await seed(owner_engine, "alice", "Notes")
    document = await add_document(owner_engine, store, collection, "a.md", "md", long_markdown("a"))
    with monkeypatch.context() as patch:
        crash_after_batches(patch, allowed=1)
        await worker.run_once(sessions, store, settings)
    first = await state(owner_engine, document)
    assert published(first) == [0, 1]

    # The retry fails before writing anything: the earlier batches must still be there.
    async def unreadable(*_: Any, **__: Any) -> bytes:
        raise Crash("storage down")

    with monkeypatch.context() as patch:
        patch.setattr(store, "get", unreadable)
        await worker.run_once(sessions, store, settings)
    retried = await state(owner_engine, document)
    assert retried["published"] == first["published"]
    assert published(retried) == [0, 1]

    await worker.run_once(sessions, store, settings)  # a good retry replaces them at the end
    done = await state(owner_engine, document)
    assert done["status"] == "indexed"
    assert {g for g, _ in done["chunks"]} == {done["published"]}
    assert published(done) == list(range(len(done["chunks"])))


async def test_a_stale_worker_is_stopped_while_the_new_one_is_still_running(
    owner_engine: AsyncEngine,
    sessions: async_sessionmaker[AsyncSession],
    store: Storage,
    storage_settings: Settings,
) -> None:
    from app.ingest.types import Chunk as Parsed

    settings = make_settings(storage_settings)
    collection = await seed(owner_engine, "alice", "Notes")
    await add_document(owner_engine, store, collection, "a.md", "md", long_markdown("a"))
    slow = await worker.claim(sessions, lease=300)
    assert slow is not None
    async with AsyncSession(owner_engine) as session:
        await session.execute(
            update(IngestJob).values(locked_until=func.now() - text("interval '1 second'"))
        )
        await session.commit()
    current = await worker.claim(sessions, lease=300)  # the job is "running" again, attempt 2
    assert current is not None
    assert (slow.attempts, current.attempts) == (1, 2)
    with pytest.raises(worker.LeaseLost):
        await worker._finish(sessions, slow, 1)
    with pytest.raises(worker.LeaseLost):
        await worker._write_batch(sessions, slow, 1, [Parsed(0, "stale", "p. 1")])
    await worker._write_batch(sessions, current, 1, [Parsed(0, "fresh", "p. 1")])  # allowed
    assert await worker._start(sessions, current, settings) is not None
