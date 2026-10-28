"""Tenant scoping: the session every owned-data route uses.

Record 0004: isolation has two layers. This module is the database layer's hook: every
transaction a scoped session begins first sets `app.owner_id`, which the row-level-security
policies on the tenant tables compare with each row's `owner_id`. `set_config(..., true)` lasts
only for the current transaction (PostgreSQL docs, System Administration Functions), so a pooled
connection never carries one user's id into another request's transaction, and a transaction
that never sets it matches no rows because `current_setting(name, true)` is then NULL.

The other layer is in the queries themselves (app/collections.py filters on owner_id), so a
mistake in either is not enough to show one user another's data.

The connection must use a role that is neither a superuser nor BYPASSRLS, or the policies do
nothing (PostgreSQL docs, Row Security Policies). See migrations for `sapiduct_api`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, SessionTransaction

from app.auth import CurrentUser

OWNER_SETTING = "app.owner_id"


def bind_owner(session: AsyncSession, owner_id: str) -> None:
    """Make every transaction this session begins carry `owner_id` for the policies.

    Registered on the sync session, which is where SQLAlchemy documents events for AsyncSession.
    The statement goes through the connection SQLAlchemy hands the hook, not through the session
    (SQLAlchemy's docs warn the session is mid-update while the event runs).
    """

    @event.listens_for(session.sync_session, "after_begin")
    def _set_owner(_: Session, __: SessionTransaction, connection: Connection) -> None:
        connection.execute(
            text("SELECT set_config(:setting, :owner, true)"),
            {"setting": OWNER_SETTING, "owner": owner_id},
        )


async def owner_session(request: Request, user: CurrentUser) -> AsyncIterator[AsyncSession]:
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with sessionmaker() as session:
        bind_owner(session, user.id)
        yield session


OwnerSessionDep = Annotated[AsyncSession, Depends(owner_session)]
