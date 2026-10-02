from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, require_roles
from app.modules.inventory import service
from app.modules.inventory.service import ItemIn, ItemOut, ItemUpdate, MovementIn, MovementOut

router = APIRouter(prefix="/inventory", tags=["inventory"])
_admin = require_roles("admin")


@router.get("/items", response_model=list[ItemOut])
async def list_items(q: str | None = None, category: str | None = None, low_only: bool = False, current_user: CurrentUser = Depends(_admin)) -> list[ItemOut]:
    return await service.list_items(current_user, q, category, low_only)


@router.post("/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
async def create(payload: ItemIn, current_user: CurrentUser = Depends(_admin)) -> ItemOut:
    return await service.create(current_user, payload)


@router.put("/items/{item_id}", response_model=ItemOut)
async def update(item_id: str, payload: ItemUpdate, current_user: CurrentUser = Depends(_admin)) -> ItemOut:
    return await service.update(current_user, item_id, payload)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(item_id: str, current_user: CurrentUser = Depends(_admin)) -> None:
    await service.delete(current_user, item_id)


@router.post("/items/{item_id}/movements", response_model=ItemOut)
async def move(item_id: str, payload: MovementIn, current_user: CurrentUser = Depends(_admin)) -> ItemOut:
    """Stock received, issued, returned, consumed or written off."""
    return await service.move(current_user, item_id, payload)


@router.get("/items/{item_id}/movements", response_model=list[MovementOut])
async def movements(item_id: str, current_user: CurrentUser = Depends(_admin)) -> list[MovementOut]:
    return await service.movements(current_user, item_id)
