import json
from datetime import datetime
from types import SimpleNamespace
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from starlette.testclient import TestClient
import os, hmac, hashlib

SESSION_SECRET = os.environ.get("SESSION_SECRET", "test-secret-key-for-testing-only-32b")


def make_session_cookie(session_id: str = "testsession") -> str:
    h = hmac.new(SESSION_SECRET.encode(), session_id.encode(), digestmod=hashlib.sha256).hexdigest()
    return f"{session_id}${h}"


def make_pubsub(messages=None):
    """Pubsub mock whose listen() yields given messages then stops."""
    messages = messages or []

    async def _listen():
        for msg in messages:
            yield msg

    p = MagicMock()
    p.subscribe = AsyncMock()
    p.unsubscribe = AsyncMock()
    p.aclose = AsyncMock()
    p.listen = MagicMock(side_effect=lambda: _listen())
    return p


@pytest.fixture(autouse=True)
def presence():
    """The stream records presence in Redis and PostgreSQL; the tests below are about
    the stream itself, so both calls are stubbed (app/presence.py has its own tests)."""
    with patch("app.routes.notifications.user_connected", new=AsyncMock()) as connected, \
         patch("app.routes.notifications.user_disconnected", new=AsyncMock()) as disconnected:
        yield SimpleNamespace(connected=connected, disconnected=disconnected)


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.publish = AsyncMock()
    r.pubsub = MagicMock(return_value=make_pubsub())
    r.get = AsyncMock(return_value=None)
    r.aclose = AsyncMock()
    return r


@pytest.fixture
def mock_db():
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=AsyncMock())
    return conn


@pytest.fixture
def notif_app(mock_redis, mock_db):
    """Minimal FastAPI app with only the notifications router registered."""
    from fastapi import FastAPI
    from app.routes.notifications import router as notif_router
    from app.db.dependencies import get_db
    from app.cache.dependencies import get_redis

    app = FastAPI()
    app.include_router(notif_router)
    app.state.redis = mock_redis

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: mock_redis
    return app


# ── the SSE stream and the connection pool ───────────────────────────────────

class TestStreamDoesNotHoldDatabaseConnection:
    def test_stream_route_has_no_get_db_dependency(self, notif_app):
        """The stream stays open as long as the page does. If it borrowed a pooled
        connection (max 5) a few open tabs would freeze every endpoint that
        touches the database."""
        from app.db.dependencies import get_db

        def calls(dependant):
            for dep in dependant.dependencies:
                yield dep.call
                yield from calls(dep)

        def find_route(app, path):
            # include_router wraps the router on this FastAPI version (see test_rate_limits.flatten)
            for route in app.routes:
                if getattr(route, "path", None) == path:
                    return route
                for inner in getattr(getattr(route, "original_router", None), "routes", []):
                    if inner.path == path:
                        return inner

        route = find_route(notif_app, "/notifications/stream")
        assert route is not None
        assert get_db not in set(calls(route.dependant))


# ── GET /notifications ───────────────────────────────────────────────────────

def make_rows_cursor(rows):
    cursor = AsyncMock()
    cursor.fetchall = AsyncMock(return_value=rows)
    return cursor


