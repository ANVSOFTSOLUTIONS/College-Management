import asyncio
import hmac

from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser, require_roles
from app.core.config import get_settings
from app.core.errors import AppError
from app.modules.backups import service
from app.modules.backups.service import BackupList, BackupResult, Kind

internal_router = APIRouter(prefix="/internal/backups", tags=["backups"])
router = APIRouter(prefix="/super-admin/backups", tags=["backups"])

_super_admin = require_roles("super_admin")
_lock = asyncio.Lock()  # one backup at a time per process


async def _run(kind: Kind) -> BackupResult:
    if _lock.locked():
        raise AppError(status.HTTP_409_CONFLICT, "backup_running", "A backup is already running.")
    async with _lock:
        return await asyncio.to_thread(service.run_backup, kind)


@internal_router.post("/run", response_model=BackupResult)
async def run_scheduled_backup(kind: Kind = "auto", x_backup_token: str = Header(default="")) -> BackupResult:
    """For the daily cron job: needs the BACKUP_TOKEN environment variable to be set and sent."""
    expected = get_settings().backup_token
    if not expected or not hmac.compare_digest(expected, x_backup_token):
        raise AppError(status.HTTP_403_FORBIDDEN, "forbidden", "Invalid backup token.")
    return await _run(kind)


@router.get("", response_model=BackupList)
async def list_backups(current_user: CurrentUser = Depends(_super_admin)) -> BackupList:
    return await asyncio.to_thread(service.list_backups)


@router.post("", response_model=BackupResult)
async def back_up_now(kind: Kind = "db", current_user: CurrentUser = Depends(_super_admin)) -> BackupResult:
    return await _run(kind)


@router.get("/{name}", response_class=FileResponse)
async def download_backup(name: str, current_user: CurrentUser = Depends(_super_admin)) -> FileResponse:
    """Download a copy to keep somewhere other than this server."""
    return FileResponse(service.backup_path(name), media_type="application/gzip", filename=name, headers={"Cache-Control": "no-store"})
