from app.db.database import db


async def fetch_one(query: str, params: tuple = ()) -> dict | None:
    async with db.pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            return await cur.fetchone()


async def fetch_all(query: str, params: tuple = ()) -> list[dict]:
    async with db.pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            return list(await cur.fetchall())


async def execute(query: str, params: tuple = ()) -> int:
    async with db.pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            return cur.rowcount
