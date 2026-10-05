import asyncio
import json
import threading
import time
import pytest
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from starlette.testclient import TestClient

import os
from app.routes.chat import CONVERSATIONS_LIMIT
SESSION_SECRET = os.environ["SESSION_SECRET"]


def make_session_cookie(session_id: str = "testsession") -> str:
    import hmac, hashlib
    h = hmac.new(SESSION_SECRET.encode(), session_id.encode(), digestmod=hashlib.sha256).hexdigest()
    return f"{session_id}${h}"


def make_pubsub(hang: bool = False):
    """Pubsub mock.

    By default listen() ends immediately (no messages). With hang=True it
    blocks forever instead, until the handler cancels it in its `finally` -
    needed by tests where the receive loop, not the pubsub listener, must
    be the task that finishes first in the handler's
    `asyncio.wait(..., FIRST_COMPLETED)`.
    """
    async def _empty():
        if False:
            yield

    async def _hang():
        await asyncio.Future()
        if False:
            yield

    p = MagicMock()
    p.subscribe = AsyncMock()
    p.unsubscribe = AsyncMock()
    p.aclose = AsyncMock()
    p.listen = MagicMock(side_effect=_hang if hang else _empty)
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
    # lifespan() registers the Lua script off this client and stores the result
    # on app.state; here that yields a stub which always allows. These tests
    # cover chat logic, not the limiter (tests/security/test_rate_limit.py does
    # that, against a real Redis).
    # {allowed, remaining, retry_after} — the shape token_bucket.lua returns.
    r.register_script = MagicMock(return_value=AsyncMock(return_value=[1, 999, 0]))
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

        with patch("app.routes.chat.get_current_user_id", new=AsyncMock(return_value=1)), \
             patch("app.db.pool.pool", mock_pool):
            with TestClient(chat_app) as tc:
                with tc.websocket_connect(
                    "/chat/2",
                    headers={
                        "Cookie": f"session={make_session_cookie()}",
                        "Origin": "http://localhost:5173",
                    },
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

        with patch("app.routes.chat.get_current_user_id", new=AsyncMock(return_value=1)), \
            patch("app.db.pool.pool", mock_pool), \
            patch("app.routes.chat.manager.connect", side_effect=spy_connect):
            with TestClient(chat_app) as tc:
                with tc.websocket_connect(
                    "/chat/5",
                    headers={"Cookie": f"session={make_session_cookie()}",
                            "Origin": "http://localhost:5173",
                    },
                    
                ):
                    pass

        assert len(captured_rooms) == 1
        assert captured_rooms[0] == "room:1_5"

    def test_non_matched_users_connection_rejected(self, chat_app, mock_redis):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=make_match_cursor(liked_by_me=True, liked_by_them=False))
        mock_pool, _ = make_pool_mock(mock_conn)

        with patch("app.routes.chat.get_current_user_id", new=AsyncMock(return_value=1)), \
             patch("app.db.pool.pool", mock_pool), \
             patch("app.routes.chat.manager.connect", new=AsyncMock()) as mock_connect:
            with TestClient(chat_app) as tc:
                with pytest.raises(Exception):
                    with tc.websocket_connect(
                        "/chat/2",
                        headers={"Cookie": f"session={make_session_cookie()}",
                                "Origin": "http://localhost:5173",
                        },
                    ):
                        pass

            mock_connect.assert_not_called()

    def test_db_error_logs_and_closes_connection(self, chat_app, mock_redis):
        """When save_message raises, logger.exception is called and the
        room is cleaned up.

        Swaps in a hanging pubsub (see make_pubsub) because the default
        one's listen() ends immediately, which would otherwise win the
        handler's FIRST_COMPLETED race before the client's message is
        ever read.
        """
        mock_redis.pubsub = MagicMock(return_value=make_pubsub(hang=True))

        error_cursor = AsyncMock()
        error_cursor.fetchone = AsyncMock(side_effect=Exception("db down"))
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=[make_match_cursor(), error_cursor])
        mock_pool, _ = make_pool_mock(mock_conn)

        with patch("app.routes.chat.get_current_user_id", new=AsyncMock(return_value=1)), \
             patch("app.db.pool.pool", mock_pool), \
             patch("app.routes.chat.logger") as mock_logger:
            with TestClient(chat_app) as tc:
                # Whether the handler's re-raised error reaches the client
                # before or after it closes its end is a race outside this
                # test's control; either way logger.exception and cleanup
                # below are what actually matter.
                try:
                    with tc.websocket_connect(
                        "/chat/2",
                        headers={
                            "Cookie": f"session={make_session_cookie()}",
                            "Origin": "http://localhost:5173",
                        },
                    ) as ws:
                        ws.send_json({"content": "trigger error"})
                except Exception:
                    pass

        mock_logger.exception.assert_called_once()
        args, kwargs = mock_logger.exception.call_args
        assert args == ("WebSocket error for user %s", 1)
        assert str(kwargs["exc_info"]) == "db down"

        from app.routes.chat import manager
        assert "room:1_2" not in manager.active


