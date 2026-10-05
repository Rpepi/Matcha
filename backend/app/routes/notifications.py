import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from psycopg import AsyncConnection
from redis import Redis
from app.db.dependencies import get_db
from app.cache.dependencies import get_redis
from app.security.session import get_current_user_id
from app.log import get_logger

logger = get_logger(__name__)

# The box shows (and keeps) at most this many notifications. Read ones beyond it are
# deleted when notifications are marked as seen; unread ones are never deleted.
NOTIFICATIONS_LIMIT = 50

# Notifications from someone blocked, in either direction, are neither shown nor
# counted. One definition for the list and the counter, so the badge always matches.
NOT_FROM_A_BLOCKED_USER = """
    NOT EXISTS (
        SELECT 1 FROM blocks b
        WHERE (b.blocker_id = n.user_id AND b.blocked_id = n.from_user_id)
            OR (b.blocker_id = n.from_user_id AND b.blocked_id = n.user_id)
    )
"""

router = APIRouter()

@router.get("/notifications/stream")
async def notifications(request: Request, redis=Depends(get_redis)):
    """Stream real-time notifications to the client (Server-Sent Events).

    Subscribes to the Redis channel ``notif:<user_id>`` and forwards each
    published message as an SSE ``data:`` frame. The subscription is released
    when the client disconnects or the stream fails.

    This handler must not depend on ``get_db``: the stream stays open for as
    long as the page does, and a pooled connection held that long would, with
    a handful of open tabs, exhaust the pool (max 5) and freeze every endpoint
    that touches the database.

    Args:
        request: Incoming request, carrying the ``session`` cookie.
        redis: Redis client (injected dependency).

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


@router.get("/notifications")
async def list_notifications(request: Request, conn: AsyncConnection = Depends(get_db), redis: Redis = Depends(get_redis)):
    """List the current user's latest notifications, newest first.

    Notifications from someone blocked in either direction are left out, like in
    the unread counter. The sender's first name comes from here because
    ``GET /users/{id}`` is not an option for every sender (404 once blocked).

    Args:
        request: Incoming request, carrying the ``session`` cookie.
        conn: Database connection (injected dependency).
        redis: Redis client (injected dependency).

    Returns:
        At most ``NOTIFICATIONS_LIMIT`` dicts with ``id``, ``type`` (``like``,
        ``unlike``, ``match``, ``visit`` or ``message``), ``seen``,
        ``created_at``, and ``from_user_id`` and ``first_name`` of the sender.

    Raises:
        HTTPException: 401 if not authenticated.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    cursor = await conn.execute(f"""
        SELECT n.id, n.type, n.seen, n.created_at, u.id AS from_user_id, u.first_name
        FROM notifications n
        JOIN users u ON u.id = n.from_user_id
        WHERE n.user_id = %s
            AND {NOT_FROM_A_BLOCKED_USER}
        ORDER BY n.id DESC
        LIMIT {NOTIFICATIONS_LIMIT}
    """, (user_id,))
    rows = await cursor.fetchall()
    return rows


@router.get("/notifications/unread-count")
async def unread_count(request: Request, conn: AsyncConnection = Depends(get_db), redis: Redis = Depends(get_redis)):
    """Count the current user's unread notifications.

    Notifications from someone blocked in either direction are left out, so
    the badge agrees with the list. The query keeps ``seen = false`` as is: it
    is what lets PostgreSQL use the partial index ``idx_notifications_unread``.

    Args:
        request: Incoming request, carrying the ``session`` cookie.
        conn: Database connection (injected dependency).
        redis: Redis client (injected dependency).

    Returns:
        ``{"unread": n}``.

    Raises:
        HTTPException: 401 if not authenticated.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    cursor = await conn.execute(f"""
        SELECT COUNT(*) AS unread
        FROM notifications n
        WHERE n.user_id = %s
            AND n.seen = false
            AND {NOT_FROM_A_BLOCKED_USER}
    """, (user_id,))
    row = await cursor.fetchone()
    return {"unread": row["unread"]}


@router.post("/notifications/seen")
async def set_notifications_as_seen(request: Request, conn: AsyncConnection = Depends(get_db), redis: Redis = Depends(get_redis)):
    """Mark all of the current user's notifications as seen.

    Also deletes the read notifications beyond the newest ``NOTIFICATIONS_LIMIT``,
    so the box stays small. Unread ones are never deleted.

    Args:
        request: Incoming request, carrying the ``session`` cookie.
        conn: Database connection (injected dependency).
        redis: Redis client (injected dependency).

    Returns:
        ``{"updated": n}``, the number of notifications that were unread.

    Raises:
        HTTPException: 401 if not authenticated.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    cursor = await conn.execute(
        "UPDATE notifications SET seen = true WHERE user_id = %s AND seen = false",
        (user_id,),
    )
    updated = cursor.rowcount
    await conn.execute("""
        DELETE FROM notifications
        WHERE user_id = %s AND seen = true
            AND id NOT IN (SELECT id FROM notifications WHERE user_id = %s ORDER BY id DESC LIMIT %s)
    """, (user_id, user_id, NOTIFICATIONS_LIMIT))
    await conn.commit()
    return {"updated": updated}


async def insert_notification(conn: AsyncConnection, user_id: int, from_user_id: int, type: str):
    """Store a notification and push it to the recipient in real time.

    Inserts a row in ``notifications``, unless the recipient already has an
    unread one of the same type from the same user: a burst of messages (or
    likes) is one entry in the box, not twenty. Does not commit: the caller
    owns the transaction.

    Args:
        conn: Database connection.
        user_id: Id of the recipient.
        from_user_id: Id of the user who triggered the notification.
        type: One of "like", "unlike", "match", "visit" or "message".
    """
    await conn.execute("""
        INSERT INTO notifications (user_id, from_user_id, type)
        SELECT %s, %s, %s
        WHERE NOT EXISTS (
            SELECT 1 FROM notifications
            WHERE user_id = %s AND from_user_id = %s AND type = %s AND seen = false
        )
    """, (user_id, from_user_id, type, user_id, from_user_id, type))


async def publish_notification(user_id: int, from_user_id: int, type: str, redis: Redis):
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
