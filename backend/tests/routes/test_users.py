import pytest
from unittest.mock import AsyncMock
from datetime import date
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
    "age": 27, "distance_km": 400, "common_tags": 2, "score": 45.0, "photo": None,
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
        assert params == ("42", "42", "42", "42")

    async def test_query_counts_likes_and_matches(self):
        conn = AsyncMock()
        conn.execute = AsyncMock(return_value=AsyncMock())

        await _recalculate_fame(conn, "1")

        query = conn.execute.call_args.args[0]
        assert "FROM likes WHERE liked_id" in query
        assert "EXISTS" in query


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
            make_cursor(),                        # INSERT visit
            make_cursor(),                        # INSERT notification
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
            make_cursor(),
            make_cursor(),
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
            make_cursor(),
            make_cursor(),
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

    async def test_records_visit(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),
            make_cursor(fetchone=USER_ROW),
            make_cursor(fetchall=[]),
            make_cursor(fetchall=[]),
            make_cursor(fetchone={"liked_by_me": False, "liked_by_them": False}),
            make_cursor(),
            make_cursor(),
        ])

        await auth_client.get("/users/2")
        calls = [str(c.args[0]) for c in mock_db.execute.call_args_list]
        assert any("INSERT INTO visits" in q for q in calls)

    async def test_no_cookie_returns_401(self, client):
        res = await client.get("/users/2")
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
        ])

        res = await auth_client.post("/users/2/block")
        assert res.status_code == 200
        assert res.json()["message"] == "user blocked"

        calls = [str(c.args[0]) for c in mock_db.execute.call_args_list]
        assert any("DELETE FROM likes" in q for q in calls)

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
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"1": 1}),
            make_cursor(),
            make_cursor(),
        ])

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
