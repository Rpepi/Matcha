import pytest
from unittest.mock import AsyncMock, patch
from datetime import date
from fastapi.responses import Response
from app.routes.users import _build_orientation_filter, _recalculate_fame

ME_ROW = {
    "gender": "male", "orientation": "hetero",
    "latitude": 48.85, "longitude": 2.35,
    "birth_date": date(1995, 1, 1),
}

BROWSE_ROW = {
    "id": 2, "first_name": "Bob", "last_name": "Smith",
    "gender": "female", "bio": "hey", "birth_date": date(1997, 3, 10),
    "fame_rating": 5, "city": "Lyon", "is_online": False, "last_seen": None,
    "age": 27, "distance_km": 400, "common_tags": 2, "score": 45.0, "photo_position": None,
    "is_liked_by_me": False,
}

USER_ROW = {
    "id": 2, "first_name": "Bob", "last_name": "Smith",
    "gender": "male", "orientation": "heterosexual", "bio": "hey",
    "birth_date": "1995-06-15", "fame_rating": 10, "city": "Lyon",
    "is_online": False, "last_seen": None,
}


def make_cursor(fetchone=None, fetchall=None):
    c = AsyncMock()
    c.fetchone = AsyncMock(return_value=fetchone)
    c.fetchall = AsyncMock(return_value=fetchall or [])
    return c


class TestRecalculateFame:
    async def test_calls_update_with_correct_user_id(self):
        conn = AsyncMock()
        conn.execute = AsyncMock(return_value=AsyncMock())

        await _recalculate_fame(conn, "42")

        query, params = conn.execute.call_args.args
        assert "UPDATE users SET fame_rating" in query
        assert params == ("42", "42", "42")
        assert query.count("%s") == len(params)

    async def test_query_counts_likes_and_matches(self):
        conn = AsyncMock()
        conn.execute = AsyncMock(return_value=AsyncMock())

        await _recalculate_fame(conn, "1")

        query = conn.execute.call_args.args[0]
        assert "FROM likes WHERE liked_id" in query
        assert "EXISTS" in query

    async def test_a_match_is_the_reverse_of_the_received_like(self):
        """A like received from X is a match when the user also likes X: the second
        copy of `likes` must point back at the *liker* of the first one. Comparing it
        to the user's own id looks for "user likes user", which never exists, so no
        match was ever counted (checked against a real database, a mock cannot see it)."""
        conn = AsyncMock()
        conn.execute = AsyncMock(return_value=AsyncMock())

        await _recalculate_fame(conn, "1")

        query = " ".join(conn.execute.call_args.args[0].split())
        assert "l2.liker_id = l1.liked_id AND l2.liked_id = l1.liker_id" in query


class TestOrientationFilter:
    def test_hetero_male_sees_female(self):
        conds, params = _build_orientation_filter("male", "hetero")
        assert "u.gender = %s" in conds
        assert params[0] == "female"
        assert "hetero" in params[1]
        assert "bi" in params[1]

    def test_hetero_female_sees_male(self):
        conds, params = _build_orientation_filter("female", "hetero")
        assert params[0] == "male"

    def test_homo_male_sees_male(self):
        conds, params = _build_orientation_filter("male", "homo")
        assert "u.gender = %s" in conds
        assert params[0] == "male"
        assert "homo" in params[1]
        assert "bi" in params[1]

    def test_bi_has_no_gender_constraint(self):
        conds, params = _build_orientation_filter("male", "bi")
        assert conds == []
        assert params == []

    def test_hetero_other_gender_skips_gender_filter(self):
        conds, params = _build_orientation_filter("other", "hetero")
        assert not any("u.gender" in c for c in conds)


