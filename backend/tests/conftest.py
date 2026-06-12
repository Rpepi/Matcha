import os
os.environ.setdefault("SESSION_SECRET", "test-secret-key-for-testing-only-32b")
os.environ.setdefault("MAIL_SECRET", "test-mail-secret-for-testing-only-32b")
os.environ.setdefault("MAIL_HOST", "localhost")
os.environ.setdefault("MAIL_PORT", "1025")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport


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
    """HTTP test client with DB and Redis dependencies overridden."""
    with patch("app.db.pool.open_pool", new_callable=AsyncMock), \
         patch("app.db.pool.close_pool", new_callable=AsyncMock), \
         patch("redis.asyncio.Redis", return_value=mock_redis):

        from app import create_app
        from app.db.dependencies import get_db
        from app.cache.dependencies import get_redis

        application = create_app()

        async def override_get_db():
            yield mock_db

        application.dependency_overrides[get_db] = override_get_db
        application.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as c:
            yield c
