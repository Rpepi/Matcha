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

    application = create_app()

    async def override_get_db():
        yield mock_db

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_redis] = lambda: mock_redis
    # dependency_overrides only patches Depends(get_redis); code that reaches
    # request.app.state.redis directly (the chat WebSocket handler) needs the
    # same mock available there too, or it hits a real, unmocked State.redis
    # AttributeError instead of using the test's mock.
    application.state.redis = mock_redis

    # The Lua script is normally registered in lifespan(), which the ASGI
    # transport used by these fixtures never runs. Route tests exercise route
    # logic, not the limiter, so it is replaced by a stub that always allows —
    # the same way get_db/get_redis are swapped for mocks. Everything goes
    # through app.state, so this covers the HTTP dependency and the chat
    # WebSocket check at once.
    # {allowed, remaining, retry_after} — the shape token_bucket.lua returns.
    application.state.rate_limit_script = AsyncMock(return_value=[1, 999, 0])

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
