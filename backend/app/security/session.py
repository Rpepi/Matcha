from fastapi import Cookie, Response, Depends, Cookie, HTTPException
from redis.asyncio import Redis
from redis import RedisError
import os
import hmac
import hashlib
import secrets
from app.db.dependencies import get_db


SECRET = os.getenv("SESSION_SECRET")
if not SECRET:
    raise RuntimeError("SESSION_SECRET env variable is not set")


async def create_session(response: Response, user_id: int, conn: Redis) -> None: 
    session_id = secrets.token_hex(32)
    session_hash = hmac.new(SECRET.encode(), session_id.encode(), digestmod=hashlib.sha256).hexdigest()
    cookie_value = session_id + "$" + session_hash

    try:
        await conn.set("session:" + session_id, user_id, ex=604800)
    except RedisError:
        raise HTTPException(status_code=503, detail="Failed to create session cache")
        
    response.set_cookie(
        key="session",
        value=cookie_value,
        httponly=True,      # Javascript cannot read cookie (xss protection).
        secure=True,        # https
        samesite="lax",     # csrf protection
        max_age=604800
    )
