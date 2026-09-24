import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from fastapi.responses import Response as FastAPIResponse


def make_mock_response():
    r = MagicMock()
    r.set_cookie = MagicMock()
    return r


def make_mock_redis(fail=False):
    from redis import RedisError
    r = AsyncMock()
    if fail:
        r.set = AsyncMock(side_effect=RedisError("Connection refused"))
    else:
        r.set = AsyncMock(return_value=True)
    return r


class TestCreateSession:
    async def test_stores_session_in_redis(self):
        from app.security.session import create_session
        response = make_mock_response()
        redis = make_mock_redis()

        with patch("app.security.session.SECRET", "test-secret-key-32bytes-long!!!!"):
            await create_session(response, "42", redis)

        redis.set.assert_called_once()
        key, value = redis.set.call_args.args
        assert key.startswith("session:")
        assert value == "42"

    async def test_session_ttl_is_one_week(self):
        from app.security.session import create_session
        response = make_mock_response()
        redis = make_mock_redis()

        with patch("app.security.session.SECRET", "test-secret-key-32bytes-long!!!!"):
            await create_session(response, "42", redis)

        assert redis.set.call_args.kwargs.get("ex") == 604800

    async def test_sets_httponly_cookie(self):
        from app.security.session import create_session
        response = make_mock_response()
        redis = make_mock_redis()

        with patch("app.security.session.SECRET", "test-secret-key-32bytes-long!!!!"):
            await create_session(response, "42", redis)

        response.set_cookie.assert_called_once()
        kwargs = response.set_cookie.call_args.kwargs
        assert kwargs["httponly"] is True
        assert kwargs["samesite"] == "strict"
        assert kwargs["key"] == "session"

    async def test_cookie_value_contains_hmac_signature(self):
        from app.security.session import create_session
        response = make_mock_response()
        redis = make_mock_redis()

        with patch("app.security.session.SECRET", "test-secret-key-32bytes-long!!!!"):
            await create_session(response, "42", redis)

        cookie_value = response.set_cookie.call_args.kwargs["value"]
        # Format: <session_id>$<hmac>
        assert "$" in cookie_value
        parts = cookie_value.split("$")
        assert len(parts) == 2
        assert len(parts[0]) == 64  # secrets.token_hex(32) = 64 hex chars
        assert len(parts[1]) == 64  # SHA-256 hex digest

    async def test_indexes_session_in_user_sessions_zset(self):
        from app.security.session import create_session
        response = make_mock_response()
        redis = make_mock_redis()

        with patch("app.security.session.SECRET", "test-secret-key-32bytes-long!!!!"):
            await create_session(response, "42", redis)

        redis.zadd.assert_called_once()
        key, mapping = redis.zadd.call_args.args
        assert key == "user_sessions:42"
        session_id = redis.set.call_args.args[0].split(":", 1)[1]
        assert session_id in mapping

    async def test_user_sessions_score_is_expiry_timestamp(self):
        import time
        from app.security.session import create_session
        response = make_mock_response()
        redis = make_mock_redis()

        before = time.time()
        with patch("app.security.session.SECRET", "test-secret-key-32bytes-long!!!!"):
            await create_session(response, "42", redis)
        after = time.time()

        _, mapping = redis.zadd.call_args.args
        score = next(iter(mapping.values()))
        assert before + 604800 <= score <= after + 604800

    async def test_raises_503_when_redis_fails(self):
        from app.security.session import create_session
        response = make_mock_response()
        redis = make_mock_redis(fail=True)

        with patch("app.security.session.SECRET", "test-secret-key-32bytes-long!!!!"):
            with pytest.raises(HTTPException) as exc_info:
                await create_session(response, "42", redis)

        assert exc_info.value.status_code == 503

    async def test_cookie_not_set_when_redis_fails(self):
        from app.security.session import create_session
        response = make_mock_response()
        redis = make_mock_redis(fail=True)

        with patch("app.security.session.SECRET", "test-secret-key-32bytes-long!!!!"):
            with pytest.raises(HTTPException):
                await create_session(response, "42", redis)

        response.set_cookie.assert_not_called()

    async def test_redis_error_is_logged(self):
        from app.security.session import create_session
        response = make_mock_response()
        redis = make_mock_redis(fail=True)

        with patch("app.security.session.SECRET", "test-secret-key-32bytes-long!!!!"), \
             patch("app.security.session.logger") as mock_logger:
            with pytest.raises(HTTPException):
                await create_session(response, "42", redis)

        mock_logger.exception.assert_called_once()


# ── get_current_user_id ───────────────────────────────────────────────────────

class TestGetCurrentUserId:
    def _make_redis(self, user_id="1"):
        r = AsyncMock()
        r.get = AsyncMock(return_value=user_id)
        return r

    async def test_valid_cookie_returns_user_id(self):
        from app.security.session import get_current_user_id
        import hmac, hashlib
        secret = "any-secret-key-for-this-unit-test!"
        session_id = "abc123"
        sig = hmac.new(secret.encode(), session_id.encode(), digestmod=hashlib.sha256).hexdigest()
        cookie = f"{session_id}${sig}"
        redis = self._make_redis("42")

        with patch("app.security.session.SECRET", secret):
            uid = await get_current_user_id(cookie, redis)

        assert uid == "42"

    async def test_missing_cookie_raises_401(self):
        from app.security.session import get_current_user_id
        redis = self._make_redis()

        with pytest.raises(HTTPException) as exc:
            await get_current_user_id(None, redis)
        assert exc.value.status_code == 401

    async def test_empty_cookie_raises_401(self):
        from app.security.session import get_current_user_id
        redis = self._make_redis()

        with pytest.raises(HTTPException) as exc:
            await get_current_user_id("", redis)
        assert exc.value.status_code == 401

    async def test_cookie_without_dollar_sign_raises_401(self):
        from app.security.session import get_current_user_id
        redis = self._make_redis()

        with pytest.raises(HTTPException) as exc:
            await get_current_user_id("invalidsessionnocookie", redis)
        assert exc.value.status_code == 401

    async def test_tampered_hmac_raises_401(self):
        from app.security.session import get_current_user_id
        redis = self._make_redis()
        cookie = "validsessionid$aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

        with patch("app.security.session.SECRET", "any-secret-key-for-this-unit-test!"):
            with pytest.raises(HTTPException) as exc:
                await get_current_user_id(cookie, redis)
        assert exc.value.status_code == 401

    async def test_expired_session_raises_401(self):
        from app.security.session import get_current_user_id
        import hmac, hashlib
        secret = "any-secret-key-for-this-unit-test!"
        session_id = "expiredsession"
        sig = hmac.new(secret.encode(), session_id.encode(), digestmod=hashlib.sha256).hexdigest()
        cookie = f"{session_id}${sig}"

        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)  # session not in Redis

        with patch("app.security.session.SECRET", "any-secret-key-for-this-unit-test!"):
            with pytest.raises(HTTPException) as exc:
                await get_current_user_id(cookie, redis)
        assert exc.value.status_code == 401