class TestListNotifications:
    async def test_returns_notifications_with_the_sender_name(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_rows_cursor([
            {"id": 9, "type": "match", "seen": False, "created_at": datetime(2026, 10, 3, 9, 13), "from_user_id": 2, "first_name": "Bob"},
            {"id": 8, "type": "visit", "seen": True, "created_at": datetime(2026, 10, 2, 9, 13), "from_user_id": 3, "first_name": "Cleo"},
        ]))

        res = await auth_client.get("/notifications")

        assert res.status_code == 200
        assert res.json() == [
            {"id": 9, "type": "match", "seen": False, "created_at": "2026-10-03T09:13:00", "from_user_id": 2, "first_name": "Bob"},
            {"id": 8, "type": "visit", "seen": True, "created_at": "2026-10-02T09:13:00", "from_user_id": 3, "first_name": "Cleo"},
        ]

    async def test_no_notification_returns_an_empty_list(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_rows_cursor([]))

        res = await auth_client.get("/notifications")

        assert res.status_code == 200
        assert res.json() == []

    async def test_asks_for_the_session_users_latest_ones_only(self, auth_client, mock_db, mock_redis):
        from app.routes.notifications import NOTIFICATIONS_LIMIT
        mock_redis.get = AsyncMock(return_value="7")
        mock_db.execute = AsyncMock(return_value=make_rows_cursor([]))

        await auth_client.get("/notifications")

        query, params = mock_db.execute.call_args.args
        query = " ".join(query.split())
        assert params == (7,)
        assert query.count("%s") == len(params)
        # a constant of ours (never user input), written into the query rather than passed as a parameter
        assert f"LIMIT {NOTIFICATIONS_LIMIT}" in query
        assert "WHERE n.user_id = %s" in query
        assert "ORDER BY n.id DESC" in query  # newest first
        assert "JOIN users u ON u.id = n.from_user_id" in query  # the name cannot come from GET /users/{id}

    async def test_leaves_out_notifications_from_blocked_users_in_both_directions(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_rows_cursor([]))

        await auth_client.get("/notifications")

        query = " ".join(mock_db.execute.call_args.args[0].split())
        assert "NOT EXISTS" in query
        assert "b.blocker_id = n.user_id AND b.blocked_id = n.from_user_id" in query
        assert "b.blocker_id = n.from_user_id AND b.blocked_id = n.user_id" in query

    async def test_list_and_counter_share_the_same_blocked_filter(self, auth_client, mock_db, mock_redis):
        """If they diverged the badge would announce notifications the list does not show."""
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[make_rows_cursor([]), make_count_cursor(0)])

        await auth_client.get("/notifications")
        await auth_client.get("/notifications/unread-count")

        list_query, count_query = (" ".join(c.args[0].split()) for c in mock_db.execute.call_args_list)
        blocked = " ".join(__import__("app.routes.notifications", fromlist=["x"]).NOT_FROM_A_BLOCKED_USER.split())
        assert blocked in list_query and blocked in count_query

    async def test_expired_session_returns_401(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)

        res = await auth_client.get("/notifications")

        assert res.status_code == 401
        mock_db.execute.assert_not_called()

    async def test_no_cookie_returns_401(self, client, mock_db):
        res = await client.get("/notifications")

        assert res.status_code == 401
        mock_db.execute.assert_not_called()


# ── GET /notifications/unread-count ──────────────────────────────────────────

def make_count_cursor(unread):
    cursor = AsyncMock()
    cursor.fetchone = AsyncMock(return_value={"unread": unread})
    return cursor


class TestUnreadCount:
    async def test_returns_the_number_of_unread_notifications(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_count_cursor(3))

        res = await auth_client.get("/notifications/unread-count")

        assert res.status_code == 200
        assert res.json() == {"unread": 3}

    async def test_nothing_unread_returns_zero(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_count_cursor(0))

        res = await auth_client.get("/notifications/unread-count")

        assert res.status_code == 200
        assert res.json() == {"unread": 0}

    async def test_counts_only_the_session_users_unread_rows(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="7")
        mock_db.execute = AsyncMock(return_value=make_count_cursor(0))

        await auth_client.get("/notifications/unread-count")

        query, params = mock_db.execute.call_args.args
        assert params == (7,)
        assert query.count("%s") == len(params)
        # `seen = false` written as is: it is what lets PostgreSQL use the partial index
        assert "n.user_id = %s" in query and "n.seen = false" in query

    async def test_ignores_notifications_from_blocked_users_in_both_directions(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_count_cursor(0))

        await auth_client.get("/notifications/unread-count")

        query = " ".join(mock_db.execute.call_args.args[0].split())
        assert "NOT EXISTS" in query
        assert "b.blocker_id = n.user_id AND b.blocked_id = n.from_user_id" in query  # I blocked them
        assert "b.blocker_id = n.from_user_id AND b.blocked_id = n.user_id" in query  # they blocked me

    async def test_expired_session_returns_401(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)

        res = await auth_client.get("/notifications/unread-count")

        assert res.status_code == 401
        mock_db.execute.assert_not_called()

    async def test_no_cookie_returns_401(self, client, mock_db):
        res = await client.get("/notifications/unread-count")

        assert res.status_code == 401
        mock_db.execute.assert_not_called()


