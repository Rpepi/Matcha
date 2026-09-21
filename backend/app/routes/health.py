from fastapi import APIRouter, Depends
from psycopg import AsyncConnection
from app.db.dependencies import get_db

router = APIRouter()


@router.get("/api/health")
def health():
    """Liveness probe.

    Returns:
        ``{"status": "ok"}``.
    """
    return {"status": "ok"}


@router.get("/api/db_check")
async def db_check(conn: AsyncConnection = Depends(get_db)):
    """Check database connectivity by running ``SELECT 1``.

    Args:
        conn: Database connection (injected dependency).

    Returns:
        ``{"db": row}`` where ``row`` is the row returned by the query.
    """
    result = await conn.execute("SELECT 1")
    row = await result.fetchone()
    return {"db": row}
