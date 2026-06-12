import hmac
import hashlib
import pytest
from unittest.mock import AsyncMock

SECRET = "test-secret-key-for-testing-only-32b"


def make_cookie(session_id: str = "testsession") -> str:
    h = hmac.new(SECRET.encode(), session_id.encode(), digestmod=hashlib.sha256).hexdigest()
    return f"{session_id}${h}"


def make_cursor(fetchone=None, fetchall=None):
    c = AsyncMock()
    c.fetchone = AsyncMock(return_value=fetchone)
    c.fetchall = AsyncMock(return_value=fetchall or [])
    return c


PROFILE_ROW = {
    "id": "1", "username": "alice", "email": "alice@test.com",
    "first_name": "Alice", "last_name": "Smith", "gender": "female",
    "orientation": "bisexual", "bio": "hello", "birth_date": "2000-01-01",
    "fame_rating": 0, "latitude": 48.8, "longitude": 2.3, "city": "Paris",
    "is_online": True, "last_seen": None, "profile_complete": True,
    "created_at": None,
}


class TestGetProfileMe:
    async def test_returns_profile_with_tags_and_photos(self, client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=PROFILE_ROW),
            make_cursor(fetchall=[{"name": "hiking"}, {"name": "music"}]),
            make_cursor(fetchall=[{"path": "/photos/1.jpg", "is_profile": True, "position": 0}]),
        ])

        res = await client.get("/profile/me", cookies={"session": make_cookie()})
        assert res.status_code == 200
        data = res.json()
        assert data["username"] == "alice"
        assert data["tags"] == ["hiking", "music"]
        assert len(data["photos"]) == 1
        assert data["photos"][0]["path"] == "/photos/1.jpg"

    async def test_no_cookie_returns_401(self, client):
        res = await client.get("/profile/me")
        assert res.status_code == 401

    async def test_expired_session_returns_401(self, client, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        res = await client.get("/profile/me", cookies={"session": make_cookie()})
        assert res.status_code == 401

    async def test_user_not_found_returns_401(self, client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone=None))

        res = await client.get("/profile/me", cookies={"session": make_cookie()})
        assert res.status_code == 401

    async def test_empty_tags_and_photos(self, client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=PROFILE_ROW),
            make_cursor(fetchall=[]),
            make_cursor(fetchall=[]),
        ])

        res = await client.get("/profile/me", cookies={"session": make_cookie()})
        assert res.status_code == 200
        assert res.json()["tags"] == []
        assert res.json()["photos"] == []