# ── POST /notifications/seen ─────────────────────────────────────────────────

def make_update_cursor(rowcount):
    cursor = AsyncMock()
    cursor.rowcount = rowcount
    return cursor


class TestMarkSeen:
    async def test_marks_notifications_seen_and_returns_how_many(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_update_cursor(4))  # the prune statement reuses it

        res = await auth_client.post("/notifications/seen")

        assert res.status_code == 200
        assert res.json() == {"updated": 4}

    async def test_nothing_unread_updates_zero_rows(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_update_cursor(0))

        res = await auth_client.post("/notifications/seen")

        assert res.status_code == 200
        assert res.json() == {"updated": 0}

    async def test_only_touches_the_session_users_unread_rows(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="7")
        mock_db.execute = AsyncMock(return_value=make_update_cursor(0))

        await auth_client.post("/notifications/seen")

        query, params = mock_db.execute.call_args_list[0].args
        assert params == (7,)
        assert query.count("%s") == len(params)
        assert "SET seen = true" in query
        assert "WHERE user_id = %s AND seen = false" in query

    async def test_prunes_only_read_notifications_beyond_the_limit(self, auth_client, mock_db, mock_redis):
        from app.routes.notifications import NOTIFICATIONS_LIMIT
        mock_redis.get = AsyncMock(return_value="7")
        mock_db.execute = AsyncMock(return_value=make_update_cursor(2))

        await auth_client.post("/notifications/seen")

        query, params = mock_db.execute.call_args_list[1].args
        query = " ".join(query.split())
        assert params == (7, 7, NOTIFICATIONS_LIMIT)
        assert query.count("%s") == len(params)
        assert "DELETE FROM notifications" in query
        assert "seen = true" in query  # an unread notification is never deleted
        assert "ORDER BY id DESC LIMIT %s" in query  # the newest ones are kept

    async def test_the_count_returned_is_the_unread_ones_not_the_pruned_ones(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        first, second = make_update_cursor(3), make_update_cursor(11)  # 11 old rows deleted
        mock_db.execute = AsyncMock(side_effect=[first, second])

        res = await auth_client.post("/notifications/seen")

        assert res.json() == {"updated": 3}

    async def test_commits_after_the_update(self, auth_client, mock_db, mock_redis):
        """The write is committed before answering, not left to the pool when the
        request ends, so a count asked right after the reply is already up to date."""
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_update_cursor(1))

        await auth_client.post("/notifications/seen")

        assert [call[0] for call in mock_db.mock_calls if call[0] in ("execute", "commit")] == ["execute", "execute", "commit"]

    async def test_expired_session_writes_nothing(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)

        res = await auth_client.post("/notifications/seen")

        assert res.status_code == 401
        mock_db.execute.assert_not_called()
        mock_db.commit.assert_not_awaited()

    async def test_no_cookie_writes_nothing(self, client, mock_db):
        res = await client.post("/notifications/seen")

        assert res.status_code == 401
        mock_db.execute.assert_not_called()
        mock_db.commit.assert_not_awaited()


# ── insert_notification ──────────────────────────────────────────────────────

class TestInsertNotification:
    async def test_inserts_notification_with_correct_params(self):
        from app.routes.notifications import insert_notification
        conn = AsyncMock()

        await insert_notification(conn, 1, 2, "like")

        query, params = conn.execute.call_args.args
        assert "INSERT INTO notifications" in query
        assert params == (1, 2, "like", 1, 2, "like")
        assert query.count("%s") == len(params)

    async def test_skips_a_duplicate_unread_notification(self):
        """A burst of messages (or a like / unlike loop) is one entry in the box, not
        twenty: nothing is inserted while an identical unread one is still there."""
        from app.routes.notifications import insert_notification
        conn = AsyncMock()

        await insert_notification(conn, 1, 2, "message")

        query = " ".join(conn.execute.call_args.args[0].split())
        assert "WHERE NOT EXISTS" in query
        assert "WHERE user_id = %s AND from_user_id = %s AND type = %s AND seen = false" in query

    async def test_does_not_touch_redis(self):
        """insert_notification only writes to the DB; the caller commits and
        publishes separately once the transaction succeeds."""
        from app.routes.notifications import insert_notification
        conn = AsyncMock()
        redis = AsyncMock()

        await insert_notification(conn, 1, 2, "like")

        redis.publish.assert_not_called()

    async def test_db_failure_propagates(self):
        from app.routes.notifications import insert_notification
        conn = AsyncMock()
        conn.execute = AsyncMock(side_effect=Exception("db down"))

        with pytest.raises(Exception, match="db down"):
            await insert_notification(conn, 1, 2, "like")


