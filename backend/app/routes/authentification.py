from fastapi import APIRouter, Depends, Response, Request, HTTPException
from psycopg import AsyncConnection
import redis.asyncio as redis
from app.db.dependencies import get_db
from app.cache.dependencies import get_redis
from app.security.session import create_session
from app.security.passwords import verify_password, ph


router = APIRouter()


DUMMY_HASH = ph.hash("dummy")


async def authenticate_user(username: str, password: str, conn: AsyncConnection) -> tuple:
    cursor = await conn.execute(
        "SELECT id, password_hash, verified, profile_complete FROM users WHERE username = %s", (username,)
    )
    row = await cursor.fetchone()
    hash_to_check = row["password_hash"] if row else DUMMY_HASH
    if not await verify_password(hash_to_check, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not row["verified"]:
        raise HTTPException(status_code=403, detail="Email not verified")
    return str(row["id"]), row["profile_complete"]


@router.post("/login")
async def login(request: Request, response: Response, redis: redis.Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(status_code=415, detail="Wrong content type")
    try:
        body = await request.json()
        username = body["username"]
        password = body["password"]
    except Exception:
        raise HTTPException(status_code=400, detail="Username and password are required")
    if not isinstance(username, str) or not isinstance(password, str):
        raise HTTPException(status_code=400, detail="Username and password must be strings")
    user_id, profile_complete = await authenticate_user(username, password, conn)
    await create_session(response, user_id, redis)
    return {
        "id": user_id,
        "username": username,
        "profile_complete": profile_complete,
    }
