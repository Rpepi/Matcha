import re
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from psycopg.errors import UniqueViolation
from fastapi.responses import Response
from app.routes.profile import RECEIVED_LIST_LIMIT

JPEG_BYTES = b'\xff\xd8\xff\xe0' + b'\x00' * 200
PNG_BYTES = b'\x89PNG\r\n\x1a\n' + b'\x00' * 200

PROFILE_ROW = {
    "id": "1", "email": "alice@test.com",
    "first_name": "Alice", "last_name": "Smith", "gender": "female",
    "orientation": "bisexual", "bio": "hello", "birth_date": "2000-01-01",
    "fame_rating": 0, "latitude": 48.8, "longitude": 2.3, "city": "Paris",
    "is_online": True, "last_seen": None, "profile_complete": True,
    "created_at": None,
}


INCOMPLETE_PROFILE_ROW = {"gender": None, "birth_date": None, "city": None, "latitude": None, "longitude": None}


def make_cursor(fetchone=None, fetchall=None):
    c = AsyncMock()
    c.fetchone = AsyncMock(return_value=fetchone)
    c.fetchall = AsyncMock(return_value=fetchall or [])
    return c


class TestGetProfileMe:
    async def test_returns_profile_with_tags_and_photos(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=PROFILE_ROW),
            make_cursor(fetchall=[{"name": "hiking"}, {"name": "music"}]),
            make_cursor(fetchall=[{"path": "/photos/1.jpg", "is_profile": True, "position": 1}]),
        ])

        res = await auth_client.get("/profile/me")
        assert res.status_code == 200
        data = res.json()
        assert data["email"] == "alice@test.com"
        assert data["tags"] == ["hiking", "music"]
        assert len(data["photos"]) == 1
        assert data["photos"][0]["path"] == "/photos/1.jpg"

    async def test_no_cookie_returns_401(self, client):
        res = await client.get("/profile/me")
        assert res.status_code == 401

    async def test_expired_session_returns_401(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        res = await auth_client.get("/profile/me")
        assert res.status_code == 401

    async def test_user_not_found_returns_401(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone=None))

        res = await auth_client.get("/profile/me")
        assert res.status_code == 401

    async def test_empty_tags_and_photos(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=PROFILE_ROW),
            make_cursor(fetchall=[]),
            make_cursor(fetchall=[]),
        ])

        res = await auth_client.get("/profile/me")
        assert res.status_code == 200
        assert res.json()["tags"] == []
        assert res.json()["photos"] == []