# ── publish_notification ─────────────────────────────────────────────────────

class TestPublishNotification:
    async def test_publishes_to_correct_user_channel(self):
        from app.routes.notifications import publish_notification
        redis = AsyncMock()

        await publish_notification(99, 42, "visit", redis)

        channel = redis.publish.call_args.args[0]
        assert channel == "notif:99"

    async def test_publishes_correct_json_payload(self):
        from app.routes.notifications import publish_notification
        redis = AsyncMock()

        await publish_notification(10, 20, "match", redis)

        _, payload = redis.publish.call_args.args
        data = json.loads(payload)
        assert data == {"type": "match", "from_user_id": 20}

    async def test_like_notification(self):
        from app.routes.notifications import publish_notification
        redis = AsyncMock()

        await publish_notification(1, 2, "like", redis)

        _, payload = redis.publish.call_args.args
        assert json.loads(payload)["type"] == "like"

    async def test_unlike_notification(self):
        from app.routes.notifications import publish_notification
        redis = AsyncMock()

        await publish_notification(1, 2, "unlike", redis)

        _, payload = redis.publish.call_args.args
        assert json.loads(payload)["type"] == "unlike"

    async def test_match_notification(self):
        from app.routes.notifications import publish_notification
        redis = AsyncMock()

        await publish_notification("1", "2", "match", redis)

        _, payload = redis.publish.call_args.args
        assert json.loads(payload)["type"] == "match"

    async def test_visit_notification(self):
        from app.routes.notifications import publish_notification
        redis = AsyncMock()

        await publish_notification("1", "2", "visit", redis)

        _, payload = redis.publish.call_args.args
        assert json.loads(payload)["type"] == "visit"

    async def test_from_user_id_in_redis_payload_not_target(self):
        from app.routes.notifications import publish_notification
        redis = AsyncMock()

        await publish_notification(user_id="5", from_user_id="7", type="like", redis=redis)

        _, payload = redis.publish.call_args.args
        data = json.loads(payload)
        assert data["from_user_id"] == "7"


# ── GET /notifications/stream ─────────────────────────────────────────────────

