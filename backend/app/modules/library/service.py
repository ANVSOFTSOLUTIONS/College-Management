"""Library: the book catalogue, loans to students and faculty, and late-return fines.

A book has a number of copies; copies on loan are unavailable until returned.
A loan is due after the college's loan period; returning it late charges the
fine per day for each day past the due date. Nobody can hold more than the
college's maximum number of books at once.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi import status
from pydantic import BaseModel, Field, field_validator, model_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.db.helpers import execute, fetch_all, fetch_one
from app.modules.alerts.service import today_ist


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class LibrarySettings(BaseModel):
    loan_days: int = Field(default=14, ge=1, le=365)
    fine_per_day: float = Field(default=2.0, ge=0, le=1000)
    max_books: int = Field(default=3, ge=1, le=50)


class BookIn(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    author: str = Field(default="", max_length=200)
    isbn: str = Field(default="", max_length=20)
    category: str = Field(default="", max_length=100)
    shelf: str = Field(default="", max_length=50)
    total_copies: int = Field(default=1, ge=1, le=10000)

    _strip_text = field_validator("title", "author", "isbn", "category", "shelf", mode="before")(_strip)


class BookOut(BookIn):
    id: str
    on_loan: int
    available: int


class IssueIn(BaseModel):
    """Lend to a student or to a faculty member (one of the two)."""

    book_id: str
    student_id: str | None = None
    teacher_id: str | None = None

    @model_validator(mode="after")
    def _one_borrower(self):
        if bool(self.student_id) == bool(self.teacher_id):
            raise ValueError("Choose a student or a faculty member.")
        return self


class LoanOut(BaseModel):
    id: str
    book_id: str
    book_title: str
    borrower_name: str
    borrower_code: str  # roll number or employee code
    borrower_type: str  # 'student' or 'faculty'
    issued_on: date
    due_on: date
    returned_on: date | None
    overdue_days: int
    fine: float  # charged on return; for an open overdue loan, what it would be today
    fine_paid: bool


def _not_found(what: str) -> AppError:
    return AppError(status.HTTP_404_NOT_FOUND, f"{what}_not_found", f"{what.capitalize()} not found.")


# --- Settings -------------------------------------------------------------------


async def get_settings(school_id: str) -> LibrarySettings:
    row = await fetch_one("SELECT * FROM library_settings WHERE school_id = %s", (school_id,))
    if row is None:
        return LibrarySettings()
    return LibrarySettings(loan_days=row["loan_days"], fine_per_day=float(row["fine_per_day"]), max_books=row["max_books"])


async def save_settings(school_id: str, payload: LibrarySettings) -> LibrarySettings:
    await execute(
        """
        INSERT INTO library_settings (school_id, loan_days, fine_per_day, max_books) VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE loan_days = VALUES(loan_days), fine_per_day = VALUES(fine_per_day), max_books = VALUES(max_books)
        """,
        (school_id, payload.loan_days, payload.fine_per_day, payload.max_books),
    )
    return await get_settings(school_id)


# --- Books ----------------------------------------------------------------------

_BOOK_SELECT = """
    SELECT b.*, (SELECT COUNT(*) FROM library_loans l WHERE l.book_id = b.id AND l.returned_on IS NULL) AS on_loan
    FROM library_books b
"""


def _book_out(row: dict) -> BookOut:
    return BookOut(
        id=row["id"],
        title=row["title"],
        author=row["author"],
        isbn=row["isbn"],
        category=row["category"],
        shelf=row["shelf"],
        total_copies=row["total_copies"],
        on_loan=row["on_loan"],
        available=max(row["total_copies"] - row["on_loan"], 0),
    )


async def list_books(school_id: str, q: str = "") -> list[BookOut]:
    where, params = "b.school_id = %s", [school_id]
    if q.strip():
        where += " AND (b.title LIKE %s OR b.author LIKE %s OR b.isbn LIKE %s OR b.category LIKE %s)"
        params += [f"%{q.strip()}%"] * 4
    rows = await fetch_all(f"{_BOOK_SELECT} WHERE {where} ORDER BY b.title LIMIT 500", tuple(params))
    return [_book_out(r) for r in rows]


async def _book(school_id: str, book_id: str) -> BookOut:
    row = await fetch_one(f"{_BOOK_SELECT} WHERE b.school_id = %s AND b.id = %s", (school_id, book_id))
    if row is None:
        raise _not_found("book")
    return _book_out(row)


async def create_book(school_id: str, payload: BookIn) -> BookOut:
    book_id = str(uuid.uuid4())
    await execute(
        """
        INSERT INTO library_books (id, school_id, title, author, isbn, category, shelf, total_copies)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (book_id, school_id, payload.title, payload.author, payload.isbn, payload.category, payload.shelf, payload.total_copies),
    )
    return await _book(school_id, book_id)


