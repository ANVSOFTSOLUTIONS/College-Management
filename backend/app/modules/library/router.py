from typing import Literal

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import CurrentUser, require_roles
from app.modules.library import service
from app.modules.library.service import BookIn, BookOut, IssueIn, LibrarySettings, LibrarySummary, LoanOut
from app.modules.parents import service as parents

router = APIRouter(prefix="/library", tags=["library"])
portal_router = APIRouter(prefix="/me/parent/children", tags=["parent portal"])

_admin_only = require_roles("admin")
_staff = require_roles("admin", "teacher")


@router.get("/settings", response_model=LibrarySettings)
async def get_settings(current_user: CurrentUser = Depends(_staff)) -> LibrarySettings:
    return await service.get_settings(current_user.school_id)


@router.put("/settings", response_model=LibrarySettings)
async def save_settings(payload: LibrarySettings, current_user: CurrentUser = Depends(_admin_only)) -> LibrarySettings:
    return await service.save_settings(current_user.school_id, payload)


@router.get("/summary", response_model=LibrarySummary)
async def summary(current_user: CurrentUser = Depends(_staff)) -> LibrarySummary:
    return await service.summary(current_user.school_id)


@router.get("/books", response_model=list[BookOut])
async def list_books(q: str = "", current_user: CurrentUser = Depends(require_roles("admin", "teacher", "student"))) -> list[BookOut]:
    """The catalogue; students can search it too."""
    return await service.list_books(current_user.school_id, q)


@router.post("/books", response_model=BookOut, status_code=status.HTTP_201_CREATED)
async def create_book(payload: BookIn, current_user: CurrentUser = Depends(_admin_only)) -> BookOut:
    return await service.create_book(current_user.school_id, payload)


@router.put("/books/{book_id}", response_model=BookOut)
async def update_book(book_id: str, payload: BookIn, current_user: CurrentUser = Depends(_admin_only)) -> BookOut:
    return await service.update_book(current_user.school_id, book_id, payload)


@router.delete("/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book(book_id: str, current_user: CurrentUser = Depends(_admin_only)) -> Response:
    await service.delete_book(current_user.school_id, book_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/loans", response_model=list[LoanOut])
async def list_loans(
    view: Literal["open", "overdue", "fines", "all"] = "open",
    student_id: str | None = None,
    current_user: CurrentUser = Depends(_admin_only),
) -> list[LoanOut]:
    return await service.list_loans(current_user.school_id, view=view, student_id=student_id)


@router.post("/loans", response_model=LoanOut, status_code=status.HTTP_201_CREATED)
async def issue(payload: IssueIn, current_user: CurrentUser = Depends(_admin_only)) -> LoanOut:
    return await service.issue(current_user, payload)


@router.post("/loans/{loan_id}/return", response_model=LoanOut)
async def return_loan(loan_id: str, current_user: CurrentUser = Depends(_admin_only)) -> LoanOut:
    return await service.return_loan(current_user.school_id, loan_id)


@router.post("/loans/{loan_id}/renew", response_model=LoanOut)
async def renew(loan_id: str, current_user: CurrentUser = Depends(_admin_only)) -> LoanOut:
    return await service.renew(current_user.school_id, loan_id)


@router.post("/loans/{loan_id}/fine-paid", response_model=LoanOut)
async def fine_paid(loan_id: str, current_user: CurrentUser = Depends(_admin_only)) -> LoanOut:
    return await service.mark_fine_paid(current_user.school_id, loan_id)


@portal_router.get("/{student_id}/library", response_model=list[LoanOut])
async def child_loans(student_id: str, current_user: CurrentUser = Depends(require_roles("parent", "student"))) -> list[LoanOut]:
    child = await parents.child_row(current_user, student_id)
    return await service.list_loans(child["school_id"], view="all", student_id=child["id"])