class TestBrowseUsers:
    async def test_returns_scored_list(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=ME_ROW),
            make_cursor(fetchall=[BROWSE_ROW]),
        ])

        res = await auth_client.get("/users")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert data[0]["first_name"] == "Bob"
        assert "distance_km" in data[0]
        assert "common_tags" in data[0]
        assert "score" in data[0]
        assert "email" not in data[0]

    async def test_returns_photo_position_and_like_state(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=ME_ROW),
            make_cursor(fetchall=[{**BROWSE_ROW, "photo_position": 2, "is_liked_by_me": True}]),
        ])

        res = await auth_client.get("/users")
        assert res.status_code == 200
        assert res.json()[0]["photo_position"] == 2
        assert res.json()[0]["is_liked_by_me"] is True

    async def test_placeholders_and_params_stay_aligned(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=ME_ROW),
            make_cursor(fetchall=[]),
        ])

        await auth_client.get("/users")

        query, params = mock_db.execute.call_args_list[1].args
        assert query.count("%s") == len(params)
        # SELECT order: distance (lat, lon), common_tags x2, score (lat, lon), then is_liked_by_me.
        assert "is_liked_by_me" in query
        assert params[:7] == [48.85, 2.35, "1", "1", 48.85, 2.35, "1"]

    async def test_no_location_returns_400(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone={
            **ME_ROW, "latitude": None, "longitude": None,
        }))

        res = await auth_client.get("/users")
        assert res.status_code == 400
        assert "location" in res.json()["detail"]

    async def test_invalid_page_param_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.get("/users?page=abc")
        assert res.status_code == 400

    async def test_invalid_min_age_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.get("/users?min_age=young")
        assert res.status_code == 400

    async def test_age_filter_passed_to_query(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=ME_ROW),
            make_cursor(fetchall=[]),
        ])

        res = await auth_client.get("/users?min_age=20&max_age=30")
        assert res.status_code == 200
        query_str = str(mock_db.execute.call_args_list[1].args[0])
        assert "AGE" in query_str

    async def test_pagination_offset(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=ME_ROW),
            make_cursor(fetchall=[]),
        ])

        res = await auth_client.get("/users?page=2")
        assert res.status_code == 200
        # offset = page * 20 = 40
        params = mock_db.execute.call_args_list[1].args[1]
        assert params[-1] == 40

    async def test_empty_result(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=ME_ROW),
            make_cursor(fetchall=[]),
        ])

        res = await auth_client.get("/users")
        assert res.status_code == 200
        assert res.json() == []

    async def test_no_cookie_returns_401(self, client):
        res = await client.get("/users")
        assert res.status_code == 401


class TestGetUserProfile:
    async def test_returns_public_profile(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),           # _is_blocked
            make_cursor(fetchone=USER_ROW),       # _get_user_or_404
            make_cursor(fetchall=[{"position": 1, "path": "/p.jpg", "is_profile": True}]),
            make_cursor(fetchall=[{"name": "sport"}]),
            make_cursor(fetchone={"liked_by_me": False, "liked_by_them": False}),
            make_cursor(fetchone=None),           # visits upsert: no row -> no notification
        ])

        res = await auth_client.get("/users/2")
        assert res.status_code == 200
        data = res.json()
        assert data["first_name"] == "Bob"
        assert "email" not in data
        assert "password_hash" not in data
        assert len(data["photos"]) == 1
        assert data["tags"] == ["sport"]
        assert data["is_liked_by_me"] is False
        assert data["is_match"] is False

    async def test_liked_but_not_matched(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),
            make_cursor(fetchone=USER_ROW),
            make_cursor(fetchall=[]),
            make_cursor(fetchall=[]),
            make_cursor(fetchone={"liked_by_me": True, "liked_by_them": False}),
            make_cursor(fetchone=None),  # visits upsert: no row -> no notification
        ])

        res = await auth_client.get("/users/2")
        assert res.status_code == 200
        data = res.json()
        assert data["is_liked_by_me"] is True
        assert data["is_match"] is False

    async def test_mutual_like_is_match(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),
            make_cursor(fetchone=USER_ROW),
            make_cursor(fetchall=[]),
            make_cursor(fetchall=[]),
            make_cursor(fetchone={"liked_by_me": True, "liked_by_them": True}),
            make_cursor(fetchone=None),  # visits upsert: no row -> no notification
        ])

        res = await auth_client.get("/users/2")
        assert res.status_code == 200
        data = res.json()
        assert data["is_liked_by_me"] is True
        assert data["is_match"] is True

    async def test_own_profile_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.get("/users/1")
        assert res.status_code == 400

    async def test_blocked_user_returns_404(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone={"1": 1}))

        res = await auth_client.get("/users/2")
        assert res.status_code == 404

    async def test_unknown_user_returns_404(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),   # not blocked
            make_cursor(fetchone=None),   # user not found
        ])

        res = await auth_client.get("/users/999")
        assert res.status_code == 404

    async def test_first_visit_upserts_and_notifies(self, auth_client, mock_db, mock_redis):
        """No prior visit (or one older than 15 days): the upsert returns a
        row, so a "visit" notification is inserted and published."""
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),
            make_cursor(fetchone=USER_ROW),
            make_cursor(fetchall=[]),
            make_cursor(fetchall=[]),
            make_cursor(fetchone={"liked_by_me": False, "liked_by_them": False}),
            make_cursor(fetchone={"id": 42}),  # visits upsert: fresh row -> notify
            make_cursor(),                     # INSERT notification
        ])

        res = await auth_client.get("/users/2")
        assert res.status_code == 200

        calls = [str(c.args[0]) for c in mock_db.execute.call_args_list]
        assert any("INSERT INTO visits" in q for q in calls)
        assert any("INSERT INTO notifications" in q for q in calls)
        mock_redis.publish.assert_called_once()

    async def test_repeat_visit_within_15_days_skips_notification(self, auth_client, mock_db, mock_redis):
        """A visit less than 15 days old already exists: ON CONFLICT ... WHERE
        is false, the upsert touches nothing and returns no row, so no
        notification is inserted or published."""
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),
            make_cursor(fetchone=USER_ROW),
            make_cursor(fetchall=[]),
            make_cursor(fetchall=[]),
            make_cursor(fetchone={"liked_by_me": False, "liked_by_them": False}),
            make_cursor(fetchone=None),  # visits upsert: WHERE false -> no row
        ])

        res = await auth_client.get("/users/2")
        assert res.status_code == 200

        calls = [str(c.args[0]) for c in mock_db.execute.call_args_list]
        assert any("INSERT INTO visits" in q for q in calls)
        assert not any("INSERT INTO notifications" in q for q in calls)
        mock_redis.publish.assert_not_called()

    async def test_no_cookie_returns_401(self, client):
        res = await client.get("/users/2")
        assert res.status_code == 401


