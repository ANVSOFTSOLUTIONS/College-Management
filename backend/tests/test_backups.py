import gzip
import os
import tarfile
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.modules.backups import service
from app.modules.backups.service import BackupResult
from tests.factories import auth_headers, create_school, create_user, login

API = "/api/v1"
PASSWORD = "Secret123!"
XAMPP_MYSQLDUMP = Path("C:/xampp/mysql/bin/mysqldump.exe")


@pytest.fixture
def backup_settings(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "backup_dir", str(tmp_path))
    monkeypatch.setattr(settings, "backup_token", "cron-secret-123")
    if XAMPP_MYSQLDUMP.exists():
        monkeypatch.setattr(settings, "mysqldump_path", str(XAMPP_MYSQLDUMP))
    return tmp_path


@pytest.mark.skipif(not XAMPP_MYSQLDUMP.exists(), reason="needs a local mysqldump")
async def test_real_database_and_files_backup(db, backup_settings):
    await create_school(code="BAK1")
    result = service.run_backup("auto")  # first run: database and files
    kinds = sorted(b.kind for b in result.created)
    assert kinds == ["db", "files"]
    db_file = next(backup_settings / b.name for b in result.created if b.kind == "db")
    dump = gzip.decompress(db_file.read_bytes()).decode()
    assert "CREATE TABLE `schools`" in dump and "BAK1" in dump
    files = next(backup_settings / b.name for b in result.created if b.kind == "files")
    with tarfile.open(files) as archive:
        assert any(name.startswith(("uploads", "private_uploads")) for name in archive.getnames())
    # A second 'auto' run the same week only backs up the database.
    assert [b.kind for b in service.run_backup("auto").created] == ["db"]
    assert not list(backup_settings.glob("*.part"))


def test_old_backups_are_removed(backup_settings):
    for day in range(1, 19):
        path = backup_settings / f"db-202609{day:02d}-020000.sql.gz"
        path.write_bytes(b"x")
        os.utime(path, (day * 86400, day * 86400))
    (backup_settings / "notes.txt").write_text("left alone")
    removed = service._prune("db", service.KEEP_DB)
    assert len(removed) == 4 and removed[0] == "db-20260901-020000.sql.gz"
    assert len(list(backup_settings.glob("db-*"))) == 14 and (backup_settings / "notes.txt").exists()


def test_bad_mysqldump_reports_failure(backup_settings, monkeypatch):
    monkeypatch.setattr(get_settings(), "mysqldump_path", "definitely-not-mysqldump")
    with pytest.raises(Exception) as error:
        service.run_backup("db")
    assert "Database backup failed" in str(error.value.detail)
    assert not list(backup_settings.glob("db-*"))


async def test_cron_trigger_needs_the_token(db, client, backup_settings, monkeypatch):
    calls = []
    monkeypatch.setattr(service, "run_backup", lambda kind: calls.append(kind) or BackupResult(created=[], removed=[]))
    url = f"{API}/internal/backups/run"
    assert (await client.post(url)).status_code == 403
    assert (await client.post(url, headers={"X-Backup-Token": "wrong"})).status_code == 403
    assert (await client.post(url, headers={"X-Backup-Token": "cron-secret-123"})).status_code == 200
    monkeypatch.setattr(get_settings(), "backup_token", "")
    assert (await client.post(url, headers={"X-Backup-Token": ""})).status_code == 403  # unset token: trigger off
    assert calls == ["auto"]


async def test_super_admin_lists_and_downloads(db, client, backup_settings):
    (backup_settings / "db-20260928-020000.sql.gz").write_bytes(gzip.compress(b"-- dump"))
    await create_user(school_id=None, email="root-bak@example.com", password=PASSWORD, role="super_admin")
    root = auth_headers((await login(client, "root-bak@example.com", PASSWORD)).json()["access_token"])
    listed = (await client.get(f"{API}/super-admin/backups", headers=root)).json()
    assert [b["name"] for b in listed["backups"]] == ["db-20260928-020000.sql.gz"] and listed["last_db_hours_ago"] is not None
    download = await client.get(f"{API}/super-admin/backups/db-20260928-020000.sql.gz", headers=root)
    assert gzip.decompress(download.content) == b"-- dump"
    assert (await client.get(f"{API}/super-admin/backups/..%2F..%2Fetc%2Fpasswd", headers=root)).status_code == 404

    school_id = await create_school(code="BAK2")
    await create_user(school_id=school_id, email="bak2-admin@example.com", password=PASSWORD, role="admin")
    admin = auth_headers((await login(client, "bak2-admin@example.com", PASSWORD)).json()["access_token"])
    assert (await client.get(f"{API}/super-admin/backups", headers=admin)).status_code == 403
