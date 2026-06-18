import os, json
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Response, Request
from fastapi.responses import StreamingResponse
from psycopg import AsyncConnection
from redis import Redis
from app.db.dependencies import get_db
from app.cache.dependencies import get_redis
from app.security.session import get_current_user_id
from app.log import get_logger

REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

logger = get_logger(__name__)

router = APIRouter()

@router.get("/notifications/stream")
async def notifications(request: Request, response: Response, redis=Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    async def event_generator():
        # Dedicated connection with no socket timeout — pubsub must block indefinitely.
        # The shared Redis pool has retry/timeout settings incompatible with long-lived pubsub.
        pubsub_client = aioredis.Redis(
            host="cache",
            port=6379,
            password=REDIS_PASSWORD,
            decode_responses=True,
            socket_timeout=None,
        )
        pubsub = pubsub_client.pubsub()
        await pubsub.subscribe(f"notif:{user_id}")
        try:
            async for message in pubsub.listen():
                if await request.is_disconnected():
                    break
                if message["type"] == "message":
                    yield f"data: {message['data']}\n\n"
        except Exception:
            logger.exception("Notification stream error for user %s", user_id)
        finally:
            await pubsub.unsubscribe(f"notif:{user_id}")
            await pubsub_client.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   #disable nginx buffering
        }
    )


async def _notify(conn: AsyncConnection, user_id: str, from_user_id: str, type: str, redis: Redis):
    await conn.execute(
        "INSERT INTO notifications (user_id, from_user_id, type) VALUES (%s, %s, %s)",
        (user_id, from_user_id, type)
    )
    await redis.publish(f"notif:{user_id}", json.dumps({
        "type": type,
        "from_user_id": from_user_id,
    }))