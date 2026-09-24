import os
import hmac
import hashlib

os.environ.setdefault("SESSION_SECRET", "test-secret-key-for-testing-only-32b")
os.environ.setdefault("MAIL_SECRET", "test-mail-secret-for-testing-only-32b")
os.environ.setdefault("MAIL_HOST", "localhost")
os.environ.setdefault("MAIL_PORT", "1025")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

# Read the actual secret so make_session_cookie always matches session.py's SECRET.
SESSION_SECRET = os.environ["SESSION_SECRET"]


def make_session_cookie(session_id: str = "testsession") -> str:
    h = hmac.new(SESSION_SECRET.encode(), session_id.encode(), digestmod=hashlib.sha256).hexdigest()
    return f"{session_id}${h}"


def _build_app(mock_db, mock_redis):
    from app import create_app
    from app.db.dependencies import get_db
    from app.cache.dependencies import get_redis
    from app.security.rate_limit import (
        loginLimiter, registerLimiter, forgotPasswordLimiter, oauthLoginLimiter,
        LikeLimiter, blockLimiter, uploadPhotoLimiter, reportLimiter,
    )

    application = create_app()

    async def override_get_db():
        yield mock_db

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_redis] = lambda: mock_redis
    # dependency_overrides only patches Depends(get_redis); code that reaches
    # for request.app.state.redis directly (rate_limit.py's user_identifier,
    # since fastapi_limiter calls it outside FastAPI's dependency graph) needs
    # the same mock available there too, or it hits a real, unmocked
    # State.redis AttributeError instead of using the test's mock.
    application.state.redis = mock_redis

    # Every limiter below is a module-level singleton holding real in-memory
    # counters shared by the whole pytest session — nothing resets them
    # between tests. Route tests exist to test route logic, not the limiter
    # itself (already verified live against the real app), so they're
    # disabled here the same way get_db/get_redis are swapped for mocks.
    async def _no_limit():
        return None

    for limiter in (loginLimiter, registerLimiter, forgotPasswordLimiter, oauthLoginLimiter,
                     LikeLimiter, blockLimiter, uploadPhotoLimiter, reportLimiter):
        application.dependency_overrides[limiter] = _no_limit

    return application


@pytest.fixture
def mock_cursor():
    cursor = AsyncMock()
    cursor.fetchone = AsyncMock(return_value=None)
    return cursor


@pytest.fixture
def mock_db(mock_cursor):
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=mock_cursor)
    return conn


@pytest.fixture
def mock_redis():
    r = AsyncMock()
    r.set = AsyncMock(return_value=True)
    r.get = AsyncMock(return_value=None)
    r.delete = AsyncMock(return_value=1)
    r.aclose = AsyncMock()
    return r


@pytest.fixture
async def client(mock_db, mock_redis):
    """Unauthenticated HTTP test client."""
    with patch("app.db.pool.open_pool", new_callable=AsyncMock), \
        patch("app.db.pool.close_pool", new_callable=AsyncMock), \
        patch("redis.asyncio.Redis", return_value=mock_redis):

        application = _build_app(mock_db, mock_redis)

        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as c:
            yield c


@pytest.fixture
async def auth_client(mock_db, mock_redis):
    """Authenticated HTTP test client with session cookie preset."""
    with patch("app.db.pool.open_pool", new_callable=AsyncMock), \
        patch("app.db.pool.close_pool", new_callable=AsyncMock), \
        patch("redis.asyncio.Redis", return_value=mock_redis):

        application = _build_app(mock_db, mock_redis)

        async with AsyncClient(
            transport=ASGITransport(app=application),
            base_url="http://test",
            cookies={"session": make_session_cookie()},
        ) as c:
            yield c
