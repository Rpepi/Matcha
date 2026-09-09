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
    def __init__(self):
        self.active: defaultdict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, room_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active[room_id].append(websocket)

    def disconnect(self, room_id: str, websocket: WebSocket):
        self.active[room_id].remove(websocket)
        if not self.active.get(room_id):
            del self.active[room_id]


manager = ConnectionManager()
router = APIRouter()


async def _is_mutual_match(conn, a: int, b: int) -> bool:
    cursor = await conn.execute("""
        SELECT
            EXISTS (SELECT 1 FROM likes WHERE liker_id = %s AND liked_id = %s) AS liked_by_me,
            EXISTS (SELECT 1 FROM likes WHERE liker_id = %s AND liked_id = %s) AS liked_by_them
    """, (a, b, b, a))
    row = await cursor.fetchone()
    return row["liked_by_me"] and row["liked_by_them"]


async def save_message(conn, sender_id: int, target_id: int, content: str) -> dict:
    cursor = await conn.execute(
        "INSERT INTO messages (sender_id, receiver_id, content) VALUES (%s, %s, %s) RETURNING id, created_at",
        (sender_id, target_id, content),
    )
    row = await cursor.fetchone()
    return {"id": row["id"], "sender_id": sender_id, "content": content, "created_at": row["created_at"].isoformat()}


@router.websocket("/chat/{target_id}")
async def chat_setup(websocket: WebSocket, target_id: int):
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
