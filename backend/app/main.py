from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from app.db.pool import open_pool,  close_pool
from psycopg import AsyncConnection
from app.db.dependencies import get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await open_pool()
    yield
    await close_pool()

app = FastAPI(lifespan=lifespan)

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/db_check")
async def db_check(conn: AsyncConnection = Depends(get_db)):
    result = await conn.execute("SELECT * FROM MIGRATIONS")
    row = await result.fetchall()
    return {"db": row}

