import pytest
from unittest.mock import AsyncMock


class TestHealthRoute:
    async def test_health_returns_ok(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestDbCheckRoute:
    async def test_db_check_returns_db_result(self, client, mock_cursor):
        mock_cursor.fetchone = AsyncMock(return_value={"?column?": 1})

        resp = await client.get("/api/db_check")

        assert resp.status_code == 200
        assert resp.json()["db"] is not None

    async def test_db_check_executes_select_one(self, client, mock_db):
        await client.get("/api/db_check")
        mock_db.execute.assert_called_once_with("SELECT 1")
