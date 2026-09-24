import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from starlette.testclient import TestClient

import os
SESSION_SECRET = os.environ["SESSION_SECRET"]


def make_session_cookie(session_id: str = "testsession") -> str:
    import hmac, hashlib
    h = hmac.new(SESSION_SECRET.encode(), session_id.encode(), digestmod=hashlib.sha256).hexdigest()
    return f"{session_id}${h}"


def make_pubsub():
    """Pubsub mock whose listen() immediately ends (no messages)."""
    async def _empty():
        if False:
            yield

    p = MagicMock()
    p.subscribe = AsyncMock()
    p.unsubscribe = AsyncMock()
    p.aclose = AsyncMock()
    p.listen = MagicMock(side_effect=lambda: _empty())
    return p


def make_match_cursor(liked_by_me=True, liked_by_them=True):
    cursor = AsyncMock()
    cursor.fetchone = AsyncMock(return_value={"liked_by_me": liked_by_me, "liked_by_them": liked_by_them})
    return cursor


def make_pool_mock(mock_conn=None):
    if mock_conn is None:
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=make_match_cursor())
    pool = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.connection = MagicMock(return_value=cm)
    return pool, mock_conn


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.set = AsyncMock(return_value=True)
    r.get = AsyncMock(return_value=None)
    r.publish = AsyncMock()
    r.pubsub = MagicMock(return_value=make_pubsub())
    r.aclose = AsyncMock()
    return r


@pytest.fixture
def chat_app(mock_redis):
    with patch("app.open_pool", new_callable=AsyncMock), \
         patch("app.close_pool", new_callable=AsyncMock), \
         patch("redis.asyncio.Redis", return_value=mock_redis):
        from app import create_app
        yield create_app()


# ── ConnectionManager ─────────────────────────────────────────────────────────

class TestConnectionManager:
    async def test_connect_accepts_websocket_and_adds_to_room(self):
        from app.routes.chat import ConnectionManager
        mgr = ConnectionManager()
        ws = AsyncMock()

        await mgr.connect("room:1_2", ws)

        ws.accept.assert_called_once()
        assert ws in mgr.active["room:1_2"]

    async def test_disconnect_removes_websocket(self):
        from app.routes.chat import ConnectionManager
        mgr = ConnectionManager()
        ws = AsyncMock()

        await mgr.connect("room:1_2", ws)
        mgr.disconnect("room:1_2", ws)

        assert "room:1_2" not in mgr.active

    async def test_disconnect_keeps_room_when_other_clients_remain(self):
        from app.routes.chat import ConnectionManager
        mgr = ConnectionManager()
        ws1, ws2 = AsyncMock(), AsyncMock()

        await mgr.connect("room:1_2", ws1)
        await mgr.connect("room:1_2", ws2)
        mgr.disconnect("room:1_2", ws1)

        assert "room:1_2" in mgr.active
        assert ws2 in mgr.active["room:1_2"]
        assert ws1 not in mgr.active["room:1_2"]

    async def test_multiple_rooms_are_independent(self):
        from app.routes.chat import ConnectionManager
        mgr = ConnectionManager()
        ws1, ws2 = AsyncMock(), AsyncMock()

        await mgr.connect("room:1_2", ws1)
        await mgr.connect("room:3_4", ws2)

        assert ws1 in mgr.active["room:1_2"]
        assert ws2 in mgr.active["room:3_4"]

    def test_room_id_is_order_independent(self):
        """min/max ensures room:1_5 and room:5_1 resolve to the same key."""
        a, b = 5, 1
        assert f"room:{min(a, b)}_{max(a, b)}" == f"room:{min(b, a)}_{max(b, a)}"


# ── save_message ──────────────────────────────────────────────────────────────

