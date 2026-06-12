from fastapi import Response, HTTPException, Request
from redis.asyncio import Redis
from redis import RedisError
import os
import hmac
import hashlib
import secrets


SECRET = os.getenv("SESSION_SECRET")
if not SECRET:
    raise RuntimeError("SESSION_SECRET env variable is not set")


async def create_session(response: Response, user_id: int, conn: Redis): 
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
        samesite="strict",     # csrf protection
        max_age=604800
    )

async def get_current_user_id(request: Request, redis: Redis) -> str:
    cookie = request.cookies.get("session")
    if not cookie or "$" not in cookie:
        raise HTTPException(status_code=401, detail="Not Authenticated")
    
    session_id = cookie.split("$")[0]
    user_id = await redis.get("session:" + session_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return user_id