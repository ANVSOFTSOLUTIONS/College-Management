"""Hostel: hostels, their rooms, and which student stays in which room.

A student has at most one current room. A room can't take more students than
its capacity. Vacating keeps the stay in history (vacated_on is set).
Hostel fees are charged from the Fees page (fee type "Hostel", chosen students).
"""

import uuid
from datetime import date
from typing import Literal

import aiomysql
from fastapi import status
from pydantic import BaseModel, Field, field_validator

from app.core.errors import AppError
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.alerts.service import today_ist

Gender = Literal["boys", "girls", "mixed"]


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class HostelIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    gender: Gender = "mixed"
    warden_name: str = Field(default="", max_length=150)
    warden_phone: str = Field(default="", max_length=20)

    _strip_text = field_validator("name", "warden_name", "warden_phone", mode="before")(_strip)


class RoomIn(BaseModel):
    room_number: str = Field(min_length=1, max_length=20)
    capacity: int = Field(default=2, ge=1, le=20)
    room_type: str = Field(default="non-ac", max_length=20)

    _strip_text = field_validator("room_number", "room_type", mode="before")(_strip)


class Occupant(BaseModel):
    allocation_id: str
    student_id: str
    full_name: str
    admission_number: str
    class_name: str
    allocated_on: date


class RoomOut(RoomIn):
    id: str
    occupants: list[Occupant]


class HostelOut(HostelIn):
    id: str
    rooms: list[RoomOut]
    capacity: int
    occupied: int


class AllocateIn(BaseModel):
    student_id: str
    room_id: str


class StayOut(BaseModel):
    hostel_name: str
    room_number: str
    room_type: str
    warden_name: str
    warden_phone: str
    allocated_on: date
    roommates: list[str]


def _not_found(what: str) -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, f"{what}_not_found", f"{what.capitalize()} not found.")


async def list_hostels(school_id: str) -> list[HostelOut]:
    hostels = await fetch_all("SELECT * FROM hostels WHERE school_id = %s ORDER BY name", (school_id,))
    rooms = await fetch_all("SELECT * FROM hostel_rooms WHERE school_id = %s ORDER BY room_number", (school_id,))
    occupants = await fetch_all(
        """
        SELECT a.id AS allocation_id, a.room_id, a.allocated_on, s.id AS student_id, s.full_name, s.admission_number,
               CONCAT(c.name, ' - ', c.section) AS class_name
        FROM hostel_allocations a JOIN students s ON s.id = a.student_id JOIN classes c ON c.id = s.class_id
        WHERE a.school_id = %s AND a.vacated_on IS NULL ORDER BY s.full_name
        """,
        (school_id,),
    )
    by_room: dict[str, list[Occupant]] = {}
    for o in occupants:
        by_room.setdefault(o["room_id"], []).append(Occupant(**{k: o[k] for k in Occupant.model_fields}))
    result = []
    for h in hostels:
        room_list = [
            RoomOut(id=r["id"], room_number=r["room_number"], capacity=r["capacity"], room_type=r["room_type"], occupants=by_room.get(r["id"], []))
            for r in rooms
            if r["hostel_id"] == h["id"]
        ]
        result.append(
            HostelOut(
                id=h["id"], name=h["name"], gender=h["gender"], warden_name=h["warden_name"], warden_phone=h["warden_phone"],
                rooms=room_list, capacity=sum(r.capacity for r in room_list), occupied=sum(len(r.occupants) for r in room_list),
            )
        )
    return result


async def _hostel(school_id: str, hostel_id: str) -> dict:
    row = await fetch_one("SELECT * FROM hostels WHERE school_id = %s AND id = %s", (school_id, hostel_id))
    if row is None:
        raise _not_found("hostel")
    return row


_HOSTEL_TAKEN = AppError(status.HTTP_409_CONFLICT, "hostel_exists", "A hostel with this name already exists.")
_ROOM_TAKEN = AppError(status.HTTP_409_CONFLICT, "room_exists", "This hostel already has a room with that number.")


async def create_hostel(school_id: str, payload: HostelIn) -> None:
    try:
        await execute(
            "INSERT INTO hostels (id, school_id, name, gender, warden_name, warden_phone) VALUES (%s, %s, %s, %s, %s, %s)",
            (str(uuid.uuid4()), school_id, payload.name, payload.gender, payload.warden_name, payload.warden_phone),
        )
    except aiomysql.IntegrityError as exc:
        raise _HOSTEL_TAKEN from exc


async def update_hostel(school_id: str, hostel_id: str, payload: HostelIn) -> None:
    await _hostel(school_id, hostel_id)
    try:
        await execute(
            "UPDATE hostels SET name = %s, gender = %s, warden_name = %s, warden_phone = %s WHERE id = %s",
            (payload.name, payload.gender, payload.warden_name, payload.warden_phone, hostel_id),
        )
    except aiomysql.IntegrityError as exc:
        raise _HOSTEL_TAKEN from exc


async def _occupied(where: str, value: str) -> int:
    row = await fetch_one(
        f"SELECT COUNT(*) AS n FROM hostel_allocations a JOIN hostel_rooms r ON r.id = a.room_id WHERE {where} = %s AND a.vacated_on IS NULL",
        (value,),
    )
    return row["n"]