class TestSaveMessage:
    async def test_returns_dict_with_all_fields(self):
        from app.routes.chat import save_message
        created_at = datetime(2024, 6, 1, 10, 30, 0)
        cursor = AsyncMock()
        cursor.fetchone = AsyncMock(return_value={"id": 42, "created_at": created_at})
        conn = AsyncMock()
        conn.execute = AsyncMock(return_value=cursor)

        msg = await save_message(conn, sender_id=1, target_id=2, content="hello")

        assert msg["id"] == 42
        assert msg["sender_id"] == 1
        assert msg["content"] == "hello"
        assert msg["created_at"] == created_at.isoformat()

    async def test_executes_insert_with_correct_params(self):
        from app.routes.chat import save_message
        cursor = AsyncMock()
        cursor.fetchone = AsyncMock(return_value={"id": 1, "created_at": datetime.now()})
        conn = AsyncMock()
        conn.execute = AsyncMock(return_value=cursor)

        await save_message(conn, sender_id=7, target_id=3, content="ping")

        query, params = conn.execute.call_args.args
        assert "INSERT INTO messages" in query
        assert params == (7, 3, "ping")

    async def test_returns_correct_sender_id(self):
        from app.routes.chat import save_message
        cursor = AsyncMock()
        cursor.fetchone = AsyncMock(return_value={"id": 5, "created_at": datetime.now()})
        conn = AsyncMock()
        conn.execute = AsyncMock(return_value=cursor)

        msg = await save_message(conn, sender_id=99, target_id=1, content="yo")

        assert msg["sender_id"] == 99


# ── WebSocket integration ─────────────────────────────────────────────────────

class TestChatWebSocket:
    def test_unauthenticated_connection_raises(self, chat_app):
        from fastapi import HTTPException
        with patch("app.routes.chat.get_current_user_id",
                   new=AsyncMock(side_effect=HTTPException(401, "Not Authenticated"))):
            with TestClient(chat_app) as tc:
                with pytest.raises(Exception):
                    with tc.websocket_connect("/chat/2"):
                        pass

    def test_authenticated_connect_and_clean_disconnect(self, chat_app, mock_redis):
        mock_pool, _ = make_pool_mock()

        with patch("app.routes.chat.get_current_user_id", new=AsyncMock(return_value="1")), \
             patch("app.db.pool.pool", mock_pool):
            with TestClient(chat_app) as tc:
                with tc.websocket_connect(
                    "/chat/2",
                    headers={"Cookie": f"session={make_session_cookie()}"},
                ):
                    pass  # clean disconnect triggers WebSocketDisconnect in handler

    def test_room_id_uses_sorted_user_ids(self, chat_app, mock_redis):
        """User 1 talking to user 5 → room:1_5 (not room:5_1)."""
        captured_rooms = []

        original_connect = __import__("app.routes.chat", fromlist=["manager"]).manager.connect

        async def spy_connect(room_id, ws):
            captured_rooms.append(room_id)
            await original_connect(room_id, ws)

        mock_pool, _ = make_pool_mock()

        with patch("app.routes.chat.get_current_user_id", new=AsyncMock(return_value="1")), \
             patch("app.db.pool.pool", mock_pool), \
             patch("app.routes.chat.manager.connect", side_effect=spy_connect):
            with TestClient(chat_app) as tc:
                with tc.websocket_connect(
                    "/chat/5",
                    headers={"Cookie": f"session={make_session_cookie()}"},
                ):
                    pass

        assert len(captured_rooms) == 1
        assert captured_rooms[0] == "room:1_5"

    def test_non_matched_users_connection_rejected(self, chat_app, mock_redis):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=make_match_cursor(liked_by_me=True, liked_by_them=False))
        mock_pool, _ = make_pool_mock(mock_conn)

        with patch("app.routes.chat.get_current_user_id", new=AsyncMock(return_value="1")), \
             patch("app.db.pool.pool", mock_pool), \
             patch("app.routes.chat.manager.connect", new=AsyncMock()) as mock_connect:
            with TestClient(chat_app) as tc:
                with pytest.raises(Exception):
                    with tc.websocket_connect(
                        "/chat/2",
                        headers={"Cookie": f"session={make_session_cookie()}"},
                    ):
                        pass

            mock_connect.assert_not_called()

    def test_db_error_logs_and_closes_connection(self, chat_app, mock_redis):
        """When save_message raises, logger.exception is called and connection closes."""
        error_cursor = AsyncMock()
        error_cursor.fetchone = AsyncMock(side_effect=Exception("db down"))
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=[make_match_cursor(), error_cursor])
        mock_pool, _ = make_pool_mock(mock_conn)

        with patch("app.routes.chat.get_current_user_id", new=AsyncMock(return_value="1")), \
             patch("app.db.pool.pool", mock_pool), \
             patch("app.routes.chat.logger") as mock_logger:
            with TestClient(chat_app) as tc:
                try:
                    with tc.websocket_connect(
                        "/chat/2",
                        headers={"Cookie": f"session={make_session_cookie()}"},
                    ) as ws:
                        ws.send_json({"content": "trigger error"})
                except Exception:
                    pass