# ── input validation ──────────────────────────────────────────────────────────

WS_HEADERS = {
    "Cookie": f"session={make_session_cookie()}",
    "Origin": "http://localhost:5173",
}


class TestParseChatFrame:
    def test_valid_frame_returns_stripped_content(self):
        from app.routes.chat import parse_chat_frame
        assert parse_chat_frame('{"content": "  hello  "}') == "hello"

    def test_newlines_and_unicode_are_kept(self):
        from app.routes.chat import parse_chat_frame
        assert parse_chat_frame('{"content": "salut\\nça va 👋"}') == "salut\nça va 👋"

    def test_extra_keys_are_ignored(self):
        from app.routes.chat import parse_chat_frame
        assert parse_chat_frame('{"content": "hi", "sender_id": 99}') == "hi"

    def test_content_at_the_limit_is_accepted(self):
        from app.routes.chat import parse_chat_frame
        from app.validation import MAX_MESSAGE
        assert len(parse_chat_frame(json.dumps({"content": "a" * MAX_MESSAGE}))) == MAX_MESSAGE

    @pytest.mark.parametrize("raw", [
        "not json", "", "{", "[]", "[1]", '"text"', "42", "null", "true",
        '{}', '{"content": null}', '{"content": 5}', '{"content": ["a"]}', '{"content": {"a": 1}}',
        '{"content": ""}', '{"content": "   "}',
        '{"content": "a\\u0000b"}', '{"content": "\\ud800"}', '{"content": "a\\u0001b"}',
        '{"content": NaN}',
        "[" * 100_000,
    ])
    def test_bad_frame_raises_400(self, raw):
        from fastapi import HTTPException
        from app.routes.chat import parse_chat_frame
        with pytest.raises(HTTPException) as exc:
            parse_chat_frame(raw)
        assert exc.value.status_code == 400

    def test_oversized_content_raises_400(self):
        from fastapi import HTTPException
        from app.routes.chat import parse_chat_frame
        from app.validation import MAX_MESSAGE
        with pytest.raises(HTTPException) as exc:
            parse_chat_frame(json.dumps({"content": "a" * (MAX_MESSAGE + 1)}))
        assert exc.value.status_code == 400
        assert str(MAX_MESSAGE) in exc.value.detail

    def test_two_megabyte_message_is_refused(self):
        from fastapi import HTTPException
        from app.routes.chat import parse_chat_frame
        with pytest.raises(HTTPException):
            parse_chat_frame(json.dumps({"content": "a" * 2_000_000}))


@contextmanager
def open_chat(chat_app, mock_redis, mock_conn=None):
    """Connect to ``/chat/2`` as user 1 and leave the socket cleanly.

    The pubsub never ends (``hang=True``), so the handler only finishes when
    the client disconnects. Starlette's ``WebSocketTestSession`` cancels the
    app the moment its ``with`` block exits, without waiting for it: a
    handler still in its ``finally`` cleanup would be cancelled halfway and
    the exit raises ``CancelledError``. So the client disconnects first and
    waits for the handler's own last await (``pubsub.aclose``) before the
    block is left.

    Yields:
        ``(websocket, mock_conn)``.
    """
    if mock_conn is None:
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=make_match_cursor())
    mock_pool, _ = make_pool_mock(mock_conn)

    cleaned_up = threading.Event()
    pubsub = make_pubsub(hang=True)
    pubsub.aclose = AsyncMock(side_effect=lambda: cleaned_up.set())
    mock_redis.pubsub = MagicMock(return_value=pubsub)

    with patch("app.routes.chat.get_current_user_id", new=AsyncMock(return_value=1)), \
         patch("app.db.pool.pool", mock_pool):
        with TestClient(chat_app) as tc:
            with tc.websocket_connect("/chat/2", headers=WS_HEADERS) as ws:
                yield ws, mock_conn
                ws.close()
                assert cleaned_up.wait(timeout=5), "chat handler did not finish its cleanup"