class TestNotificationsStream:
    def test_unauthenticated_request_returns_401(self, notif_app):
        from fastapi import HTTPException
        with patch(
            "app.routes.notifications.get_current_user_id",
            new=AsyncMock(side_effect=HTTPException(401, "Not Authenticated")),
        ):
            with TestClient(notif_app, raise_server_exceptions=False) as tc:
                resp = tc.get("/notifications/stream")
                assert resp.status_code == 401

    def test_authenticated_request_returns_200(self, notif_app):
        with patch(
            "app.routes.notifications.get_current_user_id",
            new=AsyncMock(return_value="42"),
        ):
            with TestClient(notif_app) as tc:
                with tc.stream("GET", "/notifications/stream",
                               headers={"Cookie": f"session={make_session_cookie()}"}
                               ) as resp:
                    assert resp.status_code == 200

    def test_response_content_type_is_event_stream(self, notif_app):
        with patch(
            "app.routes.notifications.get_current_user_id",
            new=AsyncMock(return_value="42"),
        ):
            with TestClient(notif_app) as tc:
                with tc.stream("GET", "/notifications/stream",
                               headers={"Cookie": f"session={make_session_cookie()}"}
                               ) as resp:
                    assert "text/event-stream" in resp.headers["content-type"]

    def test_response_disables_caching(self, notif_app):
        with patch(
            "app.routes.notifications.get_current_user_id",
            new=AsyncMock(return_value="42"),
        ):
            with TestClient(notif_app) as tc:
                with tc.stream("GET", "/notifications/stream",
                               headers={"Cookie": f"session={make_session_cookie()}"}
                               ) as resp:
                    assert resp.headers.get("cache-control") == "no-cache"

    def test_response_disables_nginx_buffering(self, notif_app):
        with patch(
            "app.routes.notifications.get_current_user_id",
            new=AsyncMock(return_value="42"),
        ):
            with TestClient(notif_app) as tc:
                with tc.stream("GET", "/notifications/stream",
                               headers={"Cookie": f"session={make_session_cookie()}"}
                               ) as resp:
                    assert resp.headers.get("x-accel-buffering") == "no"

    def test_subscribes_to_correct_redis_channel(self, notif_app, mock_redis):
        pubsub = make_pubsub()
        mock_redis.pubsub = MagicMock(return_value=pubsub)

        with patch(
            "app.routes.notifications.get_current_user_id",
            new=AsyncMock(return_value="42"),
        ):
            with TestClient(notif_app) as tc:
                with tc.stream("GET", "/notifications/stream",
                               headers={"Cookie": f"session={make_session_cookie()}"}):
                    pass

        pubsub.subscribe.assert_called_once_with("notif:42")

    def test_unsubscribes_on_stream_end(self, notif_app, mock_redis):
        pubsub = make_pubsub()
        mock_redis.pubsub = MagicMock(return_value=pubsub)

        with patch(
            "app.routes.notifications.get_current_user_id",
            new=AsyncMock(return_value="42"),
        ):
            with TestClient(notif_app) as tc:
                with tc.stream("GET", "/notifications/stream",
                               headers={"Cookie": f"session={make_session_cookie()}"}):
                    pass

        pubsub.unsubscribe.assert_called_once_with("notif:42")

    def test_message_events_are_forwarded_as_sse_data(self, notif_app, mock_redis):
        payload = json.dumps({"type": "like", "from_user_id": "7"})
        messages = [
            {"type": "subscribe", "data": 1},
            {"type": "message", "data": payload},
        ]
        pubsub = make_pubsub(messages)
        mock_redis.pubsub = MagicMock(return_value=pubsub)

        with patch(
            "app.routes.notifications.get_current_user_id",
            new=AsyncMock(return_value="42"),
        ):
            with TestClient(notif_app) as tc:
                with tc.stream("GET", "/notifications/stream",
                               headers={"Cookie": f"session={make_session_cookie()}"}
                               ) as resp:
                    body = b"".join(resp.iter_bytes())

        assert f"data: {payload}\n\n".encode() in body

    def test_subscribe_events_are_not_forwarded(self, notif_app, mock_redis):
        messages = [
            {"type": "subscribe", "data": 1},
            {"type": "unsubscribe", "data": 0},
        ]
        pubsub = make_pubsub(messages)
        mock_redis.pubsub = MagicMock(return_value=pubsub)

        with patch(
            "app.routes.notifications.get_current_user_id",
            new=AsyncMock(return_value="42"),
        ):
            with TestClient(notif_app) as tc:
                with tc.stream("GET", "/notifications/stream",
                               headers={"Cookie": f"session={make_session_cookie()}"}
                               ) as resp:
                    body = b"".join(resp.iter_bytes())

        assert b"data:" not in body

    def test_multiple_messages_all_streamed(self, notif_app, mock_redis):
        payloads = [
            json.dumps({"type": "like", "from_user_id": "1"}),
            json.dumps({"type": "visit", "from_user_id": "2"}),
        ]
        messages = [{"type": "message", "data": p} for p in payloads]
        pubsub = make_pubsub(messages)
        mock_redis.pubsub = MagicMock(return_value=pubsub)

        with patch(
            "app.routes.notifications.get_current_user_id",
            new=AsyncMock(return_value="42"),
        ):
            with TestClient(notif_app) as tc:
                with tc.stream("GET", "/notifications/stream",
                               headers={"Cookie": f"session={make_session_cookie()}"}
                               ) as resp:
                    body = b"".join(resp.iter_bytes())

        for p in payloads:
            assert f"data: {p}\n\n".encode() in body

    def test_channel_is_specific_to_authenticated_user(self, notif_app, mock_redis):
        """Two different users subscribe to separate channels."""
        pubsub_a = make_pubsub()
        mock_redis.pubsub = MagicMock(return_value=pubsub_a)

        with patch(
            "app.routes.notifications.get_current_user_id",
            new=AsyncMock(return_value="99"),
        ):
            with TestClient(notif_app) as tc:
                with tc.stream("GET", "/notifications/stream",
                               headers={"Cookie": f"session={make_session_cookie()}"}):
                    pass

        pubsub_a.subscribe.assert_called_once_with("notif:99")
        channel = pubsub_a.subscribe.call_args.args[0]
        assert channel != "notif:42"


