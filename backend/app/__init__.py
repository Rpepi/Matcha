from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
import redis.asyncio as redis
from redis.backoff import FullJitterBackoff
from redis.retry import Retry
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
import os
from fastapi.middleware.cors import CORSMiddleware
from app.db.pool import open_pool, close_pool
from app.log import setup_logging, get_logger
from app.presence import reset_presence
from app.routes.authentification import router as authentification_router
from app.routes.profile import router as profile_router
from app.routes.users import router as users_router
from app.routes.chat import router as chat_router
from app.routes.notifications import router as notifications_router
from app.routes.oauth import router as oauth_router
from pathlib import Path

logger = get_logger(__name__)

# The browser frontend asks for "soft" errors with this request header (see
# SoftErrorsMiddleware); the answer then carries the real status in STATUS_HEADER.
SOFT_ERRORS_HEADER = "X-Soft-Errors"
STATUS_HEADER = "X-Status"

REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
if not REDIS_PASSWORD:
    raise RuntimeError("env variable REDIS_PASSWORD not set")

retry = Retry(FullJitterBackoff(), 3, (RedisConnectionError, RedisTimeoutError))
lua = (Path(__file__).parent / "security" / "rate_limiter" /"token_bucket.lua").read_text()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the resources shared by the whole application.

    Opens the PostgreSQL connection pool and creates the Redis client
    (stored on ``app.state.redis``) before the app starts serving, forgets
    the open notification streams of the previous run (see ``app.presence``),
    then closes both on shutdown.

    Args:
        app: The FastAPI application whose state receives the Redis client.

    Yields:
        None: Control returns to FastAPI while the application is running.
    """
    await open_pool()
    app.state.redis = redis.Redis(
        host='cache',
        port='6379',
        decode_responses=True,
        max_connections=40, #connection pool max connections
        password=REDIS_PASSWORD,
        retry=retry
    )
    app.state.rate_limit_script = app.state.redis.register_script(lua)
    try:
        await reset_presence(app.state.redis)
    except Exception:
        logger.exception("Could not reset the presence state")
    yield
    await close_pool()
    await app.state.redis.aclose()


class SoftErrorsMiddleware:
    """Answer a client error (4xx) with a 200 when the client asks for it.

    Chrome prints every 4xx answer to ``fetch`` as a red "Failed to load
    resource" line in the console, even when the app expected it and handled it
    (a wrong password, a weak password, a refused like). The browser frontend
    therefore sends ``X-Soft-Errors: 1``: such an answer then goes out as a 200
    with the real status in ``X-Status``, and the frontend's fetch wrapper puts
    that status back before any app code sees the response. Nothing else
    changes: same body, same headers. Without the header (tests, curl, any
    other client) every status is the real one, and a server error (5xx) is
    never softened.

    Written as plain ASGI rather than with ``@app.middleware("http")`` so it
    never buffers a streaming answer (the notification stream).
    """

    def __init__(self, app):
        """Wrap an ASGI application.

        Args:
            app: The application to wrap.
        """
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or (SOFT_ERRORS_HEADER.lower().encode(), b"1") not in scope["headers"]:
            await self.app(scope, receive, send)
            return

        async def send_softened(message):
            if message["type"] == "http.response.start" and 400 <= message["status"] < 500:
                headers = [*message.get("headers", []), (STATUS_HEADER.lower().encode(), str(message["status"]).encode())]
                message = {**message, "status": 200, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_softened)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Sets up logging, adds the CORS middleware (only the Vite dev origin
    ``http://localhost:5173``, with credentials) and ``SoftErrorsMiddleware``,
    and registers the authentification, profile, users, chat, notifications
    and oauth routers.

    Returns:
        The configured FastAPI application.
    """
    setup_logging()
    app = FastAPI(lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", SOFT_ERRORS_HEADER],
        expose_headers=[STATUS_HEADER],
    )
    # Added after CORS, so it wraps it and sees the final status of every answer.
    app.add_middleware(SoftErrorsMiddleware)

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(self)"
        return response

    app.include_router(authentification_router)
    app.include_router(profile_router)
    app.include_router(users_router)
    app.include_router(chat_router)
    app.include_router(notifications_router)
    app.include_router(oauth_router)

    return app
