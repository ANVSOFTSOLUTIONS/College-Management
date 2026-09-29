from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import CurrentUser, get_current_user
from app.modules.push import service
from app.modules.push.service import SubscribeIn, UnsubscribeIn

router = APIRouter(prefix="/push", tags=["push notifications"])


@router.get("/public-key")
async def public_key(current_user: CurrentUser = Depends(get_current_user)) -> dict:
    """The key browsers need to subscribe, and how many of the user's devices get notifications."""
    public, _ = await service.vapid_keys()
    return {"public_key": public, "devices": await service.device_count(current_user)}


@router.post("/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def subscribe(payload: SubscribeIn, request: Request, current_user: CurrentUser = Depends(get_current_user)) -> Response:
    """Saves this browser/phone so notifications reach it even when the app is closed."""
    await service.subscribe(current_user, payload, request.headers.get("user-agent", ""))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(payload: UnsubscribeIn, current_user: CurrentUser = Depends(get_current_user)) -> Response:
    await service.unsubscribe(current_user, payload.endpoint)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
