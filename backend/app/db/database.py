import aiomysql

from app.core.config import get_settings
from app.db.migrations import apply_migrations


class MySQLDatabase:
    pool: aiomysql.Pool | None = None


db = MySQLDatabase()


async def connect_to_mysql() -> None:
    settings = get_settings()
    db.pool = await aiomysql.create_pool(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        db=settings.mysql_database,
        autocommit=True,
        cursorclass=aiomysql.cursors.DictCursor,
        minsize=1,
        maxsize=10,
    )
    async with db.pool.acquire() as conn:
        await apply_migrations(conn)


async def close_mysql_connection() -> None:
    if db.pool is not None:
        db.pool.close()
        await db.pool.wait_closed()
        db.pool = None
