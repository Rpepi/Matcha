from fastapi import APIRouter, Depends, Response, Request, HTTPException
from psycopg import AsyncConnection
from psycopg.errors import UniqueViolation
from itsdangerous import SignatureExpired, BadSignature
import redis.asyncio as redis
import asyncio
import time
from redis import Redis, RedisError
from app.db.dependencies import get_db
from app.cache.dependencies import get_redis
from app.security.session import create_session
from app.security.passwords import hash_password, verify_password, ph, is_password_valid
from app.security.token import generate_verification_token, send_verification_email, send_reset_email, serializer
from app.utils import require_json
from app.validation import clean_str, clean_email, MAX_EMAIL, MAX_NAME, MAX_PASSWORD, MAX_TOKEN
from app.log import get_logger
from app.security.session import get_current_user_id
from app.security.rate_limit import loginLimiter, registerLimiter, forgotPasswordLimiter

logger = get_logger(__name__)

router = APIRouter()


DUMMY_HASH = ph.hash("dummy")


async def authenticate_user(email: str, password: str, conn: AsyncConnection) -> tuple:
    """Verify an email/password pair and return the user's identity.

    A password verification is always performed, against a dummy hash when
    the email is unknown, so response time does not reveal whether an
    account exists.

    Args:
        email: Email address submitted at login.
        password: Plaintext password submitted at login.
        conn: Database connection.

    Returns:
        A tuple ``(user_id, profile_complete)`` with the id as a string.

    Raises:
        HTTPException: 401 if the email is unknown or the password is wrong;
            403 if the email address is not verified yet.
    """
    cursor = await conn.execute(
        "SELECT id, password_hash, verified, profile_complete FROM users WHERE email = %s", (email,)
    )
    row = await cursor.fetchone()
    hash_to_check = row["password_hash"] if row else DUMMY_HASH  #cannot now if an account exist mesuring the execution time.
    password_ok = await verify_password(hash_to_check, password)
    if row is None or not password_ok:
        logger.warning("Failed login attempt for email '%s'", email)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not row["verified"]:
        raise HTTPException(status_code=403, detail="Email not verified")
    return str(row["id"]), row["profile_complete"]


