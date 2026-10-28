"""The signed-in user's collections: create, list, read, rename, delete.

Every query filters on the owner (application layer) and runs in a session whose transactions set
the owner for row-level security (database layer, app/tenancy.py). A collection that isn't yours
is a 404, the same answer as one that doesn't exist.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, tuple_
from sqlalchemy.exc import IntegrityError

from app.api.pagination import Page, PageParamsDep, page
from app.auth import CurrentUser
from app.collections import Collection
from app.problems import Problem
from app.tenancy import OwnerSessionDep

router = APIRouter(prefix="/collections", tags=["collections"])

Name = Field(min_length=3, max_length=80)


class CollectionIn(BaseModel):
    name: str = Name
    mode: Literal["knowledge", "course"] = "knowledge"


class CollectionRename(BaseModel):
    name: str = Name


class CollectionOut(BaseModel):
    id: uuid.UUID
    name: str
    mode: str
    public_id: str
    created_at: datetime


class NoSuchCollection(Problem):
    def __init__(self) -> None:
        super().__init__(404, detail="No such collection.")


class NameTaken(Problem):
    def __init__(self) -> None:
        super().__init__(409, detail="You already have a collection with that name.")


def _out(row: Collection) -> CollectionOut:
    return CollectionOut.model_validate(row, from_attributes=True)


async def _owned(
    session: OwnerSessionDep, user: CurrentUser, collection_id: uuid.UUID
) -> Collection:
    row = await session.scalar(
        select(Collection).where(Collection.id == collection_id, Collection.owner_id == user.id)
    )
    if row is None:
        raise NoSuchCollection
    return row


@router.post("", status_code=201)
async def create_collection(
    body: CollectionIn, user: CurrentUser, session: OwnerSessionDep
) -> CollectionOut:
    row = Collection(owner_id=user.id, name=body.name.strip(), mode=body.mode)
    session.add(row)
    try:
        await session.commit()
    except IntegrityError:
        raise NameTaken from None
    await session.refresh(row)
    return _out(row)


@router.get("")
async def list_collections(
    user: CurrentUser, session: OwnerSessionDep, params: PageParamsDep
) -> Page[CollectionOut]:
    query = select(Collection).where(Collection.owner_id == user.id)
    after = params.after(list)
    if after is not None:
        if len(after) != 2 or not all(isinstance(part, str) for part in after):
            raise Problem(400, detail="That page cursor isn't valid.")
        try:
            created, row_id = datetime.fromisoformat(after[0]), uuid.UUID(after[1])
        except ValueError:
            raise Problem(400, detail="That page cursor isn't valid.") from None
        query = query.where(tuple_(Collection.created_at, Collection.id) < (created, row_id))
    query = query.order_by(Collection.created_at.desc(), Collection.id.desc())
    rows = (await session.scalars(query.limit(params.limit + 1))).all()
    return page(rows, params, key=lambda c: [c.created_at.isoformat(), str(c.id)], item=_out)


@router.get("/{collection_id}")
async def get_collection(
    collection_id: uuid.UUID, user: CurrentUser, session: OwnerSessionDep
) -> CollectionOut:
    return _out(await _owned(session, user, collection_id))


@router.patch("/{collection_id}")
async def rename_collection(
    collection_id: uuid.UUID, body: CollectionRename, user: CurrentUser, session: OwnerSessionDep
) -> CollectionOut:
    row = await _owned(session, user, collection_id)
    row.name = body.name.strip()
    try:
        await session.commit()
    except IntegrityError:
        raise NameTaken from None
    await session.refresh(row)
    return _out(row)


@router.delete("/{collection_id}", status_code=204)
async def delete_collection(
    collection_id: uuid.UUID, user: CurrentUser, session: OwnerSessionDep
) -> Response:
    row = await _owned(session, user, collection_id)
    await session.delete(row)
    await session.commit()
    return Response(status_code=204)
