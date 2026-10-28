"""A collection's access tokens: create or rotate, list, revoke (record 0006).

The plain token is returned once, in the response that creates it, and never again. A collection
has at most two active tokens: the current one and, for the overlap after a rotation, the old one.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, or_, select, tuple_

from app.api.pagination import Page, PageParamsDep, page
from app.auth import CurrentUser
from app.collections import Collection
from app.mcp.models import AccessToken
from app.mcp.tokens import new_token
from app.problems import Problem
from app.settings import Settings
from app.tenancy import OwnerSessionDep

router = APIRouter(prefix="/collections/{collection_id}/tokens", tags=["tokens"])

MAX_ACTIVE = 2


class TokenInfo(BaseModel):
    id: uuid.UUID
    last4: str
    created_at: datetime
    last_used_at: datetime | None
    ends_at: datetime | None
    revoked_at: datetime | None


class TokenCreated(TokenInfo):
    token: str


def _info(row: AccessToken) -> TokenInfo:
    return TokenInfo.model_validate(row, from_attributes=True)


def _active(collection_id: uuid.UUID, owner_id: str):  # type: ignore[no-untyped-def]
    return (
        AccessToken.collection_id == collection_id,
        AccessToken.owner_id == owner_id,
        AccessToken.revoked_at.is_(None),
        or_(AccessToken.ends_at.is_(None), AccessToken.ends_at > func.now()),
    )


async def _owned_collection(
    session: OwnerSessionDep, owner_id: str, collection_id: uuid.UUID, *, lock: bool = False
) -> Collection:
    query = select(Collection).where(
        Collection.id == collection_id, Collection.owner_id == owner_id
    )
    row = await session.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise Problem(404, detail="No such collection.")
    return row


@router.post("", status_code=201)
async def create_token(
    collection_id: uuid.UUID, request: Request, user: CurrentUser, session: OwnerSessionDep
) -> TokenCreated:
    settings: Settings = request.app.state.settings
    # Locking the collection row serialises two simultaneous rotations, so neither can step past
    # the limit on active tokens.
    await _owned_collection(session, user.id, collection_id, lock=True)
    active = (
        await session.scalars(select(AccessToken).where(*_active(collection_id, user.id)))
    ).all()
    if len(active) >= MAX_ACTIVE:
        raise Problem(409, detail="Two tokens are already active. Revoke one first.")
    overlap = timedelta(seconds=settings.mcp_rotation_overlap_seconds)
    for old in active:
        if old.ends_at is None:
            old.ends_at = func.now() + overlap
    made = new_token()
    row = AccessToken(
        collection_id=collection_id, owner_id=user.id, token_hash=made.digest, last4=made.last4
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return TokenCreated(**_info(row).model_dump(), token=made.plain)


@router.get("")
async def list_tokens(
    collection_id: uuid.UUID, user: CurrentUser, session: OwnerSessionDep, params: PageParamsDep
) -> Page[TokenInfo]:
    await _owned_collection(session, user.id, collection_id)
    query = select(AccessToken).where(
        AccessToken.collection_id == collection_id, AccessToken.owner_id == user.id
    )
    after = params.after(list)
    if after is not None:
        try:
            created, row_id = datetime.fromisoformat(after[0]), uuid.UUID(after[1])
        except (IndexError, TypeError, ValueError):
            raise Problem(400, detail="That page cursor isn't valid.") from None
        query = query.where(tuple_(AccessToken.created_at, AccessToken.id) < (created, row_id))
    query = query.order_by(AccessToken.created_at.desc(), AccessToken.id.desc())
    rows = (await session.scalars(query.limit(params.limit + 1))).all()
    return page(rows, params, key=lambda t: [t.created_at.isoformat(), str(t.id)], item=_info)


@router.delete("/{token_id}", status_code=204)
async def revoke_token(
    collection_id: uuid.UUID, token_id: uuid.UUID, user: CurrentUser, session: OwnerSessionDep
) -> Response:
    row = await session.scalar(
        select(AccessToken).where(
            AccessToken.id == token_id,
            AccessToken.collection_id == collection_id,
            AccessToken.owner_id == user.id,
        )
    )
    if row is None:
        raise Problem(404, detail="No such token.")
    if row.revoked_at is None:
        row.revoked_at = func.now()
        await session.commit()
    return Response(status_code=204)