class TestPutProfileMe:
    async def test_update_bio(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=INCOMPLETE_PROFILE_ROW),
            make_cursor(),
        ])

        res = await auth_client.put("/profile/me", json={"bio": "new bio"})
        assert res.status_code == 200
        assert res.json()["message"] == "profile updated"

    async def test_update_tags_only(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(
            fetchone={"id": 1},
            fetchall=[{"name": "hiking"}, {"name": "music"}]
        ))

        res = await auth_client.put("/profile/me", json={"tags": ["hiking", "music"]})
        assert res.status_code == 200
        assert res.json()["message"] == "profile updated"

    async def test_update_bio_and_tags(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")

        def side_effect(sql, params=None):
            if "gender" in sql and "SELECT" in sql:
                return make_cursor(fetchone=INCOMPLETE_PROFILE_ROW)
            if "ANY(%s)" in sql:
                return make_cursor(fetchall=[{"name": "sport"}])
            return make_cursor(fetchone={"id": 1})
        mock_db.execute = AsyncMock(side_effect=side_effect)

        res = await auth_client.put("/profile/me", json={"bio": "updated", "tags": ["sport"]})
        assert res.status_code == 200

    async def test_update_first_and_last_name(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=INCOMPLETE_PROFILE_ROW),
            make_cursor(),
        ])

        res = await auth_client.put("/profile/me", json={"first_name": "Bob", "last_name": "Jones"})
        assert res.status_code == 200
        assert res.json()["message"] == "profile updated"

    async def test_empty_first_name_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/me", json={"first_name": ""})
        assert res.status_code == 400

    async def test_non_string_last_name_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/me", json={"last_name": 42})
        assert res.status_code == 400

    async def test_update_email_resets_verified_and_sends_email(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=INCOMPLETE_PROFILE_ROW),
            make_cursor(),
        ])

        with patch("app.routes.profile.generate_verification_token", return_value="tok123") as mock_token, \
             patch("app.routes.profile.send_verification_email") as mock_send:
            res = await auth_client.put("/profile/me", json={"email": "new@test.com"})

        assert res.status_code == 200
        mock_token.assert_called_once_with("1", "new@test.com")
        mock_send.assert_called_once_with("new@test.com", "tok123")

        executed_sql = mock_db.execute.call_args_list[-1][0][0]
        assert "verified" in executed_sql

    async def test_verification_email_is_sent_off_the_event_loop(self, auth_client, mock_db, mock_redis):
        """send_verification_email is blocking smtplib (10 s timeout): it must
        run in a worker thread, not on the event loop shared by every request."""
        import threading
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=INCOMPLETE_PROFILE_ROW),
            make_cursor(),
        ])
        sender_threads = []

        def fake_send(to, token):
            sender_threads.append(threading.current_thread())

        with patch("app.routes.profile.generate_verification_token", return_value="tok123"), \
             patch("app.routes.profile.send_verification_email", side_effect=fake_send):
            res = await auth_client.put("/profile/me", json={"email": "new@test.com"})

        assert res.status_code == 200
        assert len(sender_threads) == 1
        assert sender_threads[0] is not threading.current_thread()

    async def test_email_send_failure_still_reports_the_committed_update(self, auth_client, mock_db, mock_redis):
        """The email change is committed (and `verified` reset) before the mail
        goes out, so an SMTP failure must not turn into a 500."""
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=INCOMPLETE_PROFILE_ROW),
            make_cursor(),
        ])

        with patch("app.routes.profile.generate_verification_token", return_value="tok123"), \
             patch("app.routes.profile.send_verification_email", side_effect=OSError("smtp down")):
            res = await auth_client.put("/profile/me", json={"email": "new@test.com"})

        assert res.status_code == 200
        assert "could not be sent" in res.json()["message"]
        mock_db.commit.assert_awaited_once()

    async def test_no_email_change_does_not_send_email(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=INCOMPLETE_PROFILE_ROW),
            make_cursor(),
        ])

        with patch("app.routes.profile.send_verification_email") as mock_send:
            res = await auth_client.put("/profile/me", json={"first_name": "Bob"})

        assert res.status_code == 200
        assert res.json()["message"] == "profile updated"
        mock_send.assert_not_called()

    async def test_empty_email_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/me", json={"email": ""})
        assert res.status_code == 400

    async def test_duplicate_email_returns_409(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=UniqueViolation("duplicate key"))

        with patch("app.routes.profile.generate_verification_token", return_value="tok123"), \
             patch("app.routes.profile.send_verification_email"):
            res = await auth_client.put("/profile/me", json={"email": "taken@test.com"})

        assert res.status_code == 409

    async def test_no_fields_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/me", json={})
        assert res.status_code == 400
        assert "No fields" in res.json()["detail"]

    async def test_tags_not_a_list_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/me", json={"tags": "hiking"})
        assert res.status_code == 400
        assert "list" in res.json()["detail"]

    async def test_too_many_tags_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/me", json={"tags": ["a", "b", "c", "d", "e", "f"]})
        assert res.status_code == 400
        assert "5" in res.json()["detail"]

    async def test_wrong_content_type_returns_415(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put(
            "/profile/me",
            content="bio=hello",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert res.status_code == 415

    async def test_no_cookie_returns_401(self, client):
        res = await client.put("/profile/me", json={"bio": "x"})
        assert res.status_code == 401

    async def test_db_error_returns_500(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=Exception("db down"))

        res = await auth_client.put("/profile/me", json={"bio": "new bio"})
        assert res.status_code == 500


class TestPutProfileLocation:
    async def test_valid_coordinates(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"gender": None, "birth_date": None}),
            make_cursor(),
        ])

        res = await auth_client.put("/profile/location", json={"latitude": 48.8566, "longitude": 2.3522})
        assert res.status_code == 200
        assert res.json()["message"] == "Location updated"

    async def test_missing_latitude_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/location", json={"longitude": 2.3522})
        assert res.status_code == 400

    async def test_missing_longitude_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/location", json={"latitude": 48.8566})
        assert res.status_code == 400

    async def test_string_coordinates_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/location", json={"latitude": "48.8", "longitude": "2.3"})
        assert res.status_code == 400

    async def test_out_of_range_latitude_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/location", json={"latitude": 91.0, "longitude": 2.3})
        assert res.status_code == 400
        assert "latitude" in res.json()["detail"]

    async def test_out_of_range_longitude_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/location", json={"latitude": 48.8, "longitude": 181.0})
        assert res.status_code == 400

    async def test_boundary_coordinates_accepted(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"gender": None, "birth_date": None}),
            make_cursor(),
        ])

        res = await auth_client.put("/profile/location", json={"latitude": -90.0, "longitude": 180.0})
        assert res.status_code == 200

    async def test_no_cookie_returns_401(self, client):
        res = await client.put("/profile/location", json={"latitude": 1.0, "longitude": 1.0})
        assert res.status_code == 401

    async def test_db_error_returns_500(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=Exception("db down"))

        res = await auth_client.put("/profile/location", json={"latitude": 48.8, "longitude": 2.3})
        assert res.status_code == 500


