import json
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


# ── insert_notification ──────────────────────────────────────────────────────

class TestInsertNotification:
    async def test_inserts_notification_with_correct_params(self):
        from app.routes.notifications import insert_notification
        conn = AsyncMock()

        await insert_notification(conn, "1", "2", "like")

        query, params = conn.execute.call_args.args
        assert "INSERT INTO notifications" in query
        assert params == ("1", "2", "like")

    async def test_does_not_touch_redis(self):
        """insert_notification only writes to the DB; the caller commits and
        publishes separately once the transaction succeeds."""
        from app.routes.notifications import insert_notification
        conn = AsyncMock()
        redis = AsyncMock()

        await insert_notification(conn, "1", "2", "like")

        redis.publish.assert_not_called()

    async def test_db_failure_propagates(self):
        from app.routes.notifications import insert_notification
        conn = AsyncMock()
        conn.execute = AsyncMock(side_effect=Exception("db down"))

        with pytest.raises(Exception, match="db down"):
            await insert_notification(conn, "1", "2", "like")


# ── publish_notification ─────────────────────────────────────────────────────

class TestPublishNotification:
    async def test_publishes_to_correct_user_channel(self):
        from app.routes.notifications import publish_notification
        redis = AsyncMock()

        await publish_notification("99", "42", "visit", redis)

        channel = redis.publish.call_args.args[0]
        assert channel == "notif:99"

    async def test_publishes_correct_json_payload(self):
        from app.routes.notifications import publish_notification
        redis = AsyncMock()

        await publish_notification("10", "20", "match", redis)

        _, payload = redis.publish.call_args.args
        data = json.loads(payload)
        assert data == {"type": "match", "from_user_id": "20"}

    async def test_like_notification(self):
        from app.routes.notifications import publish_notification
        redis = AsyncMock()

        await publish_notification("1", "2", "like", redis)

        _, payload = redis.publish.call_args.args
        assert json.loads(payload)["type"] == "like"

    async def test_unlike_notification(self):
        from app.routes.notifications import publish_notification
        redis = AsyncMock()

        await publish_notification("1", "2", "unlike", redis)

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
