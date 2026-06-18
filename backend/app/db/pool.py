import os
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from app.log import get_logger

logger = get_logger(__name__)

pool: AsyncConnectionPool | None = None


async def open_pool():
    global pool
    pool = AsyncConnectionPool(
        conninfo=os.getenv("DATABASE_URL"),
        min_size=2,
        max_size=5,
        kwargs={"row_factory": dict_row},
        open=False,
    )
    await pool.open()
    logger.info("PostgreSQL connection pool opened (min=2 max=5)")


async def close_pool():
    if pool:
        await pool.close()
        logger.info("PostgreSQL connection pool closed")
