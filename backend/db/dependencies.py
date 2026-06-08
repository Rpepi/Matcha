from db import pool as pool_module

async def get_db():
    async with pool_module.pool.connection() as conn:
        yield conn