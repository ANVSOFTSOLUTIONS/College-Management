"""Year-end promotion: move every class's students up a grade for the new year.

New-year classes are created as needed (class teacher and subject teachers
copied from last year's class of the same name and section, else from the
class being promoted). Students kept back move to their current grade in the
new year; students of the final class are marked graduated and their login is
turned off. Last year's classes are archived: kept with their attendance,
fees and exam history, but hidden from daily lists. A year is promoted once.
"""

import json
import re
import uuid
from typing import Literal

import aiomysql
from fastapi import status
from pydantic import BaseModel, Field, field_validator, model_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.database import db
from app.db.helpers import fetch_all, fetch_one

PRE_PRIMARY = ["nursery", "lkg", "ukg"]


class PlanStudent(BaseModel):
    id: str
    full_name: str
    admission_number: str


class PlanClass(BaseModel):
    class_id: str
    name: str
    section: str
    class_teacher_name: str
    students: list[PlanStudent]
    suggested_action: Literal["promote", "graduate"]
    suggested_target_name: str | None


class PromotionPlan(BaseModel):
    years: list[str]
    from_year: str | None
    suggested_to_year: str | None
    already_promoted_to: str | None
    classes: list[PlanClass]


class ClassMove(BaseModel):
    class_id: str
    action: Literal["promote", "graduate"]
    target_name: str | None = Field(default=None, max_length=100)
    target_section: str | None = Field(default=None, max_length=20)
    keep_back: list[str] = []

    _strip = field_validator("target_name", "target_section", mode="before")(lambda v: v.strip() if isinstance(v, str) else v)

    @model_validator(mode="after")
    def _target(self):
        if self.action == "promote" and not self.target_name:
            raise ValueError("Choose the class to promote into.")
        return self


class RunPromotionRequest(BaseModel):
    from_year: str = Field(min_length=4, max_length=9)
    to_year: str = Field(min_length=4, max_length=9)
    classes: list[ClassMove] = Field(min_length=1)

    @model_validator(mode="after")
    def _years(self):
        if self.from_year == self.to_year:
            raise ValueError("The new academic year must be different.")
        return self


class PromotionResult(BaseModel):
    promoted: int
    kept_back: int
    graduated: int
    classes_created: int


def next_year(year: str) -> str:
    """'2026' → '2027'; '2026-27' → '2027-28'."""
    match = re.fullmatch(r"(\d{4})(?:-(\d{2,4}))?", year)
    if not match:
        return ""
    start = int(match.group(1)) + 1
    if match.group(2):
        end = int(match.group(2)) + 1
        return f"{start}-{end % 100:02d}" if len(match.group(2)) == 2 else f"{start}-{end}"
    return str(start)


def suggest_target(name: str, all_names: set[str]) -> str | None:
    """Next grade's name, or None when this looks like the school's last class."""
    lower = name.strip().lower()
    if lower in PRE_PRIMARY:
        index = PRE_PRIMARY.index(lower)
        if index + 1 < len(PRE_PRIMARY):
            following = PRE_PRIMARY[index + 1]
            return next((n for n in all_names if n.lower() == following), following.upper() if following != "nursery" else "Nursery")
        # After UKG comes grade 1, named like the school's other numbered classes.
        numbered = sorted(n for n in all_names if re.search(r"\d+\s*$", n))
        prefix = re.sub(r"\d+\s*$", "", numbered[0]).strip() if numbered else "Class"
        return f"{prefix} 1".strip()
    match = re.search(r"(\d+)\s*$", name)
    if not match:
        return None
    candidate = f"{name[: match.start()]}{int(match.group(1)) + 1}"
    return candidate if candidate.lower() in {n.lower() for n in all_names} else None


async def plan(user: CurrentUser, from_year: str | None) -> PromotionPlan:
    years = [r["academic_year"] for r in await fetch_all(
        "SELECT DISTINCT academic_year FROM classes WHERE school_id = %s AND is_archived = 0 ORDER BY academic_year DESC", (user.school_id,)
    )]
    from_year = from_year or (years[0] if years else None)
    done = await fetch_one("SELECT to_year FROM promotion_runs WHERE school_id = %s AND from_year = %s", (user.school_id, from_year)) if from_year else None
    classes = await fetch_all(
        """
        SELECT c.id, c.name, c.section, u.full_name AS teacher_name FROM classes c
        JOIN teachers t ON t.id = c.teacher_id JOIN users u ON u.id = t.user_id
        WHERE c.school_id = %s AND c.academic_year = %s AND c.is_archived = 0
        ORDER BY c.name, c.section
        """,
        (user.school_id, from_year),
    )
    names = {c["name"] for c in classes}
    result = []
    for c in classes:
        students = await fetch_all(
            "SELECT id, full_name, admission_number FROM students WHERE class_id = %s AND status = 'active' ORDER BY full_name", (c["id"],)
        )
        target = suggest_target(c["name"], names)
        result.append(
            PlanClass(
                class_id=c["id"],
                name=c["name"],
                section=c["section"],
                class_teacher_name=c["teacher_name"],
                students=[PlanStudent(**s) for s in students],
                suggested_action="promote" if target else "graduate",
                suggested_target_name=target,
            )
        )
    return PromotionPlan(
        years=years,
        from_year=from_year,
        suggested_to_year=next_year(from_year) if from_year else None,
        already_promoted_to=done["to_year"] if done else None,
        classes=result,
    )