class TestGetUserPhoto:
    async def test_returns_photo_file(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),  # _is_blocked
            make_cursor(fetchone={"path": "/backend/uploads/2/a.jpg"}),
        ])

        with patch("app.routes.users.os.path.isfile", return_value=True), \
            patch("app.routes.users.FileResponse", return_value=Response(content=b"jpeg-bytes", media_type="image/jpeg")) as mock_file_response:
            res = await auth_client.get("/users/2/photos/1")

        assert res.status_code == 200
        mock_file_response.assert_called_once_with(
            "/backend/uploads/2/a.jpg", media_type="image/jpeg", headers={"Cache-Control": "private, max-age=60"}
        )

    async def test_own_id_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.get("/users/1/photos/1")
        assert res.status_code == 400

    async def test_invalid_position_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.get("/users/2/photos/6")
        assert res.status_code == 400
        assert "1-5" in res.json()["detail"]

    async def test_blocked_user_returns_404(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone={"1": 1}))

        res = await auth_client.get("/users/2/photos/1")
        assert res.status_code == 404

    async def test_photo_not_found_returns_404(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),   # not blocked
            make_cursor(fetchone=None),   # no photo at that position
        ])

        res = await auth_client.get("/users/2/photos/3")
        assert res.status_code == 404

    async def test_missing_file_on_disk_returns_404(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),
            make_cursor(fetchone={"path": "/backend/uploads/2/missing.jpg"}),
        ])

        with patch("app.routes.users.os.path.isfile", return_value=False):
            res = await auth_client.get("/users/2/photos/1")

        assert res.status_code == 404

    async def test_no_cookie_returns_401(self, client):
        res = await client.get("/users/2/photos/1")
        assert res.status_code == 401


class TestLikeUser:
    async def test_like_creates_notification(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),              # not blocked
            make_cursor(fetchone={"1": 1}),          # user exists
            make_cursor(fetchone={"exists": True}),  # has profile picture
            make_cursor(fetchone={"id": 10}),        # INSERT like → new like
            make_cursor(fetchone=None),              # no mutual like
            make_cursor(),                           # notify 'like'
            make_cursor(),                           # recalculate target fame
        ])

        res = await auth_client.post("/users/2/like")
        assert res.status_code == 200
        assert res.json()["message"] == "liked"

    async def test_mutual_like_creates_match(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),              # not blocked
            make_cursor(fetchone={"1": 1}),          # user exists
            make_cursor(fetchone={"exists": True}),  # has profile picture
            make_cursor(fetchone={"id": 10}),        # INSERT like → new
            make_cursor(fetchone={"1": 1}),          # mutual like found
            make_cursor(),                           # notify target 'match'
            make_cursor(),                           # notify self 'match'
            make_cursor(),                           # recalculate liker fame
            make_cursor(),                           # recalculate target fame
        ])

        res = await auth_client.post("/users/2/like")
        assert res.status_code == 200
        assert res.json()["message"] == "match"

    async def test_already_liked_is_idempotent(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),
            make_cursor(fetchone={"1": 1}),
            make_cursor(fetchone={"exists": True}),  # has profile picture
            make_cursor(fetchone=None),              # ON CONFLICT → no RETURNING row
        ])

        res = await auth_client.post("/users/2/like")
        assert res.status_code == 200
        assert res.json()["message"] == "already liked"

    async def test_target_without_profile_picture_returns_404(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),               # not blocked
            make_cursor(fetchone={"1": 1}),           # user exists
            make_cursor(fetchone={"exists": False}),  # no profile picture
        ])

        res = await auth_client.post("/users/2/like")
        assert res.status_code == 404
        assert "profile picture" in res.json()["detail"]

    async def test_like_self_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.post("/users/1/like")
        assert res.status_code == 400

    async def test_blocked_user_returns_404(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone={"1": 1}))

        res = await auth_client.post("/users/2/like")
        assert res.status_code == 404

    async def test_unknown_user_returns_404(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),
            make_cursor(fetchone=None),
        ])

        res = await auth_client.post("/users/999/like")
        assert res.status_code == 404

    async def test_no_cookie_returns_401(self, client):
        res = await client.post("/users/2/like")
        assert res.status_code == 401


