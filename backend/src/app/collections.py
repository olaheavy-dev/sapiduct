"""Collections and their documents: the first tenant tables (record 0004).

Every row carries `owner_id`. The queries below always filter on it (the application layer), and
the migration turns forced row-level security on for both tables (the database layer). A document
can only point at a collection with the same owner: the composite foreign key makes the database
refuse anything else, whatever the application does.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

MODES = ("knowledge", "course")
STATUSES = ("queued", "parsing", "indexed", "failed")


def new_public_id() -> str:
    """The unguessable id in a collection's MCP URL: 16 URL-safe characters, 96 random bits."""
    return secrets.token_urlsafe(12)


class Collection(Base):
    __tablename__ = "collection"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(Text, server_default="knowledge")
    public_id: Mapped[str] = mapped_column(Text, unique=True, default=new_public_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # What the documents' composite foreign key points at: a collection id only together
        # with its owner.
        UniqueConstraint("id", "owner_id", name="uq_collection_id_owner"),
        CheckConstraint("mode IN ('knowledge', 'course')", name="mode"),
        CheckConstraint("length(btrim(name)) >= 3", name="name"),
        Index("uq_collection_owner_name", "owner_id", func.lower(name), unique=True),
    )


class Document(Base):
    __tablename__ = "document"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column()
    owner_id: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(Text, server_default="queued")
    failure_reason: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["collection_id", "owner_id"],
            ["collection.id", "collection.owner_id"],
            name="fk_document_collection_owner",
            ondelete="CASCADE",
        ),
        CheckConstraint("status IN ('queued', 'parsing', 'indexed', 'failed')", name="status"),
        Index("ix_document_collection_created", "collection_id", "created_at", "id"),
    )