class TestChatWebSocketInput:
    def test_bad_frames_get_an_error_frame_and_the_socket_stays_open(self, chat_app, mock_redis):
        bad_frames = [
            "not json",
            "[]",
            "42",
            "{}",
            '{"content": 5}',
            '{"content": ""}',
            '{"content": "a\\u0000b"}',
            '{"content": "\\ud800"}',
            json.dumps({"content": "a" * 1001}),
            json.dumps({"content": "a" * 2_000_000}),
        ]

        with open_chat(chat_app, mock_redis) as (ws, mock_conn):
            for frame in bad_frames:
                ws.send_text(frame)
                reply = ws.receive_json()
                assert reply["type"] == "error"
                assert reply["detail"]

        # Only the mutual-match lookup ran: not one bad frame reached the messages table.
        assert mock_conn.execute.call_count == 1

    def test_binary_frame_gets_an_error_frame(self, chat_app, mock_redis):
        with open_chat(chat_app, mock_redis) as (ws, mock_conn):
            ws.send_bytes(b"\x00\x01\x02")
            reply = ws.receive_json()
            assert reply["type"] == "error"
            assert "text" in reply["detail"]
            ws.send_text("not json")  # still alive after the binary frame
            assert ws.receive_json()["type"] == "error"

        assert mock_conn.execute.call_count == 1

    def test_error_frame_goes_to_the_sender_only(self, chat_app, mock_redis):
        with open_chat(chat_app, mock_redis) as (ws, _):
            ws.send_text("garbage")
            assert ws.receive_json()["type"] == "error"

        mock_redis.publish.assert_not_called()

    def test_valid_message_after_a_bad_one_is_saved_once_and_stripped(self, chat_app, mock_redis):
        insert_cursor = AsyncMock()
        insert_cursor.fetchone = AsyncMock(return_value={"id": 5, "created_at": datetime(2024, 1, 1)})
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=[make_match_cursor(), insert_cursor, AsyncMock()])

        with open_chat(chat_app, mock_redis, mock_conn) as (ws, _):
            ws.send_text("garbage")
            assert ws.receive_json()["type"] == "error"
            ws.send_json({"content": "  hi there  "})
            # The valid frame ends with two publishes (notification + room message).
            deadline = time.monotonic() + 5
            while mock_redis.publish.call_count < 2 and time.monotonic() < deadline:
                time.sleep(0.01)

        assert mock_redis.publish.call_count == 2
        insert_call = mock_conn.execute.call_args_list[1]
        assert "INSERT INTO messages" in insert_call.args[0]
        assert insert_call.args[1] == (1, 2, "hi there")

    def test_every_frame_goes_through_the_rate_limiter_even_invalid_and_binary_ones(self, chat_app, mock_redis):
        """A garbage or binary frame still costs the server a reply, so it must count."""
        limiter = AsyncMock(return_value=(True, 0))

        with patch("app.routes.chat.check_chat_message_limit", new=limiter):
            with open_chat(chat_app, mock_redis) as (ws, _):
                ws.send_text("garbage")
                assert ws.receive_json()["type"] == "error"
                ws.send_bytes(b"\x00\x01")
                assert ws.receive_json()["type"] == "error"
                ws.send_text("{}")
                assert ws.receive_json()["type"] == "error"

        assert limiter.await_count == 3

    @pytest.mark.parametrize("target_id", [99999999999999999999, 2**31, 0, -1])
    def test_impossible_target_id_is_closed_before_accept(self, chat_app, mock_redis, target_id):
        from starlette.websockets import WebSocketDisconnect
        mock_pool, mock_conn = make_pool_mock()
        auth = AsyncMock(return_value="1")

        with patch("app.routes.chat.get_current_user_id", new=auth), \
            patch("app.db.pool.pool", mock_pool):
            with TestClient(chat_app) as tc:
                with pytest.raises(WebSocketDisconnect) as exc:
                    with tc.websocket_connect(f"/chat/{target_id}", headers=WS_HEADERS):
                        pass

        assert exc.value.code == 1008
        auth.assert_not_called()
        mock_conn.execute.assert_not_called()


