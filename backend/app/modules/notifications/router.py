from fastapi import APIRouter, Depends, Response, status

from app.api.deps import CurrentUser, get_current_user
from app.modules.notifications import service
from app.modules.notifications.service import NotificationList

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationList)
async def list_notifications(current_user: CurrentUser = Depends(get_current_user)) -> NotificationList:
    return await service.list_notifications(current_user)


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def read_all(current_user: CurrentUser = Depends(get_current_user)) -> Response:
    await service.mark_read(current_user, None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def read_one(notification_id: str, current_user: CurrentUser = Depends(get_current_user)) -> Response:
    await service.mark_read(current_user, notification_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
