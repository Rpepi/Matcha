import asyncio
import json
import os
from psycopg import AsyncConnection
from collections import defaultdict
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends, Request, Response
from redis.asyncio import Redis
from starlette.websockets import WebSocketState
from app.security.session import get_current_user_id
from app.security.rate_limiter.rate_limit import check_chat_message_limit
from app.validation import clean_str, parse_int_param, valid_target_id, MAX_MESSAGE, MAX_ID
from app.db import pool as pool_module
from app.db.dependencies import get_db
from app.cache.dependencies import get_redis
from app.log import get_logger
from app.security.rate_limiter.rate_limit import rate_limit

from app.routes.notifications import insert_notification, publish_notification


logger = get_logger(__name__)

HISTORY_DEFAULT_LIMIT = 30
HISTORY_MAX_LIMIT = 50
CONVERSATIONS_LIMIT = 200

FRONTEND_URL = os.getenv("FRONTEND_URL")

if not FRONTEND_URL:
    raise RuntimeError("env variable missing or not set")


def room_id_for(a: int | str, b: int | str) -> str:
    """Build the deterministic Redis/manager room id for a pair of users.

    Args:
        a: Id of the first user.
        b: Id of the second user.

    Returns:
        ``room:<min_id>_<max_id>`` so both orderings resolve to the same room.
    """
    a, b = int(a), int(b)
    return f"room:{min(a, b)}_{max(a, b)}"


async def publish_unmatch(a: int | str, b: int | str, redis: Redis) -> None:
    """Tell any open chat websocket between two users that they unmatched.

    Called by ``routes/users.py`` after an unlike or a block. A listener on
    the room channel (see ``listen_pubsub`` below) reacts by closing the
    socket, even if neither user sends another chat message.

    Args:
        a: Id of the first user.
        b: Id of the second user.
        redis: Redis client used to publish the event.
    """
    await redis.publish(room_id_for(a, b), json.dumps({"type": "unmatch"}))


class ConnectionManager:
    """Track the WebSocket connections open in each chat room.

    Rooms are identified by ``room:<min_id>_<max_id>`` and kept in the
    memory of the current process.

    Attributes:
        active: Mapping of room id to the list of its connected websockets.
    """
    def __init__(self):
        """Start with no open room."""
        self.active: defaultdict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, room_id: str, websocket: WebSocket):
        """Accept a WebSocket and register it in a room.

        Args:
            room_id: Id of the room to join.
            websocket: The client connection to accept.
        """
        await websocket.accept()
        self.active[room_id].append(websocket)

    def disconnect(self, room_id: str, websocket: WebSocket):
        """Unregister a WebSocket, dropping the room once it is empty.

        Args:
            room_id: Id of the room to leave.
            websocket: The client connection to remove.

        Raises:
            ValueError: If the websocket is not registered in that room.
        """
        self.active[room_id].remove(websocket)
        if not self.active.get(room_id):
            del self.active[room_id]


manager = ConnectionManager()
router = APIRouter()


async def _is_mutual_match(conn, a: int, b: int) -> bool:
    """Check whether two users have liked each other.

    Args:
        conn: Database connection.
        a: Id of the first user.
        b: Id of the second user.

    Returns:
        True if both a -> b and b -> a likes exist.
    """
    cursor = await conn.execute("""
        SELECT
            EXISTS (SELECT 1 FROM likes WHERE liker_id = %s AND liked_id = %s) AS liked_by_me,
            EXISTS (SELECT 1 FROM likes WHERE liker_id = %s AND liked_id = %s) AS liked_by_them
    """, (a, b, b, a))
    row = await cursor.fetchone()
    return row["liked_by_me"] and row["liked_by_them"]