async def run(user: CurrentUser, payload: RunPromotionRequest) -> PromotionResult:
    if await fetch_one("SELECT id FROM promotion_runs WHERE school_id = %s AND from_year = %s", (user.school_id, payload.from_year)):
        raise AppError(status.HTTP_409_CONFLICT, "already_promoted", f"Academic year {payload.from_year} was already promoted.")
    source = {
        c["id"]: c
        for c in await fetch_all(
            "SELECT * FROM classes WHERE school_id = %s AND academic_year = %s AND is_archived = 0", (user.school_id, payload.from_year)
        )
    }
    unknown = [m.class_id for m in payload.classes if m.class_id not in source]
    if unknown or len({m.class_id for m in payload.classes}) != len(payload.classes):
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_class", f"Choose each {payload.from_year} class once.")
    if len(payload.classes) != len(source):
        raise AppError(status.HTTP_400_BAD_REQUEST, "classes_missing", f"Include every {payload.from_year} class, so no students are left behind.")
    by_key = {(c["name"].lower(), c["section"].lower()): c for c in source.values()}

    counts = {"promoted": 0, "kept_back": 0, "graduated": 0, "classes_created": 0}
    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                new_classes: dict[tuple[str, str], str] = {}

                async def target_class(name: str, section: str, fallback: dict) -> str:
                    key = (name.lower(), section.lower())
                    if key in new_classes:
                        return new_classes[key]
                    await cur.execute(
                        "SELECT id FROM classes WHERE school_id = %s AND academic_year = %s AND name = %s AND section = %s",
                        (user.school_id, payload.to_year, name, section),
                    )
                    existing = await cur.fetchone()
                    if existing:
                        new_classes[key] = existing["id"]
                        return existing["id"]
                    template = by_key.get(key, fallback)  # last year's same class, else the class being promoted
                    class_id = str(uuid.uuid4())
                    await cur.execute(
                        "INSERT INTO classes (id, school_id, teacher_id, name, section, academic_year) VALUES (%s, %s, %s, %s, %s, %s)",
                        (class_id, user.school_id, template["teacher_id"], name, section, payload.to_year),
                    )
                    await cur.execute(
                        """
                        INSERT INTO class_subjects (id, school_id, class_id, subject_id, teacher_id)
                        SELECT UUID(), school_id, %s, subject_id, teacher_id FROM class_subjects WHERE class_id = %s
                        """,
                        (class_id, template["id"]),
                    )
                    counts["classes_created"] += 1
                    new_classes[key] = class_id
                    return class_id

                for move in payload.classes:
                    klass = source[move.class_id]
                    await cur.execute("SELECT id, user_id FROM students WHERE class_id = %s AND status = 'active'", (klass["id"],))
                    students = await cur.fetchall()
                    keep = set(move.keep_back)
                    stay = [s for s in students if s["id"] in keep]
                    moving = [s for s in students if s["id"] not in keep]
                    if stay:
                        same = await target_class(klass["name"], klass["section"], klass)
                        await cur.executemany("UPDATE students SET class_id = %s WHERE id = %s", [(same, s["id"]) for s in stay])
                        counts["kept_back"] += len(stay)
                    if not moving:
                        continue
                    if move.action == "graduate":
                        await cur.executemany("UPDATE students SET status = 'graduated' WHERE id = %s", [(s["id"],) for s in moving])
                        logins = [(s["user_id"],) for s in moving if s["user_id"]]
                        if logins:
                            await cur.executemany("UPDATE users SET status = 'inactive' WHERE id = %s", logins)
                        counts["graduated"] += len(moving)
                    else:
                        target = await target_class(move.target_name, move.target_section or klass["section"], klass)
                        await cur.executemany("UPDATE students SET class_id = %s WHERE id = %s", [(target, s["id"]) for s in moving])
                        counts["promoted"] += len(moving)

                await cur.executemany("UPDATE classes SET is_archived = 1 WHERE id = %s", [(cid,) for cid in source])
                await cur.execute(
                    "INSERT INTO promotion_runs (id, school_id, from_year, to_year, summary, run_by) VALUES (%s, %s, %s, %s, %s, %s)",
                    (str(uuid.uuid4()), user.school_id, payload.from_year, payload.to_year, json.dumps(counts), user.id),
                )
        except aiomysql.IntegrityError as exc:
            await conn.rollback()
            raise AppError(status.HTTP_409_CONFLICT, "promotion_conflict", "Promotion clashed with another change. Try again.") from exc
        except Exception:
            await conn.rollback()
            raise
        await conn.commit()
    return PromotionResult(**counts)