class TestUnlikeUser:
    async def test_unlike_removes_like(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"id": 10}),   # DELETE RETURNING
            make_cursor(),                       # notify 'unlike'
            make_cursor(),                       # recalculate target fame
        ])

        res = await auth_client.delete("/users/2/like")
        assert res.status_code == 200
        assert res.json()["message"] == "unliked"

    async def test_like_not_found_returns_404(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone=None))

        res = await auth_client.delete("/users/2/like")
        assert res.status_code == 404

    async def test_no_cookie_returns_401(self, client):
        res = await client.delete("/users/2/like")
        assert res.status_code == 401

    async def test_db_error_returns_500(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=Exception("db down"))

        res = await auth_client.delete("/users/2/like")
        assert res.status_code == 500


class TestBlockUser:
    async def test_block_removes_mutual_likes(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"1": 1}),   # user exists
            make_cursor(),                    # INSERT block
            make_cursor(),                    # DELETE likes
            make_cursor(),                    # fame of the blocker
            make_cursor(),                    # fame of the blocked user
        ])

        res = await auth_client.post("/users/2/block")
        assert res.status_code == 200
        assert res.json()["message"] == "user blocked"

        calls = [str(c.args[0]) for c in mock_db.execute.call_args_list]
        assert any("DELETE FROM likes" in q for q in calls)

    async def test_block_recalculates_both_fame_ratings(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[make_cursor(fetchone={"1": 1})] + [make_cursor()] * 4)

        await auth_client.post("/users/2/block")

        fame_updates = [c for c in mock_db.execute.call_args_list if "UPDATE users SET fame_rating" in str(c.args[0])]
        assert [c.args[1][-1] for c in fame_updates] == ["1", "2"]  # the blocker, then the blocked user
        mock_db.commit.assert_awaited_once()

    async def test_block_self_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.post("/users/1/block")
        assert res.status_code == 400

    async def test_unknown_user_returns_404(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone=None))

        res = await auth_client.post("/users/999/block")
        assert res.status_code == 404

    async def test_block_idempotent(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[make_cursor(fetchone={"1": 1})] + [make_cursor()] * 4)

        res = await auth_client.post("/users/2/block")
        assert res.status_code == 200

    async def test_no_cookie_returns_401(self, client):
        res = await client.post("/users/2/block")
        assert res.status_code == 401


class TestUnblockUser:
    async def test_unblock_existing_block(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone={"id": 5}))

        res = await auth_client.delete("/users/2/block")
        assert res.status_code == 200
        assert res.json()["message"] == "user unblocked"

    async def test_block_not_found_returns_404(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone=None))

        res = await auth_client.delete("/users/2/block")
        assert res.status_code == 404

    async def test_no_cookie_returns_401(self, client):
        res = await client.delete("/users/2/block")
        assert res.status_code == 401


class TestReportUser:
    async def test_report_with_reason(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"1": 1}),      # user exists
            make_cursor(fetchone={"id": 1}),     # INSERT RETURNING
        ])

        res = await auth_client.post("/users/2/report", json={"reason": "fake profile"})
        assert res.status_code == 200
        assert res.json()["message"] == "user reported"

    async def test_report_without_reason(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"1": 1}),
            make_cursor(fetchone={"id": 1}),
        ])

        res = await auth_client.post("/users/2/report", json={})
        assert res.status_code == 200

    async def test_already_reported_is_idempotent(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"1": 1}),
            make_cursor(fetchone=None),          # ON CONFLICT → no RETURNING
        ])

        res = await auth_client.post("/users/2/report", json={})
        assert res.status_code == 200
        assert res.json()["message"] == "already reported"

    async def test_non_string_reason_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.post("/users/2/report", json={"reason": 42})
        assert res.status_code == 400

    async def test_report_self_returns_400(self, auth_client, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        res = await auth_client.post("/users/1/report", json={})
        assert res.status_code == 400

    async def test_unknown_user_returns_404(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone=None))

        res = await auth_client.post("/users/999/report", json={})
        assert res.status_code == 404

    async def test_no_cookie_returns_401(self, client):
        res = await client.post("/users/2/report", json={})
        assert res.status_code == 401

    async def test_db_error_returns_500(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"1": 1}),
            Exception("db down"),
        ])

        res = await auth_client.post("/users/2/report", json={})
        assert res.status_code == 500