def parse_chat_frame(raw: str) -> str:
    """Validate one text frame sent by a chat client.

    The frame must be a JSON object whose ``content`` is a string of at most
    ``MAX_MESSAGE`` characters without control characters (other than
    newlines). Surrounding whitespace is stripped.

    Args:
        raw: The text of the frame.

    Returns:
        The message content to save.

    Raises:
        HTTPException: 400 if the frame is not valid JSON, not an object, or
            its ``content`` is missing or unacceptable.
    """
    try:
        data = json.loads(raw)
    except (ValueError, RecursionError):
        raise HTTPException(status_code=400, detail="message must be valid JSON")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="message must be a JSON object")
    return clean_str(data.get("content"), "content", MAX_MESSAGE, multiline=True)


async def save_message(conn, sender_id: int, target_id: int, content: str) -> dict:
    """Insert a chat message. Does not commit.

    Args:
        conn: Database connection.
        sender_id: Id of the author.
        target_id: Id of the recipient.
        content: Message text.

    Returns:
        A dict with ``id``, ``sender_id``, ``content`` and ``created_at``
        (ISO 8601 string).
    """
    cursor = await conn.execute(
        "INSERT INTO messages (sender_id, receiver_id, content) VALUES (%s, %s, %s) RETURNING id, created_at",
        (sender_id, target_id, content),
    )
    row = await cursor.fetchone()
    return {"id": row["id"], "sender_id": sender_id, "content": content, "created_at": row["created_at"].isoformat()}


@router.websocket("/chat/{target_id}")
async def chat_setup(websocket: WebSocket, target_id: int):
    """WebSocket endpoint for a one-to-one chat between matched users.

    Authenticates the user from the session cookie and closes the socket
    with code 1008 (before accepting it) if ``target_id`` cannot be a user
    id or unless both users liked each other.
    Otherwise the socket is accepted, subscribed to the room's Redis channel
    and every message published there is relayed to it. Each text frame
    received from the client must be a JSON object with a ``content``
    string (see ``parse_chat_frame``): the message is
    saved, the recipient gets a "message" notification and the message is
    published to the room so both participants receive it. A frame that
    fails validation is answered with ``{"type": "error", "detail": ...}``
    to the sender only and the socket stays open. If either user
    unlikes or blocks the other, ``routes/users.py`` publishes an "unmatch"
    event on the same room channel (see ``publish_unmatch``), which closes
    this socket even if the client stays silent. Subscription and background
    tasks are cleaned up when the connection ends, however it ends.

    Args:
        websocket: The client connection.
        target_id: Id of the other participant.

    Raises:
        HTTPException: If the session cookie is missing or invalid.
        Exception: Unexpected errors are logged, then re-raised.
    """
    if websocket.headers.get("origin") != FRONTEND_URL:
        await websocket.close(code=1008)
        return
    if not 1 <= target_id <= MAX_ID:
        await websocket.close(code=1008)
        return
    redis = websocket.app.state.redis
    sender_id = await get_current_user_id(websocket.cookies.get("session"), redis)
    room_id = room_id_for(sender_id, target_id)

    async with pool_module.pool.connection() as conn:
        if not await _is_mutual_match(conn, sender_id, target_id):
            await websocket.close(code=1008)
            return

    await manager.connect(room_id, websocket)
    pubsub = redis.pubsub()
    await pubsub.subscribe(room_id)

    async def listen_pubsub():
        """Relay chat messages to this websocket; return on an unmatch event."""
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            event = json.loads(message["data"])
            if event["type"] == "unmatch":
                return
            await websocket.send_json(event["data"])

    async def receive_loop():
        """Read chat messages from the client and broadcast them to the room.

        A frame that is not valid is answered with an ``{"type": "error"}``
        frame to the sender only; the socket stays open.
        """
        while True:
            try:
                raw = await websocket.receive_text()
            except KeyError:  # binary frame: it has no "text" entry
                raw = None
            # Every frame counts against the limit, well-formed or not: an
            # invalid or binary frame still costs a reply. Over budget, the
            # sender is told to slow down and the socket stays open — the same
            # treatment a malformed frame gets.
            allowed, retry_after = await check_chat_message_limit(websocket, sender_id)
            if not allowed:
                await websocket.send_json({
                    "type": "error",
                    "detail": f"too many messages, retry in {retry_after}s",
                })
                continue
            if raw is None:
                await websocket.send_json({"type": "error", "detail": "only text frames are supported"})
                continue
            try:
                content = parse_chat_frame(raw)
            except HTTPException as e:
                await websocket.send_json({"type": "error", "detail": e.detail})
                continue
            async with pool_module.pool.connection() as conn:
                msg = await save_message(conn, sender_id, target_id, content)
                await insert_notification(conn, target_id, sender_id, "message")
                await conn.commit()
            await publish_notification(target_id, sender_id, "message", redis)
            await redis.publish(room_id, json.dumps({"type": "message", "data": msg}))

    pubsub_task = asyncio.create_task(listen_pubsub())
    receive_task = asyncio.create_task(receive_loop())
    tasks = {pubsub_task, receive_task}

    error: Exception | None = None
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            exc = task.exception()
            if exc is None or isinstance(exc, WebSocketDisconnect):
                continue  # normal exit: client disconnected, or the room's pubsub ended cleanly (unmatch)
            logger.exception("WebSocket error for user %s", sender_id, exc_info=exc)
            error = exc
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await pubsub.unsubscribe(room_id)
        await pubsub.aclose()
        manager.disconnect(room_id, websocket)
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()

    if error is not None:
        raise error


