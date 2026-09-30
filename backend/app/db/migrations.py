"""Apply the numbered SQL migrations (database/mysql/NNN_*.sql) automatically.

schema.sql is the baseline and is imported by hand once; every later change
ships as a numbered file and is applied here, in order, the first time the app
connects after a deploy. Applied versions are recorded in schema_migrations.

Statements that fail only because their change is already there (table,
column, or index exists — e.g. someone imported the file by hand) are treated
as done, so a file is safe to meet twice. A MySQL named lock keeps forked
workers from migrating at the same time.

Files are split on ';' at line ends, so a migration must not put ';' inside
string literals or comments.
"""

import logging
import warnings
from pathlib import Path

import pymysql

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parents[2]
# On cPanel .cpanel.yml copies the files next to the app; locally they live in the repo.
_CANDIDATE_DIRS = [_BACKEND_DIR / "migrations", _BACKEND_DIR.parent / "database" / "mysql"]
_ALREADY_APPLIED_ERRORS = {
    1050,  # table already exists
    1060,  # duplicate column
    1061,  # duplicate key name
    1091,  # can't drop: constraint/key already gone
    1826,  # duplicate foreign key / check constraint name (MariaDB)
    3822,  # duplicate check constraint name (MySQL)
}
_LOCK_NAME = "school_management_migrations"


def _already_applied(exc: pymysql.err.MySQLError) -> bool:
    code, message = exc.args[0], str(exc.args[1] if len(exc.args) > 1 else "")
    # MariaDB reports a duplicate foreign key name as a generic 1005 with errno 121.
    return code in _ALREADY_APPLIED_ERRORS or (code == 1005 and "errno: 121" in message)


def find_migrations_dir() -> Path | None:
    return next((d for d in _CANDIDATE_DIRS if d.is_dir() and any(d.glob("[0-9][0-9][0-9]_*.sql"))), None)


def _statements(sql: str) -> list[str]:
    body = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    return [statement.strip() for statement in body.split(";") if statement.strip()]


async def apply_migrations(conn, migrations_dir: Path | None = None) -> list[str]:
    """Apply pending migrations on an autocommit connection; returns the versions applied."""
    migrations_dir = migrations_dir or find_migrations_dir()
    if migrations_dir is None:
        return []

    with warnings.catch_warnings():
        # "Table already exists"-style notes from IF NOT EXISTS are expected noise here.
        warnings.simplefilter("ignore", pymysql.Warning)
        return await _apply(conn, migrations_dir)


async def _apply(conn, migrations_dir: Path) -> list[str]:
    async with conn.cursor() as cur:
        await cur.execute("SELECT GET_LOCK(%s, 60)", (_LOCK_NAME,))
        try:
            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version     VARCHAR(100) NOT NULL PRIMARY KEY,
                    applied_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            await cur.execute("SELECT version FROM schema_migrations")
            applied = {row["version"] if isinstance(row, dict) else row[0] for row in await cur.fetchall()}

            newly_applied = []
            for path in sorted(migrations_dir.glob("[0-9][0-9][0-9]_*.sql")):
                if path.name in applied:
                    continue
                for statement in _statements(path.read_text(encoding="utf-8")):
                    try:
                        await cur.execute(statement)
                    except pymysql.err.MySQLError as exc:
                        if not _already_applied(exc):
                            raise
                await cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
                logger.info("Applied migration %s", path.name)
                newly_applied.append(path.name)
            return newly_applied
        finally:
            await cur.execute("SELECT RELEASE_LOCK(%s)", (_LOCK_NAME,))
