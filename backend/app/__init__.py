from contextlib import asynccontextmanager
from fastapi import FastAPI
import redis.asyncio as redis
from redis.backoff import FullJitterBackoff
from redis.retry import Retry
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
import os
from fastapi.middleware.cors import CORSMiddleware
from app.db.pool import open_pool, close_pool
from app.routes.health import router as health_router
from app.routes.authentification import router as authentification_router

REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

retry = Retry(FullJitterBackoff(), 3, (RedisConnectionError, RedisTimeoutError))

@asynccontextmanager
async def lifespan(app: FastAPI):
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


    return app