CONVERSATIONS_SQL = """
    SELECT u.id, u.first_name, u.is_online, u.last_seen,
           (SELECT position FROM photos
            WHERE user_id = u.id AND is_profile = true LIMIT 1) AS photo_position,
           lm.id AS message_id, lm.sender_id, lm.content, lm.created_at,
           unread.count AS unread_count
    FROM likes mine
    JOIN likes theirs ON theirs.liker_id = mine.liked_id AND theirs.liked_id = mine.liker_id
    JOIN users u ON u.id = mine.liked_id
    LEFT JOIN LATERAL (
        SELECT id, sender_id, content, created_at
        FROM messages
        WHERE LEAST(sender_id, receiver_id) = LEAST(%(me)s, u.id)
          AND GREATEST(sender_id, receiver_id) = GREATEST(%(me)s, u.id)
        ORDER BY id DESC
        LIMIT 1
    ) lm ON true
    CROSS JOIN LATERAL (
        SELECT COUNT(*)::int AS count
        FROM messages
        WHERE sender_id = u.id AND receiver_id = %(me)s AND seen = false
    ) unread
    WHERE mine.liker_id = %(me)s
      AND NOT EXISTS (
          SELECT 1 FROM blocks b
          WHERE (b.blocker_id = %(me)s AND b.blocked_id = u.id)
             OR (b.blocker_id = u.id AND b.blocked_id = %(me)s)
      )
    ORDER BY lm.id DESC NULLS LAST, u.first_name, u.id
    LIMIT %(limit)s
"""