class TestPutProfileMe:
    async def test_update_bio(self, client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        cursor = make_cursor(fetchone={"id": 1})
        mock_db.execute = AsyncMock(return_value=cursor)

        res = await client.put(
            "/profile/me",
            json={"bio": "new bio"},
            cookies={"session": make_cookie()},
        )
        assert res.status_code == 200
        assert res.json()["message"] == "profile updated"

    async def test_update_tags_only(self, client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        cursor = make_cursor(fetchone={"id": 1})
        mock_db.execute = AsyncMock(return_value=cursor)

        res = await client.put(
            "/profile/me",
            json={"tags": ["hiking", "music"]},
            cookies={"session": make_cookie()},
        )
        assert res.status_code == 200

    async def test_no_fields_returns_400(self, client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await client.put(
            "/profile/me",
            json={},
            cookies={"session": make_cookie()},
        )
        assert res.status_code == 400
        assert "No fields" in res.json()["detail"]

    async def test_tags_not_a_list_returns_400(self, client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await client.put(
            "/profile/me",
            json={"tags": "hiking"},
            cookies={"session": make_cookie()},
        )
        assert res.status_code == 400
        assert "list" in res.json()["detail"]

    async def test_too_many_tags_returns_400(self, client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await client.put(
            "/profile/me",
            json={"tags": ["a", "b", "c", "d", "e", "f"]},
            cookies={"session": make_cookie()},
        )
        assert res.status_code == 400
        assert "5" in res.json()["detail"]

    async def test_wrong_content_type_returns_415(self, client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await client.put(
            "/profile/me",
            content="bio=hello",
            headers={"content-type": "application/x-www-form-urlencoded"},
            cookies={"session": make_cookie()},
        )
        assert res.status_code == 415

    async def test_no_cookie_returns_401(self, client):
        res = await client.put("/profile/me", json={"bio": "x"})
        assert res.status_code == 401

    async def test_db_error_returns_500(self, client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=Exception("db down"))

        res = await client.put(
            "/profile/me",
            json={"bio": "new bio"},
            cookies={"session": make_cookie()},
        )
        assert res.status_code == 500


class TestPutProfileLocation:
    async def test_valid_coordinates(self, client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor())

        res = await client.put(
            "/profile/location",
            json={"latitude": 48.8566, "longitude": 2.3522},
            cookies={"session": make_cookie()},
        )
        assert res.status_code == 200
        assert res.json()["message"] == "Location updated"

    async def test_missing_latitude_returns_400(self, client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await client.put(
            "/profile/location",
            json={"longitude": 2.3522},
            cookies={"session": make_cookie()},
        )
        assert res.status_code == 400

    async def test_missing_longitude_returns_400(self, client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await client.put(
            "/profile/location",
            json={"latitude": 48.8566},
            cookies={"session": make_cookie()},
        )
        assert res.status_code == 400

    async def test_string_coordinates_returns_400(self, client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await client.put(
            "/profile/location",
            json={"latitude": "48.8", "longitude": "2.3"},
            cookies={"session": make_cookie()},
        )
        assert res.status_code == 400

    async def test_out_of_range_latitude_returns_400(self, client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await client.put(
            "/profile/location",
            json={"latitude": 91.0, "longitude": 2.3},
            cookies={"session": make_cookie()},
        )
        assert res.status_code == 400
        assert "GPS" in res.json()["detail"]

    async def test_out_of_range_longitude_returns_400(self, client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await client.put(
            "/profile/location",
            json={"latitude": 48.8, "longitude": 181.0},
            cookies={"session": make_cookie()},
        )
        assert res.status_code == 400

    async def test_boundary_coordinates_accepted(self, client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor())

        res = await client.put(
            "/profile/location",
            json={"latitude": -90.0, "longitude": 180.0},
            cookies={"session": make_cookie()},
        )
        assert res.status_code == 200

    async def test_no_cookie_returns_401(self, client):
        res = await client.put("/profile/location", json={"latitude": 1.0, "longitude": 1.0})
        assert res.status_code == 401

    async def test_db_error_returns_500(self, client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=Exception("db down"))

        res = await client.put(
            "/profile/location",
            json={"latitude": 48.8, "longitude": 2.3},
            cookies={"session": make_cookie()},
        )
        assert res.status_code == 500


class TestGetMyVisits:
    async def test_returns_visit_list(self, client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[
            {"id": 1, "visitor_id": 42, "created_at": None},
            {"id": 2, "visitor_id": 7, "created_at": None},
        ]))

        res = await client.get("/profile/me/visits", cookies={"session": make_cookie()})
        assert res.status_code == 200
        assert len(res.json()) == 2
        assert res.json()[0]["visitor_id"] == 42

    async def test_empty_visits(self, client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[]))

        res = await client.get("/profile/me/visits", cookies={"session": make_cookie()})
        assert res.status_code == 200
        assert res.json() == []

    async def test_no_cookie_returns_401(self, client):
        res = await client.get("/profile/me/visits")
        assert res.status_code == 401


class TestGetMyLikes:
    async def test_returns_like_list(self, client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[
            {"id": 1, "liker_id": 99, "created_at": None},
        ]))

        res = await client.get("/profile/me/likes", cookies={"session": make_cookie()})
        assert res.status_code == 200
        assert res.json()[0]["liker_id"] == 99

    async def test_empty_likes(self, client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[]))

        res = await client.get("/profile/me/likes", cookies={"session": make_cookie()})
        assert res.status_code == 200
        assert res.json() == []

    async def test_no_cookie_returns_401(self, client):
        res = await client.get("/profile/me/likes")
        assert res.status_code == 401