class TestChatRateLimit:
    def _limited_chat(self, chat_app, mock_redis, times):
        """Open a chat whose limiter allows exactly ``times`` messages, then refuses."""
        mock_redis.get = AsyncMock(return_value="1")
        limiter = AsyncMock(side_effect=[(True, 0)] * times + [(False, 7)] * 20)
        cursor = AsyncMock()
        cursor.fetchone = AsyncMock(return_value={
            "liked_by_me": True, "liked_by_them": True, "id": 5, "created_at": datetime(2024, 1, 1),
        })
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=cursor)
        return limiter, mock_conn

    def test_messages_over_the_limit_are_not_saved(self, chat_app, mock_redis):
        """Frames are handled in order, so with a budget of 2 exactly the first two are saved."""
        limiter, mock_conn = self._limited_chat(chat_app, mock_redis, times=2)

        with patch("app.routes.chat.check_chat_message_limit", new=limiter):
            with open_chat(chat_app, mock_redis, mock_conn) as (ws, _):
                for text in ("one", "two", "three", "four"):
                    ws.send_json({"content": text})

        saved = [c.args[1][2] for c in mock_conn.execute.call_args_list if "INSERT INTO messages" in c.args[0]]
        assert saved == ["one", "two"]

    def test_the_first_messages_within_the_budget_are_all_saved(self, chat_app, mock_redis):
        limiter, mock_conn = self._limited_chat(chat_app, mock_redis, times=3)

        with patch("app.routes.chat.check_chat_message_limit", new=limiter):
            with open_chat(chat_app, mock_redis, mock_conn) as (ws, _):
                for text in ("one", "two", "three"):
                    ws.send_json({"content": text})

        saved = [c.args[1][2] for c in mock_conn.execute.call_args_list if "INSERT INTO messages" in c.args[0]]
        assert saved == ["one", "two", "three"]


def make_conversation_row(user_id=2, message_id=None, sender_id=None, unread=0, photo_position=1):
    has_message = message_id is not None
    return {
        "id": user_id, "first_name": "Bob", "is_online": True, "last_seen": None,
        "photo_position": photo_position,
        "message_id": message_id, "sender_id": sender_id if has_message else None,
        "content": "hi" if has_message else None,
        "created_at": datetime(2026, 10, 3, 10, 12) if has_message else None,
        "unread_count": unread,
    }