@router.post("/auth/login", dependencies=[Depends(loginLimiter)])
async def login(request: Request, response: Response, redis: redis.Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Log a user in and open a session.

    Expects a JSON body ``{"email": str, "password": str}``. On success the
    session cookie is set on the response.

    Args:
        request: Incoming request with the JSON body.
        response: Response on which the session cookie is set.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        A dict with the user's ``id``, ``email`` and ``profile_complete``.

    Raises:
        HTTPException: 400 if a field is missing, empty, not a string, too
            long or contains control characters, or the body is not a valid
            JSON object; 401 on invalid credentials; 403 if the email is not
            verified; 413 if the body is too large; 415 if the content type
            is not JSON; 503 if the session cannot be stored.
    """

    body = await require_json(request) # will raise exception if not json format

    email = clean_str(body.get("email"), "email", MAX_EMAIL)
    password = clean_str(body.get("password"), "password", MAX_PASSWORD, strip=False)
    user_id, profile_complete = await authenticate_user(email, password, conn)
    await create_session(response, user_id, redis)
    logger.info("User %s logged in", user_id)
    return {
        "id": user_id,
        "email": email,
        "profile_complete": profile_complete,
    }


@router.post("/auth/logout")
async def logout(request: Request, response: Response, redis: redis.Redis = Depends(get_redis)):
    """Log the user out.

    Deletes the server-side session referenced by the cookie (if any) and
    clears the cookie. Succeeds even when no valid session exists.

    Args:
        request: Incoming request, carrying the ``session`` cookie.
        response: Response on which the cookie is cleared.
        redis: Redis client (injected dependency).

    Returns:
        ``{"message": "Logged out"}``.
    """
    cookie = request.cookies.get("session")
    if cookie and "$" in cookie:
        session_id = cookie.split("$")[0]
        await redis.delete("session:" + session_id)
    response.delete_cookie(key="session")
    return {"message": "Logged out"}


@router.post("/auth/forgot-password", dependencies=[Depends(forgotPasswordLimiter)])
async def forgot_password(request: Request, conn: AsyncConnection = Depends(get_db)):
    """Send a password-reset email if the address belongs to an account.

    Expects a JSON body ``{"email": str}``. The reply is the same whether or
    not the address is registered, so it cannot be used to discover which
    emails have an account.

    Args:
        request: Incoming request with the JSON body.
        conn: Database connection (injected dependency).

    Returns:
        A generic confirmation message.

    Raises:
        HTTPException: 400 if ``email`` is missing, not a string, too long or
            contains control characters, or the body is not a JSON object.
    """
    
    body = await require_json(request)

    email = clean_str(body.get("email"), "email", MAX_EMAIL)

    cursor = await conn.execute("SELECT id FROM users WHERE email = %s", (email,))
    row = await cursor.fetchone()
    if row:
        token = serializer.dumps(str(row["id"]), salt="password-reset")
        await asyncio.to_thread(send_reset_email, email, token)
    return {"message": "If this email exists, a reset link has been sent"}


@router.post("/auth/reset-password")
async def reset_password(request: Request, redis: redis.Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Set a new password using a reset token.

    Expects a JSON body ``{"token": str, "new_password": str}``. The token
    must be a valid ``password-reset`` token less than 30 minutes old and
    not used before (used tokens are remembered in Redis for 30 minutes).

    On success, all of the user's other active sessions are also
    invalidated: their ids are looked up in the sorted set
    ``user_sessions:<user_id>`` (populated by ``create_session``, scored by
    each session's expiry) and the matching ``session:<id>`` keys are
    deleted, so a stolen session cookie stops working immediately instead
    of surviving up to its full 7-day TTL. That cleanup is best-effort: the
    password change is already committed by that point, so a Redis failure
    during it is logged but does not turn a successful reset into an error
    response.

    Args:
        request: Incoming request with the JSON body.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        ``{"message": "Password updated. You can now log in."}``.

    Raises:
        HTTPException: 400 if a field is missing, not a string, too long or
            contains control characters, the
            password is too weak or too common, the token is invalid,
            expired or already used, or Redis fails while checking/marking
            the token as used.
    """

    body = await require_json(request)

    token = clean_str(body.get("token"), "token", MAX_TOKEN)
    new_password = clean_str(body.get("new_password"), "new_password", MAX_PASSWORD, strip=False)
    if not is_password_valid(new_password):
        raise HTTPException(status_code=400, detail="Password too weak or too common")

    try:
        user_id = serializer.loads(token, salt="password-reset", max_age=1800)
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="Reset link has expired")
    except BadSignature:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    try:
        redis_key = f"used_reset:{token}"
        if await redis.get(redis_key):
            raise HTTPException(status_code=400, detail="Reset link has already been used")
        await redis.set(redis_key, 1, ex=1800)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=400, detail="Redis error")


    new_hash = await hash_password(new_password)
    await conn.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_id))
    await conn.commit()

    try:
        await redis.zremrangebyscore("user_sessions:" + str(user_id), "-inf", time.time())
        session_ids = await redis.zrange("user_sessions:" + str(user_id), 0, -1)
        for session_id in session_ids:
            await redis.delete("session:" + session_id)
    except Exception:
        # Best-effort: the password change above is already committed, so a
        # Redis hiccup here must not turn a successful reset into an error
        # response — stale sessions just outlive this cleanup slightly.
        logger.exception("Failed to invalidate other sessions for user %s after password reset", user_id)
    return {"message": "Password updated. You can now log in."}



