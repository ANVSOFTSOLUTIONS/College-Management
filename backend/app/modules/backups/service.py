"""Backups of the database and uploaded files, kept on the server.

The API runs them itself (it has the database credentials; a cPanel cron job
does not), triggered by a daily cron call to /internal/backups/run with the
BACKUP_TOKEN, or by the super admin's "Back up now". Old backups are removed:
the last KEEP_DB database backups and KEEP_FILES file backups are kept.

Backups on the same server don't survive losing the server: the super admin
should download one regularly and keep it elsewhere.
"""

import gzip
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import status
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.errors import AppError
from app.modules.school_site.storage import UPLOAD_ROOT
from app.modules.students.files import PRIVATE_ROOT

KEEP_DB = 14  # two weeks of daily database backups
KEEP_FILES = 4  # a month of weekly file backups
FILES_EVERY_DAYS = 7
NAME = re.compile(r"^(db|files)-\d{8}-\d{6}\.(sql\.gz|tar\.gz)$")
Kind = Literal["db", "files", "auto"]


class BackupFile(BaseModel):
    name: str
    kind: str  # "db" or "files"
    size_bytes: int
    created_at: str  # UTC ISO


class BackupList(BaseModel):
    directory: str
    backups: list[BackupFile]
    last_db_hours_ago: float | None  # None: never backed up


class BackupResult(BaseModel):
    created: list[BackupFile]
    removed: list[str]


def backup_dir() -> Path:
    configured = get_settings().backup_dir
    path = Path(configured).expanduser() if configured else Path.home() / "school_backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _info(path: Path) -> BackupFile:
    stat = path.stat()
    return BackupFile(
        name=path.name, kind=path.name.split("-", 1)[0], size_bytes=stat.st_size,
        created_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
    )


def _existing(kind: str) -> list[Path]:
    return sorted((p for p in backup_dir().iterdir() if NAME.match(p.name) and p.name.startswith(f"{kind}-")), key=lambda p: p.name)


@dataclass
class _Credentials:
    host: str
    port: int
    user: str
    password: str
    database: str


def _dump_database(target: Path) -> None:
    settings = get_settings()
    creds = _Credentials(settings.mysql_host, settings.mysql_port, settings.mysql_user, settings.mysql_password, settings.mysql_database)
    # The password goes in a private temporary options file, never on the command line.
    with tempfile.NamedTemporaryFile("w", suffix=".cnf", delete=False) as options:
        password = creds.password.replace("\\", "\\\\").replace('"', '\\"')  # option files use backslash escapes
        options.write(f"[client]\nhost={creds.host}\nport={creds.port}\nuser={creds.user}\npassword=\"{password}\"\n")
        options_path = options.name
    os.chmod(options_path, 0o600)
    partial = target.with_suffix(target.suffix + ".part")
    try:
        command = [
            settings.mysqldump_path, f"--defaults-extra-file={options_path}", "--single-transaction", "--quick",
            "--no-tablespaces", "--default-character-set=utf8mb4", "--skip-lock-tables", creds.database,
        ]
        with gzip.open(partial, "wb") as out:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            shutil.copyfileobj(process.stdout, out)
            _, errors = process.communicate()
        if process.returncode != 0:
            raise RuntimeError(errors.decode(errors="replace").strip()[:300] or f"mysqldump exited with {process.returncode}")
        partial.replace(target)  # a backup from the same second is replaced, on every OS
    finally:
        os.unlink(options_path)
        partial.unlink(missing_ok=True)


def _archive_files(target: Path) -> None:
    partial = target.with_suffix(target.suffix + ".part")
    try:
        with tarfile.open(partial, "w:gz") as archive:
            for root, name in ((UPLOAD_ROOT, "uploads"), (PRIVATE_ROOT, "private_uploads")):
                if root.is_dir():
                    archive.add(root, arcname=name)
        partial.replace(target)  # a backup from the same second is replaced, on every OS
    finally:
        partial.unlink(missing_ok=True)


def _prune(kind: str, keep: int) -> list[str]:
    old = _existing(kind)[:-keep] if keep else _existing(kind)
    for path in old:
        path.unlink(missing_ok=True)
    return [p.name for p in old]


def run_backup(kind: Kind) -> BackupResult:
    """Blocking (call in a thread). 'auto' = the database, plus files once a week."""
    created, removed = [], []
    if kind in ("db", "auto"):
        target = backup_dir() / f"db-{_stamp()}.sql.gz"
        try:
            _dump_database(target)
        except (OSError, RuntimeError) as exc:
            raise AppError(status.HTTP_500_INTERNAL_SERVER_ERROR, "backup_failed", f"Database backup failed: {exc}") from exc
        created.append(_info(target))
        removed += _prune("db", KEEP_DB)
    files = _existing("files")
    due = not files or (datetime.now(timezone.utc).timestamp() - files[-1].stat().st_mtime) > FILES_EVERY_DAYS * 86400
    if kind == "files" or (kind == "auto" and due):
        target = backup_dir() / f"files-{_stamp()}.tar.gz"
        try:
            _archive_files(target)
        except OSError as exc:
            raise AppError(status.HTTP_500_INTERNAL_SERVER_ERROR, "backup_failed", f"Files backup failed: {exc}") from exc
        created.append(_info(target))
        removed += _prune("files", KEEP_FILES)
    return BackupResult(created=created, removed=removed)


def list_backups() -> BackupList:
    paths = sorted((p for p in backup_dir().iterdir() if NAME.match(p.name)), key=lambda p: p.stat().st_mtime, reverse=True)
    dbs = [p for p in paths if p.name.startswith("db-")]
    age = (datetime.now(timezone.utc).timestamp() - dbs[0].stat().st_mtime) / 3600 if dbs else None
    return BackupList(directory=str(backup_dir()), backups=[_info(p) for p in paths], last_db_hours_ago=round(age, 1) if age is not None else None)


def backup_path(name: str) -> Path:
    path = backup_dir() / name
    if not NAME.match(name) or not path.is_file():
        raise AppError(status.HTTP_404_NOT_FOUND, "backup_not_found", "Backup not found.")
    return path
