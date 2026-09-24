import json
from fastapi import APIRouter, Depends, Response, Request
from fastapi.responses import StreamingResponse
from psycopg import AsyncConnection
from redis import Redis
from app.db.dependencies import get_db
from app.cache.dependencies import get_redis
from app.security.session import get_current_user_id
from app.log import get_logger

logger = get_logger(__name__)

router = APIRouter()

@router.get("/notifications/stream")
async def notifications(request: Request, response: Response, redis=Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Stream real-time notifications to the client (Server-Sent Events).

    Subscribes to the Redis channel ``notif:<user_id>`` and forwards each
    published message as an SSE ``data:`` frame. The subscription is released
    when the client disconnects or the stream fails.

    Args:
        request: Incoming request, carrying the ``session`` cookie.
        response: Unused.
        redis: Redis client (injected dependency).
        conn: Unused (injected dependency).

    Returns:
        A ``text/event-stream`` streaming response.

    Raises:
        HTTPException: 401 if the user is not authenticated.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    async def event_generator():
        """Yield one SSE frame per message published on the user's channel.

        Client disconnection is checked whenever a message arrives.

        Yields:
            SSE ``data:`` frames, each carrying one JSON notification.
        """
        pubsub = redis.pubsub()
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
            await pubsub.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   #disable nginx buffering
        }
    )


async def insert_notification(conn: AsyncConnection, user_id: str, from_user_id: str, type: str):
    """Store a notification and push it to the recipient in real time.

    Inserts a row in ``notifications``. Does not commit: the
    caller owns the transaction.

    Args:
        conn: Database connection.
        user_id: Id of the recipient.
        from_user_id: Id of the user who triggered the notification.
        type: One of "like", "unlike", "match", "visit" or "message".
    """
    await conn.execute(
        "INSERT INTO notifications (user_id, from_user_id, type) VALUES (%s, %s, %s)",
        (user_id, from_user_id, type)
    )


async def publish_notification(user_id: str, from_user_id: str, type: str, redis: Redis):
    """Push a notification to the recipient in real time.

    Publishes its type and origin as
    JSON on the Redis channel ``notif:<user_id>``. Does not commit: the
    caller owns the transaction.

    Args:
        user_id: Id of the recipient.
        from_user_id: Id of the user who triggered the notification.
        type: One of "like", "unlike", "match", "visit" or "message".
        redis: Redis client used to publish the event.
    """
    await redis.publish(f"notif:{user_id}", json.dumps({
        "type": type,
        "from_user_id": from_user_id,
    }))