# ── presence: an open stream keeps the user online ────────────────────────────

class TestStreamPresence:
    @staticmethod
    def open_stream(notif_app, user_id="42"):
        with patch("app.routes.notifications.get_current_user_id", new=AsyncMock(return_value=user_id)):
            with TestClient(notif_app) as tc:
                with tc.stream("GET", "/notifications/stream",
                               headers={"Cookie": f"session={make_session_cookie()}"}) as resp:
                    b"".join(resp.iter_bytes())

    def test_opening_the_stream_records_the_user_as_connected(self, notif_app, mock_redis, presence):
        self.open_stream(notif_app)
        presence.connected.assert_awaited_once_with(mock_redis, "42")

    def test_closing_the_stream_records_the_user_as_disconnected(self, notif_app, mock_redis, presence):
        self.open_stream(notif_app)
        presence.disconnected.assert_awaited_once_with(mock_redis, "42")

    def test_each_connection_is_counted_once(self, notif_app, presence):
        self.open_stream(notif_app)
        self.open_stream(notif_app)
        assert presence.connected.await_count == 2
        assert presence.disconnected.await_count == 2

    def test_unauthenticated_stream_is_never_counted(self, notif_app, presence):
        from fastapi import HTTPException
        with patch("app.routes.notifications.get_current_user_id",
                   new=AsyncMock(side_effect=HTTPException(401, "Not Authenticated"))):
            with TestClient(notif_app, raise_server_exceptions=False) as tc:
                assert tc.get("/notifications/stream").status_code == 401
        presence.connected.assert_not_called()
        presence.disconnected.assert_not_called()

    def test_a_failure_to_record_presence_does_not_break_the_stream(self, notif_app, mock_redis, presence):
        payload = json.dumps({"type": "like", "from_user_id": "7"})
        mock_redis.pubsub = MagicMock(return_value=make_pubsub([{"type": "message", "data": payload}]))
        presence.connected.side_effect = RuntimeError("redis down")

        with patch("app.routes.notifications.get_current_user_id", new=AsyncMock(return_value="42")):
            with TestClient(notif_app) as tc:
                with tc.stream("GET", "/notifications/stream",
                               headers={"Cookie": f"session={make_session_cookie()}"}) as resp:
                    assert resp.status_code == 200
                    body = b"".join(resp.iter_bytes())

        assert f"data: {payload}\n\n".encode() in body
        # The connection was never counted, so it must not be uncounted either.
        presence.disconnected.assert_not_called()

    def test_a_failure_to_record_the_disconnection_is_contained(self, notif_app, presence):
        presence.disconnected.side_effect = RuntimeError("db down")
        self.open_stream(notif_app)  # must not raise
        presence.disconnected.assert_awaited_once()

    def test_the_stream_still_unsubscribes_when_presence_fails(self, notif_app, mock_redis, presence):
        pubsub = make_pubsub()
        mock_redis.pubsub = MagicMock(return_value=pubsub)
        presence.disconnected.side_effect = RuntimeError("db down")

        self.open_stream(notif_app)

        pubsub.unsubscribe.assert_called_once_with("notif:42")
        pubsub.aclose.assert_awaited_once()
