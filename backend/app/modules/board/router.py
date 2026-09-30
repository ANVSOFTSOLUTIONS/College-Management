from datetime import date

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser, require_roles
from app.modules.board import audience, homework, notices
from app.modules.board.homework import ClassOption, HomeworkIn, HomeworkOut
from app.modules.board.notices import NoticeIn, NoticeOut

notices_router = APIRouter(prefix="/notices", tags=["notices"])
homework_router = APIRouter(prefix="/homework", tags=["homework"])

_everyone = require_roles("admin", "teacher", "parent", "student")
_staff = require_roles("admin", "teacher")


# --- Notices ---------------------------------------------------------------------


@notices_router.get("", response_model=list[NoticeOut])
async def list_notices(include_expired: bool = False, current_user: CurrentUser = Depends(_everyone)) -> list[NoticeOut]:
    """Notices for the signed-in user, pinned first. Staff may include expired ones."""
    return await notices.list_notices(current_user, include_expired=include_expired)


@notices_router.post("", response_model=NoticeOut, status_code=status.HTTP_201_CREATED)
async def create_notice(payload: NoticeIn, current_user: CurrentUser = Depends(_staff)) -> NoticeOut:
    return await notices.create_notice(current_user, payload)


@notices_router.put("/{notice_id}", response_model=NoticeOut)
async def update_notice(notice_id: str, payload: NoticeIn, current_user: CurrentUser = Depends(_staff)) -> NoticeOut:
    return await notices.update_notice(current_user, notice_id, payload)


@notices_router.delete("/{notice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notice(notice_id: str, current_user: CurrentUser = Depends(_staff)) -> Response:
    await notices.delete_notice(current_user, notice_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@notices_router.post("/{notice_id}/attachment", response_model=NoticeOut)
async def upload_notice_attachment(notice_id: str, file: UploadFile = File(...), current_user: CurrentUser = Depends(_staff)) -> NoticeOut:
    """PDF, JPEG, PNG or WEBP up to 10MB; replaces any earlier file."""
    return await notices.set_attachment(current_user, notice_id, file)


@notices_router.delete("/{notice_id}/attachment", response_model=NoticeOut)
async def remove_notice_attachment(notice_id: str, current_user: CurrentUser = Depends(_staff)) -> NoticeOut:
    return await notices.set_attachment(current_user, notice_id, None)


@notices_router.get("/{notice_id}/attachment", response_class=FileResponse)
async def get_notice_attachment(notice_id: str, current_user: CurrentUser = Depends(_everyone)) -> FileResponse:
    return audience.attachment_response(await notices.attachment_row(current_user, notice_id))


# --- Homework --------------------------------------------------------------------


@homework_router.get("", response_model=list[HomeworkOut])
async def list_homework(
    class_id: str | None = None,
    student_id: str | None = None,
    since: date | None = None,
    current_user: CurrentUser = Depends(_everyone),
) -> list[HomeworkOut]:
    """Homework due on or after `since` (default: two weeks ago), newest due date first.

    Students see their class; parents their children (`student_id` picks one);
    teachers the classes they teach; admins every class.
    """
    return await homework.list_homework(current_user, class_id=class_id, student_id=student_id, since=since)


@homework_router.get("/options", response_model=list[ClassOption])
async def posting_options(current_user: CurrentUser = Depends(_staff)) -> list[ClassOption]:
    """Classes (with subjects) the user can post homework and class notices to."""
    return await homework.posting_options(current_user)


@homework_router.post("", response_model=HomeworkOut, status_code=status.HTTP_201_CREATED)
async def create_homework(payload: HomeworkIn, current_user: CurrentUser = Depends(_staff)) -> HomeworkOut:
    return await homework.create_homework(current_user, payload)


@homework_router.put("/{homework_id}", response_model=HomeworkOut)
async def update_homework(homework_id: str, payload: HomeworkIn, current_user: CurrentUser = Depends(_staff)) -> HomeworkOut:
    return await homework.update_homework(current_user, homework_id, payload)


@homework_router.delete("/{homework_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_homework(homework_id: str, current_user: CurrentUser = Depends(_staff)) -> Response:
    await homework.delete_homework(current_user, homework_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@homework_router.post("/{homework_id}/attachment", response_model=HomeworkOut)
async def upload_homework_attachment(homework_id: str, file: UploadFile = File(...), current_user: CurrentUser = Depends(_staff)) -> HomeworkOut:
    return await homework.set_attachment(current_user, homework_id, file)


@homework_router.delete("/{homework_id}/attachment", response_model=HomeworkOut)
async def remove_homework_attachment(homework_id: str, current_user: CurrentUser = Depends(_staff)) -> HomeworkOut:
    return await homework.set_attachment(current_user, homework_id, None)


@homework_router.get("/{homework_id}/attachment", response_class=FileResponse)
async def get_homework_attachment(homework_id: str, current_user: CurrentUser = Depends(_everyone)) -> FileResponse:
    return audience.attachment_response(await homework.attachment_row(current_user, homework_id))
