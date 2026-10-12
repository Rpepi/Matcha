import pytest
from unittest.mock import AsyncMock, patch
from datetime import date
from fastapi.responses import Response
from app.routes.users import _build_orientation_filter, _recalculate_fame, is_interested

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
    "id": 2, "username": "bob.smith", "first_name": "Bob", "last_name": "Smith",
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

        await _recalculate_fame(conn, 42)

        query, params = conn.execute.call_args.args
        assert "UPDATE users SET fame_rating" in query
        assert params == (42, 42, 42)
        assert query.count("%s") == len(params)

    async def test_query_counts_likes_and_matches(self):
        conn = AsyncMock()
        conn.execute = AsyncMock(return_value=AsyncMock())

        await _recalculate_fame(conn, 1)

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

        await _recalculate_fame(conn, 1)

        query = " ".join(conn.execute.call_args.args[0].split())
        assert "l2.liker_id = l1.liked_id AND l2.liked_id = l1.liker_id" in query


class TestIsInterested:
    @pytest.mark.parametrize("orientation, gender, other, expected", [
        ("hetero", "male", "female", True),
        ("hetero", "male", "male", False),
        ("hetero", "male", "other", False),
        ("hetero", "female", "male", True),
        ("hetero", "female", "female", False),
        ("hetero", "other", "male", True),
        ("hetero", "other", "female", True),
        ("hetero", "other", "other", False),
        ("homo", "male", "male", True),
        ("homo", "male", "female", False),
        ("homo", "other", "other", True),
        ("bi", "male", "other", True),
        ("bi", "female", "female", True),
        (None, "male", "male", True),  # no orientation given: bisexual
    ])
    def test_truth_table(self, orientation, gender, other, expected):
        assert is_interested(orientation, gender, other) is expected


def filter_keeps(me_gender, me_orientation, them_gender, them_orientation) -> bool:
    """Evaluate the conditions of _build_orientation_filter on one candidate, in Python."""
    conds, params = _build_orientation_filter(me_gender, me_orientation)
    values = iter(params)
    for cond in conds:
        allowed = next(values)
        if cond == "u.gender = ANY(%s)":
            if them_gender not in allowed:
                return False
        elif cond.startswith("COALESCE(u.orientation, 'bi')"):
            if f"{them_orientation or 'bi'}:{them_gender}" not in allowed:
                return False
        else:
            raise AssertionError(f"unexpected condition {cond}")
    return True