class TestGetMyVisits:
    async def test_returns_visit_list(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[
            {"id": 1, "visitor_id": 42, "created_at": None, "first_name": "Ada", "photo_position": 2},
            {"id": 2, "visitor_id": 7, "created_at": None, "first_name": "Bob", "photo_position": None},
        ]))

        res = await auth_client.get("/profile/me/visits")
        assert res.status_code == 200
        assert len(res.json()) == 2
        assert res.json()[0]["visitor_id"] == 42
        assert res.json()[0]["first_name"] == "Ada"
        assert res.json()[0]["photo_position"] == 2
        assert res.json()[1]["photo_position"] is None

    async def test_query_joins_visitor_name_and_profile_photo(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[]))

        await auth_client.get("/profile/me/visits")

        query, params = mock_db.execute.call_args.args
        assert "JOIN users" in query and "first_name" in query
        assert "is_profile = true" in query
        assert len(params) == 1 and int(params[0]) == 1

    async def test_query_is_ready_to_run_sql(self, auth_client, mock_db, mock_redis):
        # The DB is mocked, so nothing else would notice a placeholder that was
        # never interpolated or an alias copied from another query.
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[]))

        await auth_client.get("/profile/me/visits")

        query, _ = mock_db.execute.call_args.args
        assert "{" not in query and "}" not in query
        assert not re.search(r"\bn\.", query)

    async def test_query_leaves_out_blocked_visitors_in_both_directions(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[]))

        await auth_client.get("/profile/me/visits")

        query, _ = mock_db.execute.call_args.args
        assert "NOT EXISTS" in query and "FROM blocks" in query
        assert "b.blocker_id = v.visited_id AND b.blocked_id = v.visitor_id" in query
        assert "b.blocker_id = v.visitor_id AND b.blocked_id = v.visited_id" in query

    async def test_query_returns_newest_first_and_is_capped(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[]))

        await auth_client.get("/profile/me/visits")

        query, _ = mock_db.execute.call_args.args
        assert "ORDER BY v.created_at DESC" in query
        assert f"LIMIT {RECEIVED_LIST_LIMIT}" in query

    async def test_empty_visits(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[]))

        res = await auth_client.get("/profile/me/visits")
        assert res.status_code == 200
        assert res.json() == []

    async def test_no_cookie_returns_401(self, client):
        res = await client.get("/profile/me/visits")
        assert res.status_code == 401


class TestGetMyLikes:
    async def test_returns_like_list(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[
            {"id": 1, "liker_id": 99, "created_at": None, "first_name": "Cleo", "photo_position": 1},
        ]))

        res = await auth_client.get("/profile/me/likes")
        assert res.status_code == 200
        assert res.json()[0]["liker_id"] == 99
        assert res.json()[0]["first_name"] == "Cleo"
        assert res.json()[0]["photo_position"] == 1

    async def test_query_joins_liker_name_and_profile_photo(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[]))

        await auth_client.get("/profile/me/likes")

        query, params = mock_db.execute.call_args.args
        assert "JOIN users" in query and "first_name" in query
        assert "is_profile = true" in query
        assert len(params) == 1 and int(params[0]) == 1

    async def test_query_is_ready_to_run_sql(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[]))

        await auth_client.get("/profile/me/likes")

        query, _ = mock_db.execute.call_args.args
        assert "{" not in query and "}" not in query

    async def test_query_returns_newest_first_and_is_capped(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[]))

        await auth_client.get("/profile/me/likes")

        query, _ = mock_db.execute.call_args.args
        assert "ORDER BY l.created_at DESC" in query
        assert f"LIMIT {RECEIVED_LIST_LIMIT}" in query

    async def test_empty_likes(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[]))

        res = await auth_client.get("/profile/me/likes")
        assert res.status_code == 200
        assert res.json() == []

    async def test_no_cookie_returns_401(self, client):
        res = await client.get("/profile/me/likes")
        assert res.status_code == 401


