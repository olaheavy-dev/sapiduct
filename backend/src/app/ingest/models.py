"""Tables behind ingestion (record 0008): the chunks of a document and the queue of jobs.

Both are tenant tables like `document`: `owner_id` on every row, forced row-level security, and a
composite foreign key that makes the database refuse a chunk or job whose collection or owner does
not match its document's. Chunks are written under a generation number and search reads only the
document's published generation, so a re-index swaps old chunks for new in one transaction.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

JOB_STATUSES = ("queued", "running", "done", "failed")


class Chunk(Base):
    __tablename__ = "chunk"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column()
    collection_id: Mapped[uuid.UUID] = mapped_column()
    owner_id: Mapped[str] = mapped_column(Text)
    generation: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "collection_id", "owner_id"],
            ["document.id", "document.collection_id", "document.owner_id"],
            name="fk_chunk_document",
            ondelete="CASCADE",
        ),
        # A batch applied twice writes nothing the second time (record 0008, decision 10).
        UniqueConstraint("document_id", "generation", "position", name="uq_chunk_position"),
        Index("ix_chunk_collection", "collection_id"),
    )


class IngestJob(Base):
    __tablename__ = "ingest_job"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column()
    collection_id: Mapped[uuid.UUID] = mapped_column()
    owner_id: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["document_id", "collection_id", "owner_id"],
            ["document.id", "document.collection_id", "document.owner_id"],
            name="fk_ingest_job_document",
            ondelete="CASCADE",
        ),
        CheckConstraint("status IN ('queued', 'running', 'done', 'failed')", name="status"),
        # One live job per document: asking twice for the same document changes nothing.
        Index(
            "uq_ingest_job_live",
            "document_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
        Index(
            "ix_ingest_job_due",
            "run_after",
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )
