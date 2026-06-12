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
