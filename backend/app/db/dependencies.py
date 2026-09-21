from app.db import pool as pool_module


async def get_db():
    """Provide a pooled database connection (FastAPI dependency).

    Borrows a connection from the pool for the duration of the request and
    gives it back afterwards. Rows are returned as dicts (``dict_row``).

    Yields:
        An open psycopg ``AsyncConnection``.
    """
    async with pool_module.pool.connection() as conn:
        yield conn