class TestGetBlockedUsers:
    async def test_returns_blocked_users_with_their_names(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[
            {"id": 3, "first_name": "Kathleen", "created_at": datetime(2026, 10, 3, 9, 13)},
            {"id": 2, "first_name": "Danielle", "created_at": datetime(2026, 10, 2, 9, 13)},
        ]))

        res = await auth_client.get("/profile/me/blocked")

        assert res.status_code == 200
        assert res.json() == [
            {"id": 3, "first_name": "Kathleen", "created_at": "2026-10-03T09:13:00"},
            {"id": 2, "first_name": "Danielle", "created_at": "2026-10-02T09:13:00"},
        ]

    async def test_nobody_blocked_returns_an_empty_list(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[]))

        res = await auth_client.get("/profile/me/blocked")

        assert res.status_code == 200
        assert res.json() == []  # a list, like the other list routes: never {}

    async def test_query_is_scoped_to_the_session_user_and_newest_first(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[]))

        await auth_client.get("/profile/me/blocked")

        query, params = mock_db.execute.call_args.args
        assert params == (1,)
        assert "b.blocker_id = %s" in query
        assert "ORDER BY b.created_at DESC" in query

    async def test_query_exposes_only_what_the_screen_needs(self, auth_client, mock_db, mock_redis):
        """The name is joined in here because GET /users/{id} answers 404 for a blocked
        user: the front has no other way to get it. Nothing else of theirs should leak."""
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[]))

        await auth_client.get("/profile/me/blocked")

        query = mock_db.execute.call_args.args[0]
        assert "SELECT *" not in query
        assert "JOIN users u ON u.id = b.blocked_id" in query
        for private in ("email", "password", "latitude", "longitude", "birth_date"):
            assert private not in query

    async def test_db_failure_returns_500(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=Exception("db down"))

        res = await auth_client.get("/profile/me/blocked")

        assert res.status_code == 500
        assert res.json()["detail"] == "failed to query blocked users"

    async def test_expired_session_returns_401(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)  # cookie is signed but the session is gone

        res = await auth_client.get("/profile/me/blocked")

        assert res.status_code == 401
        mock_db.execute.assert_not_called()

    async def test_no_cookie_returns_401(self, client, mock_db):
        res = await client.get("/profile/me/blocked")

        assert res.status_code == 401
        mock_db.execute.assert_not_called()


class TestGetPhotos:
    async def test_returns_photo_list(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[
            {"position": 1, "path": "/uploads/1/a.jpg", "is_profile": True},
            {"position": 3, "path": "/uploads/1/b.jpg", "is_profile": False},
        ]))

        res = await auth_client.get("/profile/photos")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 2
        assert data[0]["position"] == 1
        assert data[0]["is_profile"] is True
        assert data[1]["position"] == 3

    async def test_empty_photos(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[]))

        res = await auth_client.get("/profile/photos")
        assert res.status_code == 200
        assert res.json() == []

    async def test_no_cookie_returns_401(self, client):
        res = await client.get("/profile/photos")
        assert res.status_code == 401


