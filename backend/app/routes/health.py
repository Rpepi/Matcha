from fastapi import APIRouter, Depends
from psycopg import AsyncConnection
from app.db.dependencies import get_db

router = APIRouter()


@router.get("/api/health")
def health():
    return {"status": "ok"}


@router.get("/api/db_check")
async def db_check(conn: AsyncConnection = Depends(get_db)):
    result = await conn.execute("SELECT 1")
    row = await result.fetchone()
    return {"db": row}
