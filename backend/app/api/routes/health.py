from fastapi import APIRouter

from app.db.database import db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    database_status = "connected" if db.pool is not None else "disconnected"
    return {"status": "ok", "database": database_status}