class TestUploadPhotos:
    async def test_upload_single_jpeg(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"count": 0}),
            make_cursor(fetchall=[]),
            make_cursor(),
        ])

        with patch("app.routes.profile.is_valid_image", return_value=True), \
             patch("app.routes.profile.process_photo", return_value="/uploads/1/x.jpg"):
            res = await auth_client.post(
                "/profile/photos",
                files=[("photos", ("photo.jpg", JPEG_BYTES, "image/jpeg"))],
            )

        assert res.status_code == 200
        assert "1" in res.json()["message"]

    async def test_upload_multiple_photos(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"count": 0}),
            make_cursor(fetchall=[]),
            make_cursor(),
            make_cursor(),
        ])

        with patch("app.routes.profile.is_valid_image", return_value=True), \
             patch("app.routes.profile.process_photo", return_value="/uploads/1/x.jpg"):
            res = await auth_client.post(
                "/profile/photos",
                files=[
                    ("photos", ("a.jpg", JPEG_BYTES, "image/jpeg")),
                    ("photos", ("b.jpg", JPEG_BYTES, "image/jpeg")),
                ],
            )

        assert res.status_code == 200
        assert "2" in res.json()["message"]

    async def test_first_photo_becomes_profile(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"count": 0}),
            make_cursor(fetchall=[]),
            make_cursor(),
        ])

        with patch("app.routes.profile.is_valid_image", return_value=True), \
             patch("app.routes.profile.process_photo", return_value="/uploads/1/x.jpg"):
            res = await auth_client.post(
                "/profile/photos",
                files=[("photos", ("a.jpg", JPEG_BYTES, "image/jpeg"))],
            )

        assert res.status_code == 200

    async def test_no_photos_field_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.post("/profile/photos", data={"other": "value"})
        assert res.status_code == 400
        assert "missing" in res.json()["detail"]

    async def test_exceeds_5_photo_limit_returns_400(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone={"count": 5}))

        res = await auth_client.post(
            "/profile/photos",
            files=[("photos", ("a.jpg", JPEG_BYTES, "image/jpeg"))],
        )
        assert res.status_code == 400
        assert "5" in res.json()["detail"]

    async def test_invalid_image_format_returns_400(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"count": 0}),
            make_cursor(fetchall=[]),
        ])

        with patch("app.routes.profile.is_valid_image", return_value=False):
            res = await auth_client.post(
                "/profile/photos",
                files=[("photos", ("evil.php", b"<?php echo 1; ?>", "image/jpeg"))],
            )

        assert res.status_code == 400
        assert "invalid" in res.json()["detail"]["error"]

    async def test_file_too_large_returns_400(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"count": 0}),
            make_cursor(fetchall=[]),
        ])

        oversized = b'\xff\xd8\xff' + b'\x00' * (5 * 1024 * 1024 + 1)
        res = await auth_client.post(
            "/profile/photos",
            files=[("photos", ("big.jpg", oversized, "image/jpeg"))],
        )
        assert res.status_code == 400
        assert "5MB" in res.json()["detail"]["error"]

    async def test_no_cookie_returns_401(self, client):
        res = await client.post(
            "/profile/photos",
            files=[("photos", ("a.jpg", JPEG_BYTES, "image/jpeg"))],
        )
        assert res.status_code == 401

    async def test_db_error_returns_500(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"count": 0}),
            make_cursor(fetchall=[]),
            Exception("db down"),
        ])

        with patch("app.routes.profile.is_valid_image", return_value=True), \
             patch("app.routes.profile.process_photo", return_value="/uploads/1/x.jpg"):
            res = await auth_client.post(
                "/profile/photos",
                files=[("photos", ("a.jpg", JPEG_BYTES, "image/jpeg"))],
            )

        assert res.status_code == 500


class TestGetPhoto:
    async def test_returns_photo_file(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone={"path": "/backend/uploads/1/a.jpg"}))

        with patch("app.routes.profile.os.path.isfile", return_value=True), \
             patch("app.routes.profile.FileResponse", return_value=Response(content=b"jpeg-bytes", media_type="image/jpeg")) as mock_file_response:
            res = await auth_client.get("/profile/photos/1")

        assert res.status_code == 200
        mock_file_response.assert_called_once_with("/backend/uploads/1/a.jpg", media_type="image/jpeg")

    async def test_invalid_position_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.get("/profile/photos/6")
        assert res.status_code == 400
        assert "1-5" in res.json()["detail"]

    async def test_photo_not_found_returns_404(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone=None))

        res = await auth_client.get("/profile/photos/3")
        assert res.status_code == 404
        assert "not found" in res.json()["detail"]

    async def test_missing_file_on_disk_returns_404(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone={"path": "/backend/uploads/1/missing.jpg"}))

        with patch("app.routes.profile.os.path.isfile", return_value=False):
            res = await auth_client.get("/profile/photos/1")

        assert res.status_code == 404

    async def test_no_cookie_returns_401(self, client):
        res = await client.get("/profile/photos/1")
        assert res.status_code == 401