async def delete_hostel(school_id: str, hostel_id: str) -> None:
    await _hostel(school_id, hostel_id)
    if await _occupied("r.hostel_id", hostel_id):
        raise AppError(status.HTTP_409_CONFLICT, "hostel_occupied", "Students are staying in this hostel. Vacate them first.")
    await execute("DELETE FROM hostels WHERE id = %s", (hostel_id,))


async def add_room(school_id: str, hostel_id: str, payload: RoomIn) -> None:
    await _hostel(school_id, hostel_id)
    try:
        await execute(
            "INSERT INTO hostel_rooms (id, school_id, hostel_id, room_number, capacity, room_type) VALUES (%s, %s, %s, %s, %s, %s)",
            (str(uuid.uuid4()), school_id, hostel_id, payload.room_number, payload.capacity, payload.room_type),
        )
    except aiomysql.IntegrityError as exc:
        raise _ROOM_TAKEN from exc


async def _room(school_id: str, room_id: str) -> dict:
    row = await fetch_one("SELECT * FROM hostel_rooms WHERE school_id = %s AND id = %s", (school_id, room_id))
    if row is None:
        raise _not_found("room")
    return row


async def update_room(school_id: str, room_id: str, payload: RoomIn) -> None:
    await _room(school_id, room_id)
    occupied = await _occupied("a.room_id", room_id)
    if payload.capacity < occupied:
        raise AppError(status.HTTP_409_CONFLICT, "room_over_capacity", f"{occupied} students stay here; capacity can't be lower.")
    try:
        await execute(
            "UPDATE hostel_rooms SET room_number = %s, capacity = %s, room_type = %s WHERE id = %s",
            (payload.room_number, payload.capacity, payload.room_type, room_id),
        )
    except aiomysql.IntegrityError as exc:
        raise _ROOM_TAKEN from exc


async def delete_room(school_id: str, room_id: str) -> None:
    await _room(school_id, room_id)
    if await _occupied("a.room_id", room_id):
        raise AppError(status.HTTP_409_CONFLICT, "room_occupied", "Students are staying in this room. Vacate them first.")
    await execute("DELETE FROM hostel_rooms WHERE id = %s", (room_id,))


async def allocate(school_id: str, payload: AllocateIn) -> None:
    """Puts the student in the room, moving them out of their current room if they have one."""
    room = await _room(school_id, payload.room_id)
    student = await fetch_one("SELECT status FROM students WHERE id = %s AND school_id = %s", (payload.student_id, school_id))
    if student is None:
        raise _not_found("student")
    if student["status"] != "active":
        raise AppError(status.HTTP_409_CONFLICT, "student_left", "This student has left.")
    current = await fetch_one(
        "SELECT id, room_id FROM hostel_allocations WHERE student_id = %s AND vacated_on IS NULL", (payload.student_id,)
    )
    if current and current["room_id"] == room["id"]:
        return
    if await _occupied("a.room_id", room["id"]) >= room["capacity"]:
        raise AppError(status.HTTP_409_CONFLICT, "room_full", f"Room {room['room_number']} is full.")
    today = today_ist()
    if current:
        await execute("UPDATE hostel_allocations SET vacated_on = %s WHERE id = %s", (today, current["id"]))
    await execute(
        "INSERT INTO hostel_allocations (id, school_id, room_id, student_id, allocated_on) VALUES (%s, %s, %s, %s, %s)",
        (str(uuid.uuid4()), school_id, room["id"], payload.student_id, today),
    )


async def vacate(school_id: str, allocation_id: str) -> None:
    row = await fetch_one(
        "SELECT id FROM hostel_allocations WHERE id = %s AND school_id = %s AND vacated_on IS NULL", (allocation_id, school_id)
    )
    if row is None:
        raise _not_found("allocation")
    await execute("UPDATE hostel_allocations SET vacated_on = %s WHERE id = %s", (today_ist(), allocation_id))


async def student_stay(student_id: str) -> StayOut | None:
    row = await fetch_one(
        """
        SELECT a.room_id, a.allocated_on, r.room_number, r.room_type, h.name AS hostel_name, h.warden_name, h.warden_phone
        FROM hostel_allocations a JOIN hostel_rooms r ON r.id = a.room_id JOIN hostels h ON h.id = r.hostel_id
        WHERE a.student_id = %s AND a.vacated_on IS NULL
        """,
        (student_id,),
    )
    if row is None:
        return None
    mates = await fetch_all(
        """
        SELECT s.full_name FROM hostel_allocations a JOIN students s ON s.id = a.student_id
        WHERE a.room_id = %s AND a.vacated_on IS NULL AND a.student_id <> %s ORDER BY s.full_name
        """,
        (row["room_id"], student_id),
    )
    return StayOut(
        hostel_name=row["hostel_name"], room_number=row["room_number"], room_type=row["room_type"], warden_name=row["warden_name"],
        warden_phone=row["warden_phone"], allocated_on=row["allocated_on"], roommates=[m["full_name"] for m in mates],
    )