@router.get("/chat/conversations", dependencies=[Depends(rate_limit("chat-conversations", limit=30, seconds=60, burst=10, by="account"))])
async def get_conversations(request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """List the current user's conversations, most recently active first.

    A conversation exists for every mutual match that is not blocked in
    either direction, including matches with no message yet. Everything is
    fetched in one query: the match, the other user's profile data, the last
    message of the pair and the number of unread messages they sent.

    Args:
        request: Incoming request, carrying the ``session`` cookie.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        A list of dicts with ``user`` (``id``, ``first_name``, ``is_online``,
        ``last_seen`` and ``photo``, a ``/users/{id}/photos/{position}`` path
        or None), ``last_message`` (``id``, ``sender_id``, ``content`` and
        ``created_at``, or None when nothing was sent yet) and
        ``unread_count``. Conversations without messages come last. At most
        ``CONVERSATIONS_LIMIT`` are returned.

    Raises:
        HTTPException: 401 if not authenticated.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    cursor = await conn.execute(CONVERSATIONS_SQL, {"me": user_id, "limit": CONVERSATIONS_LIMIT})
    rows = await cursor.fetchall()

    return [
        {
            "user": {
                "id": row["id"],
                "first_name": row["first_name"],
                "is_online": row["is_online"],
                "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None,
                "photo": (
                    f"/users/{row['id']}/photos/{row['photo_position']}"
                    if row["photo_position"] is not None else None
                ),
            },
            "last_message": None if row["message_id"] is None else {
                "id": row["message_id"],
                "sender_id": row["sender_id"],
                "content": row["content"],
                "created_at": row["created_at"].isoformat(),
            },
            "unread_count": row["unread_count"],
        }
        for row in rows
    ]


@router.get("/chat/{target_id}/messages", dependencies=[Depends(valid_target_id), Depends(rate_limit("chat-history", limit=60, seconds=60, burst=20, by="account"))])
async def get_messages(target_id: int, request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Return one page of the conversation with a matched user, newest first.

    Query parameters:
        before: Only messages with an id lower than this one, to get the
            page after the one already loaded.
        limit: Page size, 1 to ``HISTORY_MAX_LIMIT`` (default
            ``HISTORY_DEFAULT_LIMIT``).

    Args:
        target_id: Id of the other participant.
        request: Incoming request, carrying the ``session`` cookie.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        A dict with ``messages`` (dicts with ``id``, ``sender_id``,
        ``content`` and ``created_at``, the same shape as a websocket
        message) and ``has_more``, True if older messages remain.

    Raises:
        HTTPException: 400 on a bad query parameter, 401 if not
            authenticated, 403 unless both users liked each other.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)
    before = parse_int_param(request.query_params.get("before"), "before", 1, MAX_ID)
    limit = parse_int_param(request.query_params.get("limit"), "limit", 1, HISTORY_MAX_LIMIT) or HISTORY_DEFAULT_LIMIT

    if not await _is_mutual_match(conn, user_id, target_id):
        raise HTTPException(status_code=403, detail="you can only chat with a match")

    # Ordered and paginated on the same key (id grows with every insert, so it is also
    # chronological). One row more than asked: if it comes back, an older page exists.
    cursor = await conn.execute("""
        SELECT id, sender_id, content, created_at
        FROM messages
        WHERE LEAST(sender_id, receiver_id) = %s
          AND GREATEST(sender_id, receiver_id) = %s
          AND (%s::int IS NULL OR id < %s::int)
        ORDER BY id DESC
        LIMIT %s
    """, (min(user_id, target_id), max(user_id, target_id), before, before, limit + 1))
    rows = await cursor.fetchall()

    return {
        "messages": [{**row, "created_at": row["created_at"].isoformat()} for row in rows[:limit]],
        "has_more": len(rows) > limit,
    }


@router.post("/chat/{target_id}/seen", dependencies=[Depends(valid_target_id), Depends(rate_limit("chat-seen", limit=120, seconds=60, burst=10, by="account"))])
async def mark_seen(target_id: int, request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Mark every message received from a matched user as seen.

    The "message" notifications from that user are marked as seen too.

    Args:
        target_id: Id of the other participant, the author of the messages.
        request: Incoming request, carrying the ``session`` cookie.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        ``{"updated": n}``, the number of messages that were unseen.

    Raises:
        HTTPException: 401 if not authenticated, 403 unless both users
            liked each other.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    if not await _is_mutual_match(conn, user_id, target_id):
        raise HTTPException(status_code=403, detail="you can only chat with a match")

    cursor = await conn.execute(
        "UPDATE messages SET seen = true WHERE sender_id = %s AND receiver_id = %s AND seen = false",
        (target_id, user_id),
    )
    updated = cursor.rowcount
    # Reading the conversation also reads its "message" notification, or the bell would
    # keep announcing messages the user has just read.
    await conn.execute(
        "UPDATE notifications SET seen = true WHERE user_id = %s AND from_user_id = %s AND type = 'message' AND seen = false",
        (user_id, target_id),
    )
    await conn.commit()
    return {"updated": updated}
