import asyncio
import json
from collections import defaultdict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.security.session import get_current_user_id
from app.db.pool import pool
from app.log import get_logger
from app.routes.notifications import _notify

logger = get_logger(__name__)


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
    with code 1008 (before accepting it) unless both users liked each other.
    Otherwise the socket is accepted, subscribed to the room's Redis channel
    and every message published there is relayed to it. Each JSON frame
    received from the client must carry a ``content`` field: the message is
    saved, the recipient gets a "message" notification and the message is
    published to the room so both participants receive it. The subscription
    and background task are cleaned up when the connection ends.

    Args:
        websocket: The client connection.
        target_id: Id of the other participant.

    Raises:
        HTTPException: If the session cookie is missing or invalid.
        Exception: Unexpected errors are logged, then re-raised.
    """
    redis = websocket.app.state.redis
    sender_id = int(await get_current_user_id(websocket.cookies.get("session"), redis))
    room_id = f"room:{min(sender_id, target_id)}_{max(sender_id, target_id)}"

    async with pool.connection() as conn:
        if not await _is_mutual_match(conn, sender_id, target_id):
            await websocket.close(code=1008)
            return

        await manager.connect(room_id, websocket)
        pubsub = redis.pubsub()
        await pubsub.subscribe(room_id)

        async def listen_pubsub():
            """Relay the room's Redis pub/sub messages to this websocket."""
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await websocket.send_json(json.loads(message["data"]))

        pubsub_task = asyncio.create_task(listen_pubsub())

        try:
            while True:
                data = await websocket.receive_json()
                msg = await save_message(conn, sender_id, target_id, data["content"])
                await _notify(conn, target_id, sender_id, "message", redis)
                await conn.commit()
                await redis.publish(room_id, json.dumps(msg))
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.exception("WebSocket error for user %s", sender_id)
            raise
        finally:
            pubsub_task.cancel()
            await pubsub.unsubscribe(room_id)
            manager.disconnect(room_id, websocket)