async def update_book(school_id: str, book_id: str, payload: BookIn) -> BookOut:
    book = await _book(school_id, book_id)
    if payload.total_copies < book.on_loan:
        raise AppError(status.HTTP_409_CONFLICT, "copies_on_loan", f"{book.on_loan} copies are on loan; the total can't be lower.")
    await execute(
        "UPDATE library_books SET title = %s, author = %s, isbn = %s, category = %s, shelf = %s, total_copies = %s WHERE id = %s",
        (payload.title, payload.author, payload.isbn, payload.category, payload.shelf, payload.total_copies, book_id),
    )
    return await _book(school_id, book_id)


async def delete_book(school_id: str, book_id: str) -> None:
    book = await _book(school_id, book_id)
    if book.on_loan:
        raise AppError(status.HTTP_409_CONFLICT, "copies_on_loan", "Some copies are on loan. Take them back before deleting the book.")
    await execute("DELETE FROM library_books WHERE id = %s", (book_id,))


# --- Loans ----------------------------------------------------------------------

_LOAN_SELECT = """
    SELECT l.*, b.title AS book_title,
           s.full_name AS student_name, s.admission_number,
           tu.full_name AS teacher_name, t.employee_code,
           ls.fine_per_day
    FROM library_loans l
    JOIN library_books b ON b.id = l.book_id
    LEFT JOIN students s ON s.id = l.student_id
    LEFT JOIN teachers t ON t.id = l.teacher_id
    LEFT JOIN users tu ON tu.id = t.user_id
    LEFT JOIN library_settings ls ON ls.school_id = l.school_id
"""


def _fine(due_on: date, until: date, fine_per_day) -> tuple[int, Decimal]:
    late = max((until - due_on).days, 0)
    return late, Decimal(late) * Decimal(fine_per_day if fine_per_day is not None else "2.00")


def _loan_out(row: dict, today: date) -> LoanOut:
    if row["returned_on"] is None:
        overdue, fine = _fine(row["due_on"], today, row["fine_per_day"])
    else:
        overdue, fine = max((row["returned_on"] - row["due_on"]).days, 0), Decimal(row["fine"])
    is_student = row["student_id"] is not None
    return LoanOut(
        id=row["id"],
        book_id=row["book_id"],
        book_title=row["book_title"],
        borrower_name=row["student_name"] if is_student else row["teacher_name"] or "",
        borrower_code=(row["admission_number"] if is_student else row["employee_code"]) or "",
        borrower_type="student" if is_student else "faculty",
        issued_on=row["issued_on"],
        due_on=row["due_on"],
        returned_on=row["returned_on"],
        overdue_days=overdue,
        fine=float(fine),
        fine_paid=bool(row["fine_paid"]),
    )


async def list_loans(school_id: str, *, view: str = "open", student_id: str | None = None) -> list[LoanOut]:
    """view: 'open' (not returned), 'overdue' (open and past due), 'fines' (unpaid fines), or 'all'."""
    today = today_ist()
    where, params = ["l.school_id = %s"], [school_id]
    if student_id:
        where.append("l.student_id = %s")
        params.append(student_id)
    if view in ("open", "overdue"):
        where.append("l.returned_on IS NULL")
    if view == "overdue":
        where.append("l.due_on < %s")
        params.append(today)
    if view == "fines":
        where.append("l.returned_on IS NOT NULL AND l.fine > 0 AND l.fine_paid = 0")
    rows = await fetch_all(
        f"{_LOAN_SELECT} WHERE {' AND '.join(where)} ORDER BY l.returned_on IS NOT NULL, l.due_on, l.issued_on DESC LIMIT 1000",
        tuple(params),
    )
    return [_loan_out(r, today) for r in rows]


async def _loan(school_id: str, loan_id: str) -> dict:
    row = await fetch_one(f"{_LOAN_SELECT} WHERE l.school_id = %s AND l.id = %s", (school_id, loan_id))
    if row is None:
        raise _not_found("loan")
    return row


