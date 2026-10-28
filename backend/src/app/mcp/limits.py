"""Per-token rate limits, admitted atomically (record 0009).

Counting recent rows cannot hold a ceiling when workers run in parallel: several can each see 59
and admit a 60th. So each window is one counter row and admission is one statement, an upsert
whose WHERE clause refuses to go past the limit. PostgreSQL guarantees an atomic insert-or-update
for ON CONFLICT DO UPDATE even under high concurrency, and RETURNING yields a row only when one was
inserted or updated, so no row back means the limit is reached (PostgreSQL docs, INSERT).

The caller runs `admit` in a short transaction, commits it before the tool runs, and rolls it back
when a window refuses, so a refused call leaves both counters as they were.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_ADMIT = text(
    """
    INSERT INTO rate_window (token_id, owner_id, span, window_start, count)
    VALUES (:token, :owner, :span, date_trunc(:unit, now(), 'UTC'), 1)
    ON CONFLICT (token_id, span, window_start)
    DO UPDATE SET count = rate_window.count + 1 WHERE rate_window.count < :limit
    RETURNING count
    """
)


@dataclass(frozen=True, slots=True)
class Admission:
    admitted: bool
    retry_after: int = 0


def seconds_until_window_ends(span: str, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    if span == "minute":
        end = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    else:
        end = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return max(1, int((end - now).total_seconds()) + 1)


async def admit(
    session: AsyncSession, token_id: uuid.UUID, owner_id: str, *, per_minute: int, per_day: int
) -> Admission:
    """Count this call against the day, then the minute. The caller commits or rolls back."""
    for span, unit, limit in (("day", "day", per_day), ("minute", "minute", per_minute)):
        row = await session.execute(
            _ADMIT,
            {"token": token_id, "owner": owner_id, "span": span, "unit": unit, "limit": limit},
        )
        if row.first() is None:
            return Admission(False, seconds_until_window_ends(span))
    return Admission(True)
