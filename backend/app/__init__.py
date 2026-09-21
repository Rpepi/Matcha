from contextlib import asynccontextmanager
from fastapi import FastAPI
import redis.asyncio as redis
from redis.backoff import FullJitterBackoff
from redis.retry import Retry
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
import os
from fastapi.middleware.cors import CORSMiddleware
from app.db.pool import open_pool, close_pool
from app.log import setup_logging
from app.routes.health import router as health_router
from app.routes.authentification import router as authentification_router
from app.routes.profile import router as profile_router
from app.routes.users import router as users_router
from app.routes.chat import router as chat_router
from app.routes.notifications import router as notifications_router
from app.routes.oauth import router as oauth_router

REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
if not REDIS_PASSWORD:
    raise RuntimeError("env variable REDIS_PASSWORD not set")

retry = Retry(FullJitterBackoff(), 3, (RedisConnectionError, RedisTimeoutError))

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the resources shared by the whole application.

    Opens the PostgreSQL connection pool and creates the Redis client
    (stored on ``app.state.redis``) before the app starts serving, then
    closes both on shutdown.

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
    yield
    await close_pool()
    await app.state.redis.aclose()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Sets up logging, adds the CORS middleware (only the Vite dev origin
    ``http://localhost:5173``, with credentials) and registers the health,
    authentification, profile, users, chat, notifications and oauth routers.

    Returns:
        The configured FastAPI application.
    """
    setup_logging()
    app = FastAPI(lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],

    )

    app.include_router(health_router)
    app.include_router(authentification_router)
    app.include_router(profile_router)
    app.include_router(users_router)
    app.include_router(chat_router)
    app.include_router(notifications_router)
    app.include_router(oauth_router)

    return app
