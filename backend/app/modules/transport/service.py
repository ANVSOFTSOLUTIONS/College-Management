"""Transport: bus routes with their stops, and which students ride which route.

A student rides at most one route (assigning again moves them). A route can't
carry more riders than it has seats. Transport fees are charged from the Fees
page (fee type "Transport", chosen students); the route's annual fare is shown
as a guide.
"""

import uuid
from datetime import date

import aiomysql
from fastapi import status
from pydantic import BaseModel, Field, field_validator

from app.core.errors import AppError
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.alerts.service import today_ist


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class StopIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    pickup_time: str = Field(default="", max_length=10)

    _strip_text = field_validator("name", "pickup_time", mode="before")(_strip)


class RouteIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    vehicle_number: str = Field(default="", max_length=20)
    driver_name: str = Field(default="", max_length=150)
    driver_phone: str = Field(default="", max_length=20)
    seats: int = Field(default=50, ge=1, le=500)
    annual_fare: float = Field(default=0, ge=0, le=1_000_000)
    stops: list[StopIn] = Field(default_factory=list, max_length=100)  # in order of pickup

    _strip_text = field_validator("name", "vehicle_number", "driver_name", "driver_phone", mode="before")(_strip)


class StopOut(StopIn):
    id: str


class Rider(BaseModel):
    student_id: str
    full_name: str
    admission_number: str
    class_name: str
    stop_id: str | None
    stop_name: str | None


class RouteOut(BaseModel):
    id: str
    name: str
    vehicle_number: str
    driver_name: str
    driver_phone: str
    seats: int
    annual_fare: float
    stops: list[StopOut]
    riders: list[Rider]


class AssignIn(BaseModel):
    student_id: str
    route_id: str
    stop_id: str | None = None


class RideOut(BaseModel):
    route_name: str
    vehicle_number: str
    driver_name: str
    driver_phone: str
    stop_name: str | None
    pickup_time: str | None
    assigned_on: date


def _not_found(what: str) -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, f"{what}_not_found", f"{what.capitalize()} not found.")


_ROUTE_TAKEN = AppError(status.HTTP_409_CONFLICT, "route_exists", "A route with this name already exists.")


async def list_routes(school_id: str) -> list[RouteOut]:
    routes = await fetch_all("SELECT * FROM transport_routes WHERE school_id = %s ORDER BY name", (school_id,))
    if not routes:
        return []
    placeholders = ", ".join(["%s"] * len(routes))
    ids = tuple(r["id"] for r in routes)
    stops = await fetch_all(f"SELECT * FROM transport_stops WHERE route_id IN ({placeholders}) ORDER BY sort_order", ids)
    riders = await fetch_all(
        """
        SELECT a.route_id, a.stop_id, st.name AS stop_name, s.id AS student_id, s.full_name, s.admission_number,
               CONCAT(c.name, ' - ', c.section) AS class_name
        FROM transport_assignments a JOIN students s ON s.id = a.student_id JOIN classes c ON c.id = s.class_id
        LEFT JOIN transport_stops st ON st.id = a.stop_id
        WHERE a.school_id = %s ORDER BY s.full_name
        """,
        (school_id,),
    )
    return [
        RouteOut(
            id=r["id"], name=r["name"], vehicle_number=r["vehicle_number"], driver_name=r["driver_name"], driver_phone=r["driver_phone"],
            seats=r["seats"], annual_fare=float(r["annual_fare"]),
            stops=[StopOut(id=s["id"], name=s["name"], pickup_time=s["pickup_time"]) for s in stops if s["route_id"] == r["id"]],
            riders=[Rider(**{k: x[k] for k in Rider.model_fields}) for x in riders if x["route_id"] == r["id"]],
        )
        for r in routes
    ]


async def _route(school_id: str, route_id: str) -> dict:
    row = await fetch_one("SELECT * FROM transport_routes WHERE school_id = %s AND id = %s", (school_id, route_id))
    if row is None:
        raise _not_found("route")
    return row


async def _riders(route_id: str) -> int:
    return (await fetch_one("SELECT COUNT(*) AS n FROM transport_assignments WHERE route_id = %s", (route_id,)))["n"]


