from fastapi import Response, HTTPException, Request
from redis.asyncio import Redis
from redis import RedisError
import os
import hmac
import hashlib
import secrets
from app.log import get_logger

logger = get_logger(__name__)


SECRET = os.getenv("SESSION_SECRET")
if not SECRET:
    raise RuntimeError("SESSION_SECRET env variable is not set")

DEV_MODE = os.getenv("ENV", "production") != "production"


async def create_session(response: Response, user_id: int, conn: Redis): 
    session_id = secrets.token_hex(32)
    session_hash = hmac.new(SECRET.encode(), session_id.encode(), digestmod=hashlib.sha256).hexdigest()
    cookie_value = session_id + "$" + session_hash

    try:
        await conn.set("session:" + session_id, user_id, ex=604800)
    except RedisError:
        logger.exception("Redis error while creating session for user %s", user_id)
        raise HTTPException(status_code=503, detail="Failed to create session cache")
        
    response.set_cookie(
        key="session",
        value=cookie_value,
        httponly=True,
        secure=not DEV_MODE,
        samesite="strict",
        max_age=604800
    )

async def get_current_user_id(cookie: str, redis: Redis) -> str:
    if not cookie or "$" not in cookie:
        raise HTTPException(status_code=401, detail="Not Authenticated")
    
    session_id, received_hmac = cookie.split("$", 1)
    expected = hmac.new(SECRET.encode(), session_id.encode(), digestmod=hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hmac):
        raise HTTPException(status_code=401, detail="Not Authenticated")

    user_id = await redis.get("session:" + session_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return user_id