class TestGetConversations:
    async def test_returns_conversations_in_contract_shape(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        cursor = AsyncMock()
        cursor.fetchall = AsyncMock(return_value=[
            make_conversation_row(2, message_id=88, sender_id=2, unread=2),
            make_conversation_row(3, photo_position=None),
        ])
        mock_db.execute = AsyncMock(return_value=cursor)

        res = await auth_client.get("/chat/conversations")

        assert res.status_code == 200
        first, second = res.json()
        assert first == {
            "user": {"id": 2, "first_name": "Bob", "is_online": True, "last_seen": None,
                     "photo": "/users/2/photos/1"},
            "last_message": {"id": 88, "sender_id": 2, "content": "hi",
                             "created_at": "2026-10-03T10:12:00"},
            "unread_count": 2,
        }
        assert second["last_message"] is None
        assert second["user"]["photo"] is None
        assert second["unread_count"] == 0

    async def test_runs_a_single_query_for_the_session_user(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        cursor = AsyncMock()
        cursor.fetchall = AsyncMock(return_value=[])
        mock_db.execute = AsyncMock(return_value=cursor)

        await auth_client.get("/chat/conversations")

        mock_db.execute.assert_awaited_once()
        assert mock_db.execute.call_args.args[1] == {"me": 1, "limit": CONVERSATIONS_LIMIT}

    async def test_no_match_returns_empty_list(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        cursor = AsyncMock()
        cursor.fetchall = AsyncMock(return_value=[])
        mock_db.execute = AsyncMock(return_value=cursor)

        res = await auth_client.get("/chat/conversations")

        assert res.status_code == 200
        assert res.json() == []

    async def test_no_cookie_returns_401(self, client, mock_db):
        res = await client.get("/chat/conversations")
        assert res.status_code == 401
        mock_db.execute.assert_not_called()


def make_message_row(message_id, sender_id=2, minute=0):
    return {"id": message_id, "sender_id": sender_id, "content": f"m{message_id}",
            "created_at": datetime(2026, 10, 3, 10, minute)}


class TestGetMessages:
    async def test_returns_page_in_websocket_shape(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        history = AsyncMock()
        history.fetchall = AsyncMock(return_value=[make_message_row(2, 1, 1), make_message_row(1, 2, 0)])
        mock_db.execute = AsyncMock(side_effect=[make_match_cursor(), history])

        res = await auth_client.get("/chat/2/messages")

        assert res.status_code == 200
        assert res.json() == {
            "messages": [
                {"id": 2, "sender_id": 1, "content": "m2", "created_at": "2026-10-03T10:01:00"},
                {"id": 1, "sender_id": 2, "content": "m1", "created_at": "2026-10-03T10:00:00"},
            ],
            "has_more": False,
        }

    async def test_extra_row_sets_has_more_and_is_dropped(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        history = AsyncMock()
        history.fetchall = AsyncMock(return_value=[make_message_row(i) for i in (3, 2, 1)])
        mock_db.execute = AsyncMock(side_effect=[make_match_cursor(), history])

        res = await auth_client.get("/chat/2/messages?limit=2")

        body = res.json()
        assert body["has_more"] is True
        assert [m["id"] for m in body["messages"]] == [3, 2]
        assert mock_db.execute.call_args.args[1][-1] == 3  # LIMIT limit + 1

    async def test_before_and_pair_are_passed_to_query(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        history = AsyncMock()
        history.fetchall = AsyncMock(return_value=[])
        mock_db.execute = AsyncMock(side_effect=[make_match_cursor(), history])

        await auth_client.get("/chat/7/messages?before=50")

        assert mock_db.execute.call_args.args[1] == (1, 7, 50, 50, 31)

    async def test_not_a_match_is_403(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_match_cursor(liked_by_them=False))

        res = await auth_client.get("/chat/2/messages")

        assert res.status_code == 403
        mock_db.execute.assert_awaited_once()  # only the match check

    async def test_no_cookie_returns_401(self, client, mock_db):
        res = await client.get("/chat/2/messages")
        assert res.status_code == 401
        mock_db.execute.assert_not_called()


class TestMarkSeen:
    async def test_marks_messages_and_commits(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        update = AsyncMock()
        update.rowcount = 3
        mock_db.execute = AsyncMock(side_effect=[make_match_cursor(), update, AsyncMock()])

        res = await auth_client.post("/chat/2/seen")

        assert res.status_code == 200
        assert res.json() == {"updated": 3}
        assert mock_db.execute.call_args_list[1].args[1] == (2, 1)  # (sender = them, receiver = me)
        mock_db.commit.assert_awaited_once()

    async def test_also_marks_the_message_notifications_from_that_user_as_seen(self, auth_client, mock_db, mock_redis):
        """Otherwise the bell keeps announcing "X sent you a message" for messages just read."""
        mock_redis.get = AsyncMock(return_value="1")
        update = AsyncMock()
        update.rowcount = 2
        mock_db.execute = AsyncMock(side_effect=[make_match_cursor(), update, AsyncMock()])

        res = await auth_client.post("/chat/2/seen")

        assert res.json() == {"updated": 2}  # still the number of messages, not notifications
        query, params = mock_db.execute.call_args_list[2].args
        assert "UPDATE notifications SET seen = true" in query
        assert "type = 'message'" in query
        assert params == (1, 2)  # (me, the sender)
        assert [c[0] for c in mock_db.mock_calls if c[0] in ("execute", "commit")] == ["execute", "execute", "execute", "commit"]

    async def test_not_a_match_is_403_and_writes_nothing(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_match_cursor(liked_by_me=False))

        res = await auth_client.post("/chat/2/seen")

        assert res.status_code == 403
        mock_db.commit.assert_not_awaited()

    async def test_no_cookie_returns_401(self, client, mock_db):
        res = await client.post("/chat/2/seen")
        assert res.status_code == 401
        mock_db.execute.assert_not_called()