async def issue(user: CurrentUser, payload: IssueIn) -> LoanOut:
    school_id = user.school_id
    book = await _book(school_id, payload.book_id)
    if book.available <= 0:
        raise AppError(status.HTTP_409_CONFLICT, "no_copies", f"All copies of \"{book.title}\" are on loan.")
    if payload.student_id:
        student = await fetch_one("SELECT status FROM students WHERE id = %s AND school_id = %s", (payload.student_id, school_id))
        if student is None:
            raise _not_found("student")
        if student["status"] != "active":
            raise AppError(status.HTTP_409_CONFLICT, "student_left", "This student has left.")
        column, borrower = "student_id", payload.student_id
    else:
        if await fetch_one("SELECT id FROM teachers WHERE id = %s AND school_id = %s", (payload.teacher_id, school_id)) is None:
            raise _not_found("teacher")
        column, borrower = "teacher_id", payload.teacher_id

    settings = await get_settings(school_id)
    held = await fetch_one(f"SELECT COUNT(*) AS n FROM library_loans WHERE {column} = %s AND returned_on IS NULL", (borrower,))
    if held["n"] >= settings.max_books:
        raise AppError(status.HTTP_409_CONFLICT, "loan_limit", f"Already holding {held['n']} book(s); the limit is {settings.max_books}.")
    if await fetch_one(f"SELECT id FROM library_loans WHERE {column} = %s AND book_id = %s AND returned_on IS NULL", (borrower, book.id)):
        raise AppError(status.HTTP_409_CONFLICT, "already_borrowed", "They already have a copy of this book.")

    today = today_ist()
    loan_id = str(uuid.uuid4())
    await execute(
        f"""
        INSERT INTO library_loans (id, school_id, book_id, {column}, issued_on, due_on, issued_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (loan_id, school_id, book.id, borrower, today, today + timedelta(days=settings.loan_days), user.id),
    )
    return _loan_out(await _loan(school_id, loan_id), today)


async def return_loan(school_id: str, loan_id: str) -> LoanOut:
    row = await _loan(school_id, loan_id)
    if row["returned_on"] is not None:
        raise AppError(status.HTTP_409_CONFLICT, "already_returned", "This book was already returned.")
    today = today_ist()
    _, fine = _fine(row["due_on"], today, row["fine_per_day"])
    await execute("UPDATE library_loans SET returned_on = %s, fine = %s, fine_paid = %s WHERE id = %s", (today, fine, int(fine == 0), loan_id))
    return _loan_out(await _loan(school_id, loan_id), today)


async def renew(school_id: str, loan_id: str) -> LoanOut:
    """Another loan period from today, for a book that isn't overdue."""
    row = await _loan(school_id, loan_id)
    today = today_ist()
    if row["returned_on"] is not None:
        raise AppError(status.HTTP_409_CONFLICT, "already_returned", "This book was already returned.")
    if row["due_on"] < today:
        raise AppError(status.HTTP_409_CONFLICT, "overdue", "An overdue book can't be renewed; return it and collect the fine.")
    settings = await get_settings(school_id)
    await execute("UPDATE library_loans SET due_on = %s WHERE id = %s", (today + timedelta(days=settings.loan_days), loan_id))
    return _loan_out(await _loan(school_id, loan_id), today)


async def mark_fine_paid(school_id: str, loan_id: str) -> LoanOut:
    row = await _loan(school_id, loan_id)
    if row["returned_on"] is None or not row["fine"]:
        raise AppError(status.HTTP_409_CONFLICT, "no_fine", "There's no fine to collect on this loan.")
    await execute("UPDATE library_loans SET fine_paid = 1 WHERE id = %s", (loan_id,))
    return _loan_out(await _loan(school_id, loan_id), today_ist())


class LibrarySummary(BaseModel):
    titles: int
    copies: int
    on_loan: int
    overdue: int
    unpaid_fines: float


async def summary(school_id: str) -> LibrarySummary:
    books = await fetch_one("SELECT COUNT(*) AS titles, COALESCE(SUM(total_copies), 0) AS copies FROM library_books WHERE school_id = %s", (school_id,))
    loans = await fetch_one(
        """
        SELECT COALESCE(SUM(returned_on IS NULL), 0) AS on_loan, COALESCE(SUM(returned_on IS NULL AND due_on < %s), 0) AS overdue,
               COALESCE(SUM(CASE WHEN returned_on IS NOT NULL AND fine_paid = 0 THEN fine ELSE 0 END), 0) AS unpaid
        FROM library_loans WHERE school_id = %s
        """,
        (today_ist(), school_id),
    )
    return LibrarySummary(
        titles=books["titles"], copies=int(books["copies"]), on_loan=int(loans["on_loan"]), overdue=int(loans["overdue"]),
        unpaid_fines=float(loans["unpaid"]),
    )
