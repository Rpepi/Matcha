import re
from fastapi import APIRouter, Depends, Response, Request, HTTPException
from psycopg import AsyncConnection
from psycopg.errors import UniqueViolation
from itsdangerous import SignatureExpired, BadSignature
import redis.asyncio as redis
from redis import Redis
from app.db.dependencies import get_db
from app.cache.dependencies import get_redis
from app.security.session import create_session
from app.security.passwords import hash_password, verify_password, ph, is_password_valid
from app.security.token import generate_verification_token, send_verification_email, send_reset_email, serializer
from app.utils import require_json
from app.log import get_logger
from app.security.session import get_current_user_id

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


@router.post("/auth/login")
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
        HTTPException: 400 if a field is missing, empty or not a string, or
            the body is not valid JSON; 401 on invalid credentials; 403 if
            the email is not verified; 415 if the content type is not JSON;
            503 if the session cannot be stored.
    """

    body = await require_json(request) # will raise exception if not json format

    try:
        email = body["email"]
        password = body["password"]
    except Exception:
        raise HTTPException(status_code=400, detail="Email and password are required")
    if not isinstance(email, str) or not isinstance(password, str) or not email.strip() or not password.strip():
        raise HTTPException(status_code=400, detail="Email and password must be non-empty strings")
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


@router.post("/auth/forgot-password")
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
        HTTPException: 400 if ``email`` is missing or not a string.
    """
    
    body = await require_json(request)

    try:
        email = body["email"]
    except Exception:
        raise HTTPException(status_code=400, detail="Email is required")
    if not isinstance(email, str):
        raise HTTPException(status_code=400, detail="Email must be a string")

    cursor = await conn.execute("SELECT id FROM users WHERE email = %s", (email,))
    row = await cursor.fetchone()
    if row:
        token = serializer.dumps(str(row["id"]), salt="password-reset")
        send_reset_email(email, token)
    return {"message": "If this email exists, a reset link has been sent"}


@router.post("/auth/reset-password")
async def reset_password(request: Request, redis: redis.Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Set a new password using a reset token.

    Expects a JSON body ``{"token": str, "new_password": str}``. The token
    must be a valid ``password-reset`` token less than 30 minutes old and
    not used before (used tokens are remembered in Redis for 30 minutes).

    Args:
        request: Incoming request with the JSON body.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        ``{"message": "Password updated. You can now log in."}``.

    Raises:
        HTTPException: 400 if a field is missing or not a string, the
            password is too weak or too common, or the token is invalid,
            expired or already used.
    """

    body = await require_json(request)

    try:
        token = body["token"]
        new_password = body["new_password"]
    except Exception:
        raise HTTPException(status_code=400, detail="Token and new_password are required")
    if not isinstance(token, str) or not isinstance(new_password, str):
        raise HTTPException(status_code=400, detail="Fields must be strings")
    if not is_password_valid(new_password):
        raise HTTPException(status_code=400, detail="Password too weak or too common")

    try:
        user_id = serializer.loads(token, salt="password-reset", max_age=1800)
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="Reset link has expired")
    except BadSignature:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    redis_key = f"used_reset:{token}"
    if await redis.get(redis_key):
        raise HTTPException(status_code=400, detail="Reset link has already been used")
    await redis.set(redis_key, 1, ex=1800)

    new_hash = await hash_password(new_password)
    await conn.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_id))
    await conn.commit()
    return {"message": "Password updated. You can now log in."}


@router.post("/auth/register")
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
        HTTPException: 400 if a field is missing, empty or not a string, or
            the email format is invalid; 409 if the email is already taken.
        Exception: If the verification email cannot be sent. The account
            has already been created at that point.
    """

    body = await require_json(request)
    
    try:
        password = body["password"]
        email = body["email"]
        first_name = body["first_name"]
        last_name = body["last_name"]
    except Exception:
        raise HTTPException(status_code=400, detail="Required Fields are empty")

    #required
    fields = {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "password_hash": await hash_password(password),
    }

    if any(not v for v in fields.values()):
        raise HTTPException(status_code=400, detail="Required Fields are empty")
    if not all(isinstance(body.get(f), str) for f in ["password", "email", "first_name", "last_name"]):
        raise HTTPException(status_code=400, detail="Required fields must be strings")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=400, detail="Invalid email format")

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
    token = generate_verification_token(str(user_id))
    send_verification_email(email, token)
    return {"message": "Account created. Check your email to verify your account."}


@router.get("/auth/verify")
async def verify_email(request: Request, conn: AsyncConnection = Depends(get_db)):
    """Mark an email address as verified.

    Reads the ``token`` query parameter, which must be a valid
    ``email-verify`` token less than one hour old.

    Args:
        request: Incoming request carrying the ``token`` query parameter.
        conn: Database connection (injected dependency).

    Returns:
        ``{"message": "Email verified. You can now log in."}``.

    Raises:
        HTTPException: 400 if the token is missing, invalid or expired.
    """
    token = request.query_params.get("token")
    if not token:   
        raise HTTPException(status_code=400, detail="Missing token")
    try:
        user_id = serializer.loads(token, salt="email-verify", max_age=3600)  # expire after 1h
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="Verification link has expired")
    except BadSignature:
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