class TestOrientationFilter:
    def test_hetero_male_sees_hetero_and_bi_women(self):
        assert filter_keeps("male", "hetero", "female", "hetero")
        assert filter_keeps("male", "hetero", "female", "bi")

    def test_hetero_male_does_not_see_lesbians(self):
        assert not filter_keeps("male", "hetero", "female", "homo")

    def test_hetero_male_does_not_see_men(self):
        assert not filter_keeps("male", "hetero", "male", "bi")

    def test_homo_male_sees_gay_and_bi_men_only(self):
        assert filter_keeps("male", "homo", "male", "homo")
        assert filter_keeps("male", "homo", "male", "bi")
        assert not filter_keeps("male", "homo", "male", "hetero")
        assert not filter_keeps("male", "homo", "female", "bi")

    def test_bi_male_is_not_shown_people_who_would_not_be_interested(self):
        """Interest must go both ways: a hetero man or a lesbian never wants a man."""
        assert not filter_keeps("male", "bi", "male", "hetero")
        assert not filter_keeps("male", "bi", "female", "homo")
        assert filter_keeps("male", "bi", "male", "homo")
        assert filter_keeps("male", "bi", "female", "hetero")
        assert filter_keeps("male", "bi", "other", "bi")

    def test_no_orientation_counts_as_bi(self):
        assert filter_keeps("female", None, "male", None)
        assert filter_keeps("female", None, "female", "bi")

    def test_bi_adds_no_gender_condition(self):
        conds, _ = _build_orientation_filter("male", "bi")
        assert "u.gender = ANY(%s)" not in conds


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
        assert params[:7] == [48.85, 2.35, 1, 1, 48.85, 2.35, 1]

    @staticmethod
    async def browse(auth_client, mock_db, mock_redis, url):
        """Run GET ``url`` against an empty result and return the (query, params) sent."""
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=ME_ROW),
            make_cursor(fetchall=[]),
        ])
        res = await auth_client.get(url)
        assert res.status_code == 200, res.text
        return mock_db.execute.call_args_list[1].args

    async def test_default_order_is_best_score_first_with_a_stable_tie_break(self, auth_client, mock_db, mock_redis):
        query, _ = await self.browse(auth_client, mock_db, mock_redis, "/users")
        assert "ORDER BY score DESC, u.id" in query

    @pytest.mark.parametrize("sort, expected", [
        ("score", "ORDER BY score DESC, u.id"),
        ("age", "ORDER BY age ASC, u.id"),
        ("distance", "ORDER BY distance_km ASC, u.id"),
        ("fame", "ORDER BY u.fame_rating DESC, u.id"),
        ("tags", "ORDER BY common_tags DESC, u.id"),
    ])
    async def test_each_sort_uses_its_own_default_direction(self, auth_client, mock_db, mock_redis, sort, expected):
        query, _ = await self.browse(auth_client, mock_db, mock_redis, f"/users?sort={sort}")
        assert expected in query

    @pytest.mark.parametrize("order, expected", [
        ("asc", "ORDER BY u.fame_rating ASC, u.id"),
        ("desc", "ORDER BY u.fame_rating DESC, u.id"),
    ])
    async def test_order_overrides_the_default_direction(self, auth_client, mock_db, mock_redis, order, expected):
        query, _ = await self.browse(auth_client, mock_db, mock_redis, f"/users?sort=fame&order={order}")
        assert expected in query

    async def test_sorting_does_not_change_the_placeholders(self, auth_client, mock_db, mock_redis):
        query, params = await self.browse(auth_client, mock_db, mock_redis, "/users?sort=distance&order=desc")
        assert query.count("%s") == len(params)

    @pytest.mark.parametrize("url", [
        "/users?sort=name",
        "/users?sort=",
        "/users?sort=SCORE",
        "/users?sort=score;DROP TABLE users",
        "/users?sort=score,u.id",
        "/users?sort=(SELECT 1)",
        "/users?sort=age&order=sideways",
        "/users?order=DESC",
        "/users?order=asc;--",
    ])
    async def test_unknown_sort_or_order_is_400_before_the_database(self, auth_client, mock_db, mock_redis, url):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock()

        res = await auth_client.get(url)

        assert res.status_code == 400
        mock_db.execute.assert_not_called()

    async def test_named_tags_must_all_be_carried(self, auth_client, mock_db, mock_redis):
        query, params = await self.browse(auth_client, mock_db, mock_redis, "/users?tags=beach,Tech")
        assert "t.name = ANY(%s)" in query and ") = %s" in query
        # Lowercased, as the vocabulary is, followed by how many of them must match.
        assert params[-3:-1] == [["beach", "tech"], 2]
        assert query.count("%s") == len(params)

    async def test_repeated_tag_names_are_merged(self, auth_client, mock_db, mock_redis):
        _, params = await self.browse(auth_client, mock_db, mock_redis, "/users?tags=beach,beach,BEACH")
        assert ["beach"] in params
        assert params[params.index(["beach"]) + 1] == 1

    async def test_no_tags_param_adds_no_tag_condition(self, auth_client, mock_db, mock_redis):
        query, _ = await self.browse(auth_client, mock_db, mock_redis, "/users?tags=")
        assert "t.name = ANY(%s)" not in query

    @pytest.mark.parametrize("value", [
        "a,b,c,d,e,f",          # six names
        "beach,,tech",          # an empty name
        "t" * 51,               # too long
        "be\x00ach",            # NUL
    ])
    async def test_bad_tags_param_is_400_before_the_database(self, auth_client, mock_db, mock_redis, value):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock()

        res = await auth_client.get("/users", params={"tags": value})

        assert res.status_code == 400
        mock_db.execute.assert_not_called()

    async def test_tag_names_are_never_put_in_the_query_text(self, auth_client, mock_db, mock_redis):
        query, params = await self.browse(auth_client, mock_db, mock_redis, "/users?tags=beach' OR '1'='1")
        assert "OR '1'='1" not in query
        assert ["beach' or '1'='1"] in params

    async def test_max_fame_is_a_parameterized_upper_bound(self, auth_client, mock_db, mock_redis):
        query, params = await self.browse(auth_client, mock_db, mock_redis, "/users?max_fame=40")
        assert "u.fame_rating <= %s" in query
        assert 40 in params
        assert query.count("%s") == len(params)

    @pytest.mark.parametrize("value", ["-1", "1000001", "abc", "4.5", ""])
    async def test_bad_max_fame_is_400(self, auth_client, mock_db, mock_redis, value):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock()

        res = await auth_client.get("/users", params={"max_fame": value})

        assert res.status_code == 400
        mock_db.execute.assert_not_called()

    async def test_every_filter_together_keeps_params_in_query_order(self, auth_client, mock_db, mock_redis):
        url = "/users?min_age=20&max_age=40&max_distance=50&min_fame=1&max_fame=90&min_tags=1&tags=beach,tech&sort=tags&order=asc&page=2"
        query, params = await self.browse(auth_client, mock_db, mock_redis, url)

        assert query.count("%s") == len(params)
        # After the 7 SELECT-list parameters: the WHERE ones in the order the
        # conditions are written, then the page offset (page 2 -> 40).
        assert params[7:] == [
            1, 1, 1,                      # user, blocks (x2)
            ["female"],                   # genders the viewer (male, hetero) is into
            ["homo:male", "hetero:female", "hetero:other", "bi:male", "bi:female", "bi:other"],  # who is into him
            20, 40,                       # min_age, max_age
            48.85, 2.35, 50,              # max_distance
            1, 90,                        # min_fame, max_fame
            1, 1,                         # min_tags: viewer's id, minimum
            ["beach", "tech"], 2,         # named tags and how many must match
            40,
        ]
        assert "ORDER BY common_tags ASC, u.id" in query

    async def test_searched_place_moves_the_center_of_max_distance(self, auth_client, mock_db, mock_redis):
        query, params = await self.browse(
            auth_client, mock_db, mock_redis, "/users?max_distance=30&lat=18.7883&lon=98.9853"
        )
        assert query.count("%s") == len(params)
        # Distance shown and sorted on stays from the viewer; the radius is around the place.
        assert params[:2] == [48.85, 2.35]
        assert params[-4:] == [18.7883, 98.9853, 30, 0]

    async def test_without_a_place_the_radius_is_around_the_viewer(self, auth_client, mock_db, mock_redis):
        _, params = await self.browse(auth_client, mock_db, mock_redis, "/users?max_distance=30")
        assert params[-4:] == [48.85, 2.35, 30, 0]

    @pytest.mark.parametrize("query_string", [
        "lat=10", "lon=10", "lat=91&lon=0", "lat=0&lon=181", "lat=nan&lon=0",
        "lat=1e3&lon=0", "lat=abc&lon=0", "lat=&lon=0",
    ])
    async def test_bad_place_is_400_before_the_database(self, auth_client, mock_db, mock_redis, query_string):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock()

        res = await auth_client.get(f"/users?{query_string}")

        assert res.status_code == 400
        mock_db.execute.assert_not_called()

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
        assert data["username"] == "bob.smith"
        assert "email" not in data
        assert "password_hash" not in data
        assert len(data["photos"]) == 1
        assert data["tags"] == ["sport"]
        assert data["is_liked_by_me"] is False
        assert data["likes_me"] is False
        assert data["is_match"] is False

    async def test_query_selects_the_username(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),
            make_cursor(fetchone=USER_ROW),
            make_cursor(fetchall=[]),
            make_cursor(fetchall=[]),
            make_cursor(fetchone={"liked_by_me": False, "liked_by_them": False}),
            make_cursor(fetchone=None),
        ])

        await auth_client.get("/users/2")

        query = mock_db.execute.await_args_list[1].args[0]
        assert "username" in query
        assert "email" not in query and "password_hash" not in query

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
        assert data["likes_me"] is False
        assert data["is_match"] is False

    async def test_they_like_me_but_i_have_not_liked_back(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),
            make_cursor(fetchone=USER_ROW),
            make_cursor(fetchall=[]),
            make_cursor(fetchall=[]),
            make_cursor(fetchone={"liked_by_me": False, "liked_by_them": True}),
            make_cursor(fetchone=None),  # visits upsert: no row -> no notification
        ])

        res = await auth_client.get("/users/2")
        assert res.status_code == 200
        data = res.json()
        assert data["likes_me"] is True
        assert data["is_liked_by_me"] is False
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
        assert data["likes_me"] is True
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
        """No recent visit from this user: the visit is recorded and a "visit"
        notification is inserted and published."""
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),
            make_cursor(fetchone=USER_ROW),
            make_cursor(fetchall=[]),
            make_cursor(fetchall=[]),
            make_cursor(fetchone={"liked_by_me": False, "liked_by_them": False, "distance_km": 12}),
            make_cursor(fetchone={"notify": True}),  # visits upsert: no recent visit -> notify
            make_cursor(),                           # INSERT notification
        ])

        res = await auth_client.get("/users/2")
        assert res.status_code == 200

        calls = [str(c.args[0]) for c in mock_db.execute.call_args_list]
        assert any("INSERT INTO visits" in q for q in calls)
        assert any("INSERT INTO notifications" in q for q in calls)
        mock_redis.publish.assert_called_once()
        assert res.json()["distance_km"] == 12

    async def test_every_visit_moves_the_date_to_now(self, auth_client, mock_db, mock_redis):
        """The history shows the latest visit: a repeat visit always updates the date."""
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),
            make_cursor(fetchone=USER_ROW),
            make_cursor(fetchall=[]),
            make_cursor(fetchall=[]),
            make_cursor(fetchone={"liked_by_me": False, "liked_by_them": False}),
            make_cursor(fetchone={"notify": False}),
        ])

        await auth_client.get("/users/2")

        upsert = next(str(c.args[0]) for c in mock_db.execute.call_args_list if "INSERT INTO visits" in str(c.args[0]))
        assert "DO UPDATE SET created_at = NOW()" in upsert
        assert "WHERE visits.created_at" not in upsert  # no condition: the date always moves

    async def test_repeat_visit_within_the_cooldown_skips_notification(self, auth_client, mock_db, mock_redis):
        """The same visitor came seconds ago (a reload): recorded, not notified again."""
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),
            make_cursor(fetchone=USER_ROW),
            make_cursor(fetchall=[]),
            make_cursor(fetchall=[]),
            make_cursor(fetchone={"liked_by_me": False, "liked_by_them": False}),
            make_cursor(fetchone={"notify": False}),  # visits upsert: visited seconds ago
        ])

        res = await auth_client.get("/users/2")
        assert res.status_code == 200

        calls = [str(c.args[0]) for c in mock_db.execute.call_args_list]
        assert any("INSERT INTO visits" in q for q in calls)
        assert not any("INSERT INTO notifications" in q for q in calls)
        mock_redis.publish.assert_not_called()
        assert res.json()["distance_km"] is None

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

    async def test_user_without_profile_picture_cannot_like_returns_403(self, auth_client, mock_db, mock_redis):
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),               # not blocked
            make_cursor(fetchone={"1": 1}),           # user exists
            make_cursor(fetchone={"exists": False}),  # the liker has no profile picture
        ])

        res = await auth_client.post("/users/2/like")
        assert res.status_code == 403
        assert "profile picture" in res.json()["detail"]
        assert mock_db.execute.await_count == 3  # nothing was written

    async def test_the_picture_checked_is_the_likers_not_the_targets(self, auth_client, mock_db, mock_redis):
        # The target (2) may have no picture at all, as every seeded user.
        mock_redis.get = AsyncMock(return_value="1")
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),
            make_cursor(fetchone={"1": 1}),
            make_cursor(fetchone={"exists": True}),
            make_cursor(fetchone=None),              # ON CONFLICT: already liked
        ])

        res = await auth_client.post("/users/2/like")
        assert res.status_code == 200

        query, params = mock_db.execute.await_args_list[2].args
        assert "FROM photos" in query and "is_profile = true" in query
        assert [int(p) for p in params] == [1]  # the current user, not 2

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
        assert [c.args[1][-1] for c in fame_updates] == [1, 2]  # the blocker, then the blocked user
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
