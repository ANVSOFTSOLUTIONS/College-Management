from app.db.migrations import apply_migrations, find_migrations_dir

CREATE = "-- a comment; with a semicolon-free line\nCREATE TABLE IF NOT EXISTS zz_migration_probe (id INT PRIMARY KEY);\n"
ALTER = "ALTER TABLE zz_migration_probe ADD COLUMN note VARCHAR(20) NULL;\nALTER TABLE zz_migration_probe ADD UNIQUE KEY uq_zz_note (note);\n"
VERSIONS = ("901_probe.sql", "902_probe_note.sql")


async def _cleanup(conn):
    async with conn.cursor() as cur:
        await cur.execute("DROP TABLE IF EXISTS zz_migration_probe")
        await cur.execute("DELETE FROM schema_migrations WHERE version IN (%s, %s)", VERSIONS)


async def test_pending_migrations_apply_once_in_order(db, tmp_path):
    (tmp_path / VERSIONS[1]).write_text(ALTER)
    (tmp_path / VERSIONS[0]).write_text(CREATE)
    async with db.pool.acquire() as conn:
        await _cleanup(conn)
        try:
            assert await apply_migrations(conn, tmp_path) == list(VERSIONS)
            assert await apply_migrations(conn, tmp_path) == []
            async with conn.cursor() as cur:
                await cur.execute("SHOW COLUMNS FROM zz_migration_probe LIKE 'note'")
                assert await cur.fetchone() is not None
        finally:
            await _cleanup(conn)


async def test_changes_already_made_by_hand_are_accepted(db, tmp_path):
    (tmp_path / VERSIONS[0]).write_text(CREATE)
    (tmp_path / VERSIONS[1]).write_text(ALTER)
    async with db.pool.acquire() as conn:
        await _cleanup(conn)
        try:
            # Simulate someone importing both files in phpMyAdmin, without the runner's bookkeeping.
            async with conn.cursor() as cur:
                await cur.execute("CREATE TABLE zz_migration_probe (id INT PRIMARY KEY, note VARCHAR(20) NULL, UNIQUE KEY uq_zz_note (note))")
            assert await apply_migrations(conn, tmp_path) == list(VERSIONS)
        finally:
            await _cleanup(conn)


def test_repo_migrations_are_found():
    migrations_dir = find_migrations_dir()
    assert migrations_dir is not None
    assert (migrations_dir / "003_teacher_profiles_and_subjects.sql").exists()


def test_no_semicolons_in_inline_comments():
    """The runner splits on ';' and only drops whole-line comments, so a ';' in a trailing comment breaks a migration."""
    from app.db.migrations import find_migrations_dir

    for path in sorted(find_migrations_dir().glob("[0-9][0-9][0-9]_*.sql")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            code, _, comment = line.partition("--")
            assert not (code.strip() and ";" in comment), f"{path.name}:{number} has ';' in a trailing comment"