async def _save_stops(route_id: str, stops: list[StopIn]) -> None:
    """Replaces the route's stops, keeping the ids (and riders' stops) of stops whose name is unchanged."""
    existing = {s["name"].lower(): s["id"] for s in await fetch_all("SELECT id, name FROM transport_stops WHERE route_id = %s", (route_id,))}
    kept = []
    for order, stop in enumerate(stops):
        stop_id = existing.get(stop.name.lower())
        if stop_id:
            await execute("UPDATE transport_stops SET name = %s, pickup_time = %s, sort_order = %s WHERE id = %s", (stop.name, stop.pickup_time, order, stop_id))
        else:
            stop_id = str(uuid.uuid4())
            await execute(
                "INSERT INTO transport_stops (id, route_id, name, pickup_time, sort_order) VALUES (%s, %s, %s, %s, %s)",
                (stop_id, route_id, stop.name, stop.pickup_time, order),
            )
        kept.append(stop_id)
    stale = [sid for sid in existing.values() if sid not in kept]
    if stale:
        await execute(f"DELETE FROM transport_stops WHERE id IN ({', '.join(['%s'] * len(stale))})", tuple(stale))


async def create_route(school_id: str, payload: RouteIn) -> None:
    route_id = str(uuid.uuid4())
    try:
        await execute(
            """
            INSERT INTO transport_routes (id, school_id, name, vehicle_number, driver_name, driver_phone, seats, annual_fare)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (route_id, school_id, payload.name, payload.vehicle_number, payload.driver_name, payload.driver_phone, payload.seats, payload.annual_fare),
        )
    except aiomysql.IntegrityError as exc:
        raise _ROUTE_TAKEN from exc
    await _save_stops(route_id, payload.stops)


async def update_route(school_id: str, route_id: str, payload: RouteIn) -> None:
    await _route(school_id, route_id)
    riders = await _riders(route_id)
    if payload.seats < riders:
        raise AppError(status.HTTP_409_CONFLICT, "route_over_capacity", f"{riders} students ride this route; seats can't be fewer.")
    try:
        await execute(
            """
            UPDATE transport_routes SET name = %s, vehicle_number = %s, driver_name = %s, driver_phone = %s, seats = %s, annual_fare = %s
            WHERE id = %s
            """,
            (payload.name, payload.vehicle_number, payload.driver_name, payload.driver_phone, payload.seats, payload.annual_fare, route_id),
        )
    except aiomysql.IntegrityError as exc:
        raise _ROUTE_TAKEN from exc
    await _save_stops(route_id, payload.stops)


async def delete_route(school_id: str, route_id: str) -> None:
    await _route(school_id, route_id)
    if await _riders(route_id):
        raise AppError(status.HTTP_409_CONFLICT, "route_has_riders", "Students ride this route. Remove them first.")
    await execute("DELETE FROM transport_routes WHERE id = %s", (route_id,))


async def assign(school_id: str, payload: AssignIn) -> None:
    route = await _route(school_id, payload.route_id)
    student = await fetch_one("SELECT status FROM students WHERE id = %s AND school_id = %s", (payload.student_id, school_id))
    if student is None:
        raise _not_found("student")
    if student["status"] != "active":
        raise AppError(status.HTTP_409_CONFLICT, "student_left", "This student has left.")
    if payload.stop_id and await fetch_one("SELECT id FROM transport_stops WHERE id = %s AND route_id = %s", (payload.stop_id, route["id"])) is None:
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_stop", "Choose a stop on this route.")
    current = await fetch_one("SELECT route_id FROM transport_assignments WHERE student_id = %s", (payload.student_id,))
    if (current is None or current["route_id"] != route["id"]) and await _riders(route["id"]) >= route["seats"]:
        raise AppError(status.HTTP_409_CONFLICT, "route_full", f"{route['name']} has no free seats.")
    await execute(
        """
        INSERT INTO transport_assignments (student_id, school_id, route_id, stop_id, assigned_on) VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE route_id = VALUES(route_id), stop_id = VALUES(stop_id), assigned_on = VALUES(assigned_on)
        """,
        (payload.student_id, school_id, route["id"], payload.stop_id, today_ist()),
    )


async def unassign(school_id: str, student_id: str) -> None:
    await execute("DELETE FROM transport_assignments WHERE student_id = %s AND school_id = %s", (student_id, school_id))


async def student_ride(student_id: str) -> RideOut | None:
    row = await fetch_one(
        """
        SELECT r.name AS route_name, r.vehicle_number, r.driver_name, r.driver_phone, st.name AS stop_name, st.pickup_time, a.assigned_on
        FROM transport_assignments a JOIN transport_routes r ON r.id = a.route_id LEFT JOIN transport_stops st ON st.id = a.stop_id
        WHERE a.student_id = %s
        """,
        (student_id,),
    )
    return RideOut(**row) if row else None
