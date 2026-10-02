"""Inventory: lab equipment, furniture, sports goods and consumables.

Each item has a stock quantity and how many are issued out. Movements keep
the history: received (in), issued to someone (issue) and returned (return),
consumed or written off (out, damaged). Items at or below their minimum are
flagged as low stock.
"""

import uuid
from datetime import datetime
from typing import Literal

import aiomysql
from fastapi import status
from pydantic import BaseModel, Field, field_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.database import db
from app.db.helpers import execute, fetch_all, fetch_one

Kind = Literal["in", "out", "issue", "return", "damaged"]


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    category: str = Field(default="", max_length=60)
    location: str = Field(default="", max_length=100)
    unit: str = Field(default="nos", min_length=1, max_length=20)
    quantity: int = Field(default=0, ge=0, le=10_000_000)
    min_quantity: int = Field(default=0, ge=0, le=10_000_000)
    notes: str = Field(default="", max_length=300)

    _strip = field_validator("name", "category", "location", "unit", "notes", mode="before")(_strip)


class ItemUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    category: str = Field(default="", max_length=60)
    location: str = Field(default="", max_length=100)
    unit: str = Field(default="nos", min_length=1, max_length=20)
    min_quantity: int = Field(default=0, ge=0, le=10_000_000)
    notes: str = Field(default="", max_length=300)

    _strip = field_validator("name", "category", "location", "unit", "notes", mode="before")(_strip)


class MovementIn(BaseModel):
    kind: Kind
    quantity: int = Field(ge=1, le=10_000_000)
    person: str = Field(default="", max_length=150)
    note: str = Field(default="", max_length=300)

    _strip = field_validator("person", "note", mode="before")(_strip)


class ItemOut(BaseModel):
    id: str
    name: str
    category: str
    location: str
    unit: str
    quantity: int
    issued: int
    available: int
    min_quantity: int
    low_stock: bool
    notes: str


class MovementOut(BaseModel):
    id: str
    kind: str
    quantity: int
    person: str
    note: str
    by_name: str | None
    created_at: datetime


def _out(row: dict) -> ItemOut:
    available = row["quantity"] - row["issued"]
    return ItemOut(**{k: row[k] for k in ("id", "name", "category", "location", "unit", "quantity", "issued", "min_quantity", "notes")},
                   available=available, low_stock=row["quantity"] <= row["min_quantity"])


async def _get(user: CurrentUser, item_id: str) -> dict:
    row = await fetch_one("SELECT * FROM inventory_items WHERE id = %s AND school_id = %s", (item_id, user.school_id))
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "item_not_found", "Item not found.")
    return row


def _duplicate(exc: aiomysql.IntegrityError) -> AppError:
    return AppError(status.HTTP_409_CONFLICT, "item_exists", "An item with this name already exists at that location.")


async def list_items(user: CurrentUser, q: str | None, category: str | None, low_only: bool) -> list[ItemOut]:
    where, params = ["school_id = %s"], [user.school_id]
    if q:
        where.append("(name LIKE %s OR location LIKE %s)")
        params += [f"%{q.strip()}%"] * 2
    if category:
        where.append("category = %s")
        params.append(category)
    if low_only:
        where.append("quantity <= min_quantity")
    rows = await fetch_all(f"SELECT * FROM inventory_items WHERE {' AND '.join(where)} ORDER BY category, name, location", tuple(params))
    return [_out(r) for r in rows]


async def create(user: CurrentUser, payload: ItemIn) -> ItemOut:
    item_id = str(uuid.uuid4())
    try:
        await execute(
            """
            INSERT INTO inventory_items (id, school_id, name, category, location, unit, quantity, min_quantity, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (item_id, user.school_id, payload.name, payload.category, payload.location, payload.unit, payload.quantity, payload.min_quantity, payload.notes),
        )
    except aiomysql.IntegrityError as exc:
        raise _duplicate(exc) from exc
    if payload.quantity:
        await execute(
            "INSERT INTO inventory_movements (id, item_id, kind, quantity, note, created_by) VALUES (%s, %s, 'in', %s, 'Opening stock', %s)",
            (str(uuid.uuid4()), item_id, payload.quantity, user.id),
        )
    return _out(await _get(user, item_id))


async def update(user: CurrentUser, item_id: str, payload: ItemUpdate) -> ItemOut:
    await _get(user, item_id)
    try:
        await execute(
            "UPDATE inventory_items SET name = %s, category = %s, location = %s, unit = %s, min_quantity = %s, notes = %s WHERE id = %s",
            (payload.name, payload.category, payload.location, payload.unit, payload.min_quantity, payload.notes, item_id),
        )
    except aiomysql.IntegrityError as exc:
        raise _duplicate(exc) from exc
    return _out(await _get(user, item_id))


async def delete(user: CurrentUser, item_id: str) -> None:
    await _get(user, item_id)
    await execute("DELETE FROM inventory_items WHERE id = %s", (item_id,))


async def move(user: CurrentUser, item_id: str, payload: MovementIn) -> ItemOut:
    await _get(user, item_id)
    n = payload.quantity
    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                await cur.execute("SELECT quantity, issued FROM inventory_items WHERE id = %s FOR UPDATE", (item_id,))
                item = await cur.fetchone()
                available = item["quantity"] - item["issued"]
                if payload.kind in ("out", "issue", "damaged") and n > available:
                    raise AppError(status.HTTP_409_CONFLICT, "not_enough_stock", f"Only {available} available.")
                if payload.kind == "return" and n > item["issued"]:
                    raise AppError(status.HTTP_409_CONFLICT, "not_issued", f"Only {item['issued']} are issued out.")
                if payload.kind == "issue" and not payload.person:
                    raise AppError(status.HTTP_400_BAD_REQUEST, "person_required", "Say who the items are issued to.")
                change = {"in": (n, 0), "out": (-n, 0), "damaged": (-n, 0), "issue": (0, n), "return": (0, -n)}[payload.kind]
                await cur.execute("UPDATE inventory_items SET quantity = quantity + %s, issued = issued + %s WHERE id = %s", (*change, item_id))
                await cur.execute(
                    "INSERT INTO inventory_movements (id, item_id, kind, quantity, person, note, created_by) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (str(uuid.uuid4()), item_id, payload.kind, n, payload.person, payload.note, user.id),
                )
        except Exception:
            await conn.rollback()
            raise
        await conn.commit()
    return _out(await _get(user, item_id))


async def movements(user: CurrentUser, item_id: str) -> list[MovementOut]:
    await _get(user, item_id)
    rows = await fetch_all(
        """
        SELECT m.*, u.full_name AS by_name FROM inventory_movements m LEFT JOIN users u ON u.id = m.created_by
        WHERE m.item_id = %s ORDER BY m.created_at DESC, m.id LIMIT 200
        """,
        (item_id,),
    )
    return [MovementOut(**{k: r[k] for k in MovementOut.model_fields}) for r in rows]
