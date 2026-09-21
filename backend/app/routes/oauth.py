from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
from psycopg import AsyncConnection
from psycopg.errors import UniqueViolation
import redis.asyncio as redis
from redis import RedisError
from app.db.dependencies import get_db
from app.cache.dependencies import get_redis
from app.security.session import create_session
from app.security.passwords import hash_password
from app.log import get_logger
import os
import secrets
import httpx
from google.oauth2 import id_token as id_token_check
from google.auth.transport import requests as google_requests
from google.auth.exceptions import GoogleAuthError


FRONTEND_URL = os.getenv("FRONTEND_URL")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

if not FRONTEND_URL or not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET or not GOOGLE_REDIRECT_URI:
    raise RuntimeError("env variable missing or not set")

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
OAUTH_STATE_TTL_SECONDS = 300

logger = get_logger(__name__)

router = APIRouter()


@router.get("/oauth/google/login")
async def oauth_login(redis: redis.Redis = Depends(get_redis)):
    """Step 1 of the Google OAuth2 flow: send the user to Google's consent screen.

    Generates a random anti-CSRF `state`, stores it in Redis (single-use,
    5 min TTL), and redirects to Google's authorize endpoint with our
    client_id, redirect_uri, requested scopes and that state. Must be
    reached via a real browser navigation (a link, never a fetch()), since
    the consent screen has to actually be visible to the user.

    Args:
        redis: Redis client (injected dependency).

    Returns:
        A redirect to Google's authorize endpoint.

    Raises:
        HTTPException: 503 on a Redis error and 501 on any other failure
            while storing the state.
    """
    # Anti-CSRF token: stored in Redis now, checked and consumed once in the
    # callback. Proves the callback we receive corresponds to a login attempt
    # we started ourselves, not a forged/replayed request.
    state = secrets.token_hex(32)
    try:
        await redis.set(f"oauth_state:{state}", 1, ex=OAUTH_STATE_TTL_SECONDS)
    except RedisError:
        logger.exception("Redis error while creating state for oauth connexion")
        raise HTTPException(status_code=503, detail="Failed to create state cache")
    except Exception:
        raise HTTPException(status_code=501, detail="Failed to create state cache")

    # Real browser navigation, never a fetch(): Google's consent screen must
    # actually be rendered on screen, not swallowed silently in the background.
    url_obj = httpx.URL(GOOGLE_AUTHORIZE_URL, params={
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
    })
    return RedirectResponse(str(url_obj))