class TestDeletePhoto:
    async def test_delete_existing_photo(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"path": "/uploads/1/a.jpg", "is_profile": False}),
            make_cursor(),
            make_cursor(),
        ])

        with patch("app.routes.profile.os.remove") as mock_remove:
            res = await auth_client.delete("/profile/photos/2")
            mock_remove.assert_called_once_with("/uploads/1/a.jpg")

        assert res.status_code == 200
        assert res.json()["message"] == "photo deleted"

    async def test_delete_profile_photo_promotes_next(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"path": "/uploads/1/a.jpg", "is_profile": True}),
            make_cursor(),
            make_cursor(),
        ])

        with patch("app.routes.profile.os.remove"):
            res = await auth_client.delete("/profile/photos/1")

        assert res.status_code == 200
        assert mock_db.execute.call_count == 3

    async def test_photo_not_found_returns_404(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone=None))

        res = await auth_client.delete("/profile/photos/3")
        assert res.status_code == 404
        assert "not found" in res.json()["detail"]

    async def test_invalid_position_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.delete("/profile/photos/6")
        assert res.status_code == 400
        assert "1-5" in res.json()["detail"]

    async def test_position_zero_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.delete("/profile/photos/0")
        assert res.status_code == 400

    async def test_missing_file_on_disk_does_not_fail(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"path": "/uploads/1/missing.jpg", "is_profile": False}),
            make_cursor(),
            make_cursor(),
        ])

        with patch("app.routes.profile.os.remove", side_effect=OSError("no such file")):
            res = await auth_client.delete("/profile/photos/2")

        assert res.status_code == 200

    async def test_no_cookie_returns_401(self, client):
        res = await client.delete("/profile/photos/1")
        assert res.status_code == 401

    async def test_db_error_returns_500(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"path": "/uploads/1/a.jpg", "is_profile": False}),
            Exception("db down"),
        ])

        res = await auth_client.delete("/profile/photos/1")
        assert res.status_code == 500


class TestMovePhoto:
    async def test_move_to_free_position(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"position": 1}),
            make_cursor(),
        ])

        res = await auth_client.put("/profile/photos/1/move", json={"to": 3})
        assert res.status_code == 200
        assert "1" in res.json()["message"]
        assert "3" in res.json()["message"]

    async def test_move_to_occupied_position_swaps(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"position": 2}),
            make_cursor(),
        ])

        res = await auth_client.put("/profile/photos/2/move", json={"to": 4})
        assert res.status_code == 200
        assert mock_db.execute.call_count == 2

    async def test_source_not_found_returns_404(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone=None))

        res = await auth_client.put("/profile/photos/2/move", json={"to": 4})
        assert res.status_code == 404

    async def test_same_position_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/photos/2/move", json={"to": 2})
        assert res.status_code == 400
        assert "same" in res.json()["detail"]

    async def test_invalid_source_position_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/photos/6/move", json={"to": 1})
        assert res.status_code == 400
        assert "1 and 5" in res.json()["detail"]

    async def test_invalid_target_position_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/photos/1/move", json={"to": 0})
        assert res.status_code == 400

    async def test_missing_to_field_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/photos/1/move", json={})
        assert res.status_code == 400
        assert "to must be an integer" in res.json()["detail"]

    async def test_non_integer_to_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/photos/1/move", json={"to": "three"})
        assert res.status_code == 400

    async def test_no_cookie_returns_401(self, client):
        res = await client.put("/profile/photos/1/move", json={"to": 3})
        assert res.status_code == 401

    async def test_db_error_returns_500(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"position": 1}),
            Exception("db down"),
        ])

        res = await auth_client.put("/profile/photos/1/move", json={"to": 3})
        assert res.status_code == 500


