import os
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row

pool: AsyncConnectionPool | None = None

async def open_pool():
    global pool
    pool = AsyncConnectionPool(
        conninfo=os.getenv("DATABASE_URL"),
        min_size=2,
        max_size=5,
        kwargs={"row_factory": dict_row}
    )
    await pool.open()

async def close_pool():
    if pool:
        await pool.close()