@router.get("/oauth/google/callback")
async def oauth_callback(request: Request, redis: redis.Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Step 2 of the Google OAuth2 flow: handle Google's redirect back.

    Called after the user accepted (or declined) the consent screen.

    Order of operations:
      1. Bail out on Google's own error/denial, or a malformed callback.
      2. Verify and consume the anti-CSRF `state` generated in oauth_login.
      3. Exchange the authorization `code` for an id_token (server-to-server,
         client_secret never leaves the backend).
      4. Verify the id_token's signature/issuer/audience/expiry — this is
         the actual security guarantee that the identity is genuine.
      5. Find the matching user by email, or create one (no password set,
         verified=true directly since Google already confirmed the email).
      6. Open a session and redirect to /browse (existing full profile) or
         /complete-profile (Google can't provide gender/birth_date/location).

    On any failure the browser is redirected back to the frontend login page
    with a short `?error=<code>` — never a raised HTTPException, since the
    client here is a top-level browser navigation, not JS that could read a
    JSON error body.

    Args:
        request: Incoming request carrying Google's ``code``, ``state`` and
            ``error`` query parameters.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        A redirect to ``/browse`` or ``/complete-profile`` with the session
        cookie set, or to ``/login?error=<code>`` on failure.
    """
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    # ── 1. Google itself reports a problem (user hit "Cancel", or a genuine
    #      Google-side error) ──────────────────────────────────────────────
    if error:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=user_denied")
    if not state or not code:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=google_denied")

    # ── 2. Verify and consume the CSRF state (must exist, single-use) ──────
    redis_state = f"oauth_state:{state}"
    try:
        if not await redis.get(redis_state):
            return RedirectResponse(f"{FRONTEND_URL}/login?error=state_error")
    except RedisError:
        logger.exception("Redis error while getting state for oauth connexion")
        return RedirectResponse(f"{FRONTEND_URL}/login?error=redis_error")

    try:
        if not await redis.delete(redis_state):
            logger.warning("redis error while deleting state for oauth connexion")
    except RedisError:
        # Best-effort cleanup: the state was already confirmed valid above,
        # so a failure to delete it must not block an otherwise legitimate user.
        logger.exception("Redis error while deleting state for oauth connexion")

    # ── 3. Exchange the authorization code for tokens (server-to-server,
    #      client_secret never leaves the backend) ─────────────────────────
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(GOOGLE_TOKEN_URL, data=data)
        response_data = r.json()
    except (httpx.RequestError, ValueError) as e:
        logger.exception(f"httpx error while trying to get token from google: {e}")
        return RedirectResponse(f"{FRONTEND_URL}/login?error=httpx_error")

    if r.status_code != 200:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=google_error")

    id_token = response_data.get("id_token")
    if id_token is None:
        logger.error("id_token not found in google response")
        return RedirectResponse(f"{FRONTEND_URL}/login?error=google_error")

    # ── 4. Verify the id_token: signature, issuer, audience and expiry all
    #      checked in one call — this is the actual security guarantee of
    #      the whole flow ───────────────────────────────────────────────────
    try:
        claims = id_token_check.verify_oauth2_token(id_token, google_requests.Request(), audience=GOOGLE_CLIENT_ID)
    except (ValueError, GoogleAuthError) as e:
        logger.exception(f"Error: id_token_check.verify_oauth2_token: {e}")
        return RedirectResponse(f"{FRONTEND_URL}/login?error=google_error")

    if not claims.get("email_verified"):
        logger.error("Error: email is not trusted by google")
        return RedirectResponse(f"{FRONTEND_URL}/login?error=email_error")

    email = claims.get("email")
    first_name = claims.get("given_name")
    last_name = claims.get("family_name")

    if not email or not first_name or not last_name:
        logger.error("Error: missing user information from google user")
        return RedirectResponse(f"{FRONTEND_URL}/login?error=google_error")

    # ── 5. Find or create the local account, then open a session ───────────
    try:
        cursor = await conn.execute(
            "SELECT id, profile_complete FROM users where email = %s", (email,)
        )
        row = await cursor.fetchone()

        if not row:
            # No password ever set/known: this account only ever authenticates
            # via Google. verified=true directly since Google already
            # confirmed this email — no need to re-send our own verify email.
            password_hash = await hash_password(secrets.token_urlsafe(32))
            try:
                cursor = await conn.execute(
                    "INSERT INTO users (email, first_name, last_name, password_hash, verified) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING id, profile_complete",
                    (email, first_name, last_name, password_hash, True),
                )
            except UniqueViolation as e:
                # Race condition: another request created this same email
                # between our SELECT and this INSERT.
                logger.exception(f"Error: {e}")
                await conn.rollback()
                return RedirectResponse(f"{FRONTEND_URL}/login?error=email_already_taken")
            row = await cursor.fetchone()
            user_id = row["id"]
            profile_complete = row["profile_complete"]
            await conn.commit()
        else:
            user_id = row["id"]
            profile_complete = row["profile_complete"]

        # gender/orientation/birth_date/location aren't provided by Google,
        # so a brand-new account always starts with profile_complete=false.
        if profile_complete:
            response = RedirectResponse(f"{FRONTEND_URL}/browse")
        else:
            response = RedirectResponse(f"{FRONTEND_URL}/complete-profile")

        await create_session(response, user_id, redis)
        return response

    except Exception as e:
        logger.exception(f"Error: {e}")
        await conn.rollback()
        return RedirectResponse(f"{FRONTEND_URL}/login?error=db_error")
