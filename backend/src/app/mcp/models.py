"""Tables behind a collection's MCP server (records 0004, 0006, 0009).

All three are tenant tables like `collection`: they carry `owner_id`, and the migration enables
and forces row-level security on them. The one lookup that has to happen before the owner is known
(a request carries only a token and a public id) is a SECURITY DEFINER function, see the migration.
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
    LargeBinary,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AccessToken(Base):
    """A bearer token for one collection's server. Only a SHA-256 digest is stored (record 0006)."""

    __tablename__ = "access_token"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column()
    owner_id: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    last4: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Set when the token is retired by a rotation: it works until then. NULL means no end planned.
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    __table_args__ = (
        ForeignKeyConstraint(
            ["collection_id", "owner_id"],
            ["collection.id", "collection.owner_id"],
            name="fk_access_token_collection_owner",
            ondelete="CASCADE",
        ),
        CheckConstraint("octet_length(token_hash) = 32", name="hash_is_sha256"),
        Index("ix_access_token_collection", "collection_id"),
    )


class RateWindow(Base):
    """How many calls a token made in one minute or one UTC day (record 0009)."""

    __tablename__ = "rate_window"

    token_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    span: Mapped[str] = mapped_column(Text, primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text)
    count: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        ForeignKeyConstraint(
            ["token_id"],
            ["access_token.id"],
            name="fk_rate_window_access_token",
            ondelete="CASCADE",
        ),
        CheckConstraint("span IN ('minute', 'day')", name="span"),
        Index("ix_rate_window_start", "window_start"),
    )


class McpCall(Base):
    """One tool call, for the Activity tab. Arguments are capped; secrets are never stored."""

    __tablename__ = "mcp_call"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    collection_id: Mapped[uuid.UUID] = mapped_column()
    owner_id: Mapped[str] = mapped_column(Text)
    token_id: Mapped[uuid.UUID] = mapped_column()
    tool: Mapped[str] = mapped_column(Text)
    arguments: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    latency_ms: Mapped[int] = mapped_column(Integer)
    result_summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ["collection_id", "owner_id"],
            ["collection.id", "collection.owner_id"],
            name="fk_mcp_call_collection_owner",
            ondelete="CASCADE",
        ),
        CheckConstraint("status IN ('ok', 'error')", name="status"),
        Index("ix_mcp_call_collection_created", "collection_id", "created_at", "id"),
    )