@router.post("/auth/register", dependencies=[Depends(registerLimiter)])
async def register(request: Request, response: Response, conn: AsyncConnection = Depends(get_db)):
    """Create an account and send the verification email.

    Expects a JSON body with ``email``, ``password``, ``first_name`` and
    ``last_name``. The password is hashed with Argon2id and the account is
    created unverified.

    Args:
        request: Incoming request with the JSON body.
        response: Unused.
        conn: Database connection (injected dependency).

    Returns:
        A message asking the user to check their email.

    Raises:
        HTTPException: 400 if a field is missing, empty, not a string, too
            long (email 100 characters, names 50, password 128) or contains
            control characters, the email format is invalid, or the password
            is too weak; 409 if the email is already taken.
        Exception: If the verification email cannot be sent. The account
            has already been created at that point.
    """

    body = await require_json(request)

    # Everything is validated before the (expensive) password hash is computed.
    email = clean_email(body.get("email"))
    first_name = clean_str(body.get("first_name"), "first_name", MAX_NAME)
    last_name = clean_str(body.get("last_name"), "last_name", MAX_NAME)
    password = clean_str(body.get("password"), "password", MAX_PASSWORD, strip=False)
    if not is_password_valid(password):
        raise HTTPException(status_code=400, detail="Password too weak or too common")

    fields = {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "password_hash": await hash_password(password),
    }

    columns = ", ".join(fields.keys())
    placeholders = ", ".join(["%s"] * len(fields))
    try:
        cursor = await conn.execute(f"INSERT INTO users ({columns}) VALUES ({placeholders}) RETURNING id", list(fields.values()))
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="Email already taken")
    row = await cursor.fetchone()
    user_id = row["id"]
    await conn.commit()
    logger.info("New account registered: email='%s' id=%s", email, user_id)
    token = generate_verification_token(str(user_id), email)
    await asyncio.to_thread(send_verification_email, email, token)
    return {"message": "Account created. Check your email to verify your account."}


@router.get("/auth/verify")
async def verify_email(request: Request, redis: redis.Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Mark an email address as verified.

    Reads the ``token`` query parameter, which must be a valid, unused
    ``email-verify`` token less than one hour old, issued for the email
    address currently on the account. A token from a previous address
    (e.g. replayed after changing email) is rejected even if unexpired and
    unused, so verifying one address never verifies a different one for
    free.

    Args:
        request: Incoming request carrying the ``token`` query parameter.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        ``{"message": "Email verified. You can now log in."}``.

    Raises:
        HTTPException: 400 if the token is missing, malformed, invalid,
            expired, already used, or was issued for an email address that
            no longer matches the account.
    """
    token = request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="Missing token")
    token = clean_str(token, "token", MAX_TOKEN)
    try:
        payload = serializer.loads(token, salt="email-verify", max_age=3600)  # expire after 1h
        user_id = payload["user_id"]
        email = payload["email"]
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="Verification link has expired")
    except (BadSignature, TypeError, KeyError):
        # TypeError/KeyError also covers a signature-valid but old-format
        # token (plain user_id string, from before email was bound in).
        raise HTTPException(status_code=400, detail="Invalid verification token")

    redis_key = f"used_verify:{token}"
    try:
        if await redis.get(redis_key):
            raise HTTPException(status_code=400, detail="Verification link has already been used")
        await redis.set(redis_key, 1, ex=3600)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=400, detail="Redis error")

    cursor = await conn.execute("SELECT email FROM users WHERE id = %s", (user_id,))
    row = await cursor.fetchone()
    if not row or row["email"] != email:
        raise HTTPException(status_code=400, detail="Invalid verification token")

    await conn.execute("UPDATE users SET verified = true WHERE id = %s", (user_id,))
    await conn.commit()
    return {"message": "Email verified. You can now log in."}


@router.get("/auth/me")
async def verify_auth(request: Request, redis: redis.Redis = Depends(get_redis)):
    """Return the id of the authenticated user.

    The frontend's ``ProtectedRoute`` calls this to check the session.

    Args:
        request: Incoming request, carrying the ``session`` cookie.
        redis: Redis client (injected dependency).

    Returns:
        ``{"id": user_id}``.

    Raises:
        HTTPException: 401 if the user is not authenticated.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)
    return {"id": user_id }


