from fastapi import Response, HTTPException, Request
from redis.asyncio import Redis
from redis import RedisError
import os
import time
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
    """Create a session for a user and set the session cookie.

    Generates a random session id, stores ``session:<id>`` -> ``user_id`` in
    Redis for 7 days, and records the session id in the sorted set
    ``user_sessions:<user_id>`` (scored by its expiry timestamp) so all of a
    user's active sessions can later be found and revoked at once — see
    ``routes.authentification.reset_password``. Sets a ``session`` cookie of
    the form ``<id>$<hmac_sha256>``. The cookie is httponly, samesite=strict
    and secure unless ``ENV`` is set to something other than "production".

    Args:
        response: Response on which the cookie is set.
        user_id: Id of the authenticated user.
        conn: Redis client used to store the session.

    Raises:
        HTTPException: 503 if Redis cannot store the session.
    """
    session_id = secrets.token_hex(32)
    session_hash = hmac.new(SECRET.encode(), session_id.encode(), digestmod=hashlib.sha256).hexdigest()
    cookie_value = session_id + "$" + session_hash

    try:
        expires_at = time.time() + 604800
        await conn.set("session:" + session_id, user_id, ex=604800)
        await conn.zadd("user_sessions:" + str(user_id), {session_id: expires_at})
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
    """Resolve a session cookie to the id of the logged-in user.

    Splits the cookie into session id and HMAC, checks the signature in
    constant time, then looks up ``session:<id>`` in Redis.

    Args:
        cookie: Raw value of the ``session`` cookie (``None`` if absent).
        redis: Redis client holding the sessions.

    Returns:
        The user id stored in the session, as a string.

    Raises:
        HTTPException: 401 if the cookie is missing or malformed, the
            signature is invalid, or the session is unknown or expired.
    """
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