class TestListTags:
    async def test_returns_all_tags(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[
            {"name": "cooking"}, {"name": "hiking"}, {"name": "music"},
        ]))

        res = await auth_client.get("/tags")
        assert res.status_code == 200
        assert res.json() == {"tags": ["cooking", "hiking", "music"]}

    async def test_search_filters_tags(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[{"name": "hiking"}]))

        res = await auth_client.get("/tags?search=hik")
        assert res.status_code == 200
        assert res.json() == {"tags": ["hiking"]}

        executed_sql, params = mock_db.execute.call_args_list[-1][0]
        assert "ILIKE" in executed_sql
        assert params == ("%hik%",)

    async def test_empty_tags(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[]))

        res = await auth_client.get("/tags")
        assert res.status_code == 200
        assert res.json() == {"tags": []}

    async def test_no_cookie_returns_401(self, client):
        res = await client.get("/tags")
        assert res.status_code == 401


class TestGetTags:
    async def test_returns_tag_list(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[
            {"name": "hiking"}, {"name": "music"},
        ]))

        res = await auth_client.get("/profile/tags")
        assert res.status_code == 200
        assert res.json() == {"tags": ["hiking", "music"]}

    async def test_empty_tags(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[]))

        res = await auth_client.get("/profile/tags")
        assert res.status_code == 200
        assert res.json() == {"tags": []}

    async def test_no_cookie_returns_401(self, client):
        res = await client.get("/profile/tags")
        assert res.status_code == 401


class TestPutTags:
    async def test_replaces_all_tags(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(
            fetchone={"id": 1},
            fetchall=[{"name": "sport"}, {"name": "cinema"}]
        ))

        res = await auth_client.put("/profile/tags", json={"tags": ["sport", "cinema"]})
        assert res.status_code == 200
        assert res.json()["message"] == "tags updated"

    async def test_empty_list_clears_tags(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor())

        res = await auth_client.put("/profile/tags", json={"tags": []})
        assert res.status_code == 200

    async def test_strips_whitespace_from_tags(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(
            fetchone={"id": 1},
            fetchall=[{"name": "sport"}]
        ))

        res = await auth_client.put("/profile/tags", json={"tags": ["  sport  "]})
        assert res.status_code == 200

    async def test_normalizes_tag_case(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(
            fetchone={"id": 1},
            fetchall=[{"name": "hiking"}, {"name": "music"}]
        ))

        res = await auth_client.put("/profile/tags", json={"tags": ["  Hiking  ", "MUSIC"]})
        assert res.status_code == 200

        existence_check_params = [
            call.args[1][0] for call in mock_db.execute.call_args_list
            if "ANY(%s)" in call.args[0]
        ]
        assert existence_check_params == [["hiking", "music"]]

    async def test_missing_tags_field_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/tags", json={})
        assert res.status_code == 400

    async def test_tags_not_a_list_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/tags", json={"tags": "sport"})
        assert res.status_code == 400
        assert "list" in res.json()["detail"]

    async def test_too_many_tags_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/tags", json={"tags": ["a", "b", "c", "d", "e", "f"]})
        assert res.status_code == 400
        assert "5" in res.json()["detail"]

    async def test_empty_string_tag_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/tags", json={"tags": ["sport", ""]})
        assert res.status_code == 400
        assert "non-empty" in res.json()["detail"]

    async def test_non_string_tag_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put("/profile/tags", json={"tags": [42]})
        assert res.status_code == 400

    async def test_wrong_content_type_returns_415(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.put(
            "/profile/tags",
            content="tags=sport",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert res.status_code == 415

    async def test_no_cookie_returns_401(self, client):
        res = await client.put("/profile/tags", json={"tags": ["sport"]})
        assert res.status_code == 401

    async def test_db_error_returns_500(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=Exception("db down"))

        res = await auth_client.put("/profile/tags", json={"tags": ["sport"]})
        assert res.status_code == 500


class TestDeleteTag:
    async def test_removes_existing_tag(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone={"tag_id": 7}))

        res = await auth_client.delete("/profile/tags/sport")
        assert res.status_code == 200
        assert "sport" in res.json()["message"]

    async def test_removes_tag_regardless_of_case(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone={"tag_id": 7}))

        res = await auth_client.delete("/profile/tags/Sport")
        assert res.status_code == 200

        params = mock_db.execute.call_args_list[-1][0][1]
        assert params == (1, "sport")

    async def test_tag_not_found_returns_404(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone=None))

        res = await auth_client.delete("/profile/tags/unknown")
        assert res.status_code == 404
        assert "not found" in res.json()["detail"]

    async def test_no_cookie_returns_401(self, client):
        res = await client.delete("/profile/tags/sport")
        assert res.status_code == 401
