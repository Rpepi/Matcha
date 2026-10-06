"""Hostile-input tests for every JSON/query/path input.

Each case must be refused with a 4xx *before* the database is reached: with
a mocked DB a NUL byte or an oversized id would not crash anything, so
``mock_db.execute.assert_not_called()`` is what proves the validation layer
caught it (against the real PostgreSQL these inputs used to end in a 500).
"""
import json
import pytest
from unittest.mock import AsyncMock, patch

NUL = "\x00"
SURROGATE = "\ud800"
HUGE_ID = 99999999999999999999


def make_cursor(fetchone=None, fetchall=None):
    c = AsyncMock()
    c.fetchone = AsyncMock(return_value=fetchone)
    c.fetchall = AsyncMock(return_value=fetchall or [])
    return c


async def send(client, method: str, path: str, body):
    """Send ``body`` as JSON.

    ``json.dumps`` (ASCII-only output) is used rather than httpx's ``json=``
    so lone surrogates and NaN reach the server as escapes, exactly as a
    hostile client would send them.
    """
    return await client.request(
        method, path, content=json.dumps(body), headers={"content-type": "application/json"}
    )


@pytest.fixture
def authed(auth_client, mock_redis):
    mock_redis.get = AsyncMock(return_value="1")
    return auth_client


# ── every JSON endpoint: wrong body shapes ────────────────────────────────────

JSON_ENDPOINTS = [
    ("POST", "/auth/login"),
    ("POST", "/auth/forgot-password"),
    ("POST", "/auth/reset-password"),
    ("POST", "/auth/register"),
    ("PUT", "/profile/me"),
    ("PUT", "/profile/location"),
    ("PUT", "/profile/tags"),
    ("PUT", "/profile/photos/1/move"),
    ("POST", "/users/2/report"),
]


@pytest.mark.parametrize("method,path", JSON_ENDPOINTS)
class TestEveryJsonEndpoint:
    @pytest.mark.parametrize("body", [[], [1, 2], "text", 42, None, True, [{"email": "a@b.co"}]])
    async def test_non_object_body_is_400(self, authed, mock_db, method, path, body):
        res = await send(authed, method, path, body)
        assert res.status_code == 400
        mock_db.execute.assert_not_called()

    @pytest.mark.parametrize("raw", ['{"a": NaN}', '{"a": Infinity}', '{"a": -Infinity}', "{", "", "\xff"])
    async def test_malformed_json_is_400(self, authed, mock_db, method, path, raw):
        res = await authed.request(method, path, content=raw.encode("latin-1"),
                                   headers={"content-type": "application/json"})
        assert res.status_code == 400
        mock_db.execute.assert_not_called()

    async def test_deeply_nested_json_is_400(self, authed, mock_db, method, path):
        res = await authed.request(method, path, content=b"[" * 30_000 + b"]" * 30_000,
                                   headers={"content-type": "application/json"})
        assert res.status_code == 400
        mock_db.execute.assert_not_called()

    async def test_oversized_body_is_413(self, authed, mock_db, method, path):
        res = await send(authed, method, path, {"bio": "x" * 100_000})
        assert res.status_code == 413
        mock_db.execute.assert_not_called()

    async def test_wrong_content_type_is_415(self, authed, mock_db, method, path):
        res = await authed.request(method, path, content=b"{}", headers={"content-type": "text/plain"})
        assert res.status_code == 415
        mock_db.execute.assert_not_called()


# ── auth ──────────────────────────────────────────────────────────────────────

class TestLoginInput:
    @pytest.mark.parametrize("body", [
        {"email": f"a{NUL}b@x.co", "password": "secret1!"},
        {"email": NUL, "password": "secret1!"},
        {"email": "a@b.co", "password": f"pw{NUL}"},
        {"email": "a@b.co", "password": SURROGATE},
        {"email": SURROGATE, "password": "secret1!"},
        {"email": "a" * 101, "password": "secret1!"},
        {"email": "a@b.co", "password": "p" * 129},
        {"email": "a@b.co", "password": "p" * 1_000_000},
        {"email": 5, "password": "secret1!"},
        {"email": ["a@b.co"], "password": "secret1!"},
        {"email": {"a": 1}, "password": "secret1!"},
        {"email": "a@b.co", "password": 123},
        {"email": "a@b.co", "password": None},
        {"email": "a@b.co", "password": "   "},
        {"email": "   ", "password": "secret1!"},
        {"email": "a@b.co"},
        {"password": "secret1!"},
        {},
        {"username": f"al{NUL}ice", "password": "secret1!"},
        {"username": SURROGATE, "password": "secret1!"},
        {"username": "a" * 101, "password": "secret1!"},
        {"username": 5, "password": "secret1!"},
        {"username": None, "password": "secret1!"},
        {"username": ["alice"], "password": "secret1!"},
        {"username": "   ", "password": "secret1!"},
    ])
    async def test_bad_login_is_400_and_never_hits_db(self, client, mock_db, body):
        # 1 MB body is > 64 KB, so that case is a 413 rather than a 400.
        res = await send(client, "POST", "/auth/login", body)
        assert res.status_code in (400, 413)
        mock_db.execute.assert_not_called()

    async def test_password_at_the_limit_is_processed(self, client, mock_db):
        res = await send(client, "POST", "/auth/login", {"email": "a@b.co", "password": "p" * 64})
        assert res.status_code == 401 # got as far as the credential check
        mock_db.execute.assert_called_once()

    async def test_email_is_stripped_before_lookup(self, client, mock_db):
        await send(client, "POST", "/auth/login", {"email": "  a@b.co  ", "password": "secret1!"})
        assert mock_db.execute.call_args.args[1] == ("a@b.co",)


class TestForgotPasswordInput:
    @pytest.mark.parametrize("body", [
        {"email": f"a{NUL}b@x.co"},
        {"email": SURROGATE},
        {"email": "a" * 101},
        {"email": 5},
        {"email": None},
        {"email": ["a@b.co"]},
        {},
    ])
    async def test_bad_email_is_400_and_never_hits_db(self, client, mock_db, body):
        res = await send(client, "POST", "/auth/forgot-password", body)
        assert res.status_code == 400
        mock_db.execute.assert_not_called()

    async def test_unknown_but_well_formed_email_still_gets_the_generic_answer(self, client):
        res = await send(client, "POST", "/auth/forgot-password", {"email": "nobody@x.co"})
        assert res.status_code == 200


class TestRegisterInput:
    VALID = {"email": "new@x.co", "username": "al_ice", "password": "Sup3rsecret!", "first_name": "Al", "last_name": "Ice"}

    @pytest.mark.parametrize("override", [
        {"password": 123},
        {"password": None},
        {"password": ["a"]},
        {"password": {"a": 1}},
        {"password": True},
        {"password": f"Sup3r{NUL}secret!"},
        {"password": SURROGATE + "Sup3rsecret!"},
        {"password": "S1" + "a" * 127},              # 129 chars
        {"password": "12345678"},                    # weak (existing rule)
        {"email": f"a{NUL}@b.co"},
        {"email": "a" * 96 + "@b.co"},               # 101 chars
        {"email": "no-at-sign"},
        {"email": "a@b.co\n\n"},
        {"email": 5},
        {"username": f"al{NUL}ice"},
        {"username": SURROGATE + "alice"},
        {"username": "a" * 31},
        {"username": "al"},
        {"username": "al ice"},
        {"username": "al\nice"},
        {"username": "al@ice"},
        {"username": "<script>alert(1)</script>"},
        {"username": "' OR 1=1 --"},
        {"username": 5},
        {"username": None},
        {"username": ["alice"]},
        {"first_name": "a" * 51},
        {"first_name": f"Al{NUL}"},
        {"first_name": SURROGATE},
        {"first_name": 5},
        {"first_name": "   "},
        {"first_name": "Al\nice"},
        {"last_name": "a" * 51},
        {"last_name": f"Ice{NUL}"},
        {"last_name": ["x"]},
        {"last_name": None},
    ])
    async def test_bad_field_is_400_and_never_hits_db(self, client, mock_db, override):
        body = {**self.VALID, **override}
        res = await send(client, "POST", "/auth/register", body)
        assert res.status_code == 400
        mock_db.execute.assert_not_called()

    @pytest.mark.parametrize("missing", ["email", "username", "password", "first_name", "last_name"])
    async def test_missing_field_is_400(self, client, mock_db, missing):
        body = {k: v for k, v in self.VALID.items() if k != missing}
        res = await send(client, "POST", "/auth/register", body)
        assert res.status_code == 400
        mock_db.execute.assert_not_called()

    async def test_invalid_input_never_reaches_the_password_hash(self, client):
        """The Argon2 hash used to run *before* the type checks (a non-string password crashed it)."""
        with patch("app.routes.authentification.hash_password", new_callable=AsyncMock) as mock_hash:
            for password in (123, None, "p" * 5000, f"x{NUL}y1", "12345678"):
                res = await send(client, "POST", "/auth/register", {**self.VALID, "password": password})
                assert res.status_code == 400
            mock_hash.assert_not_called()

    async def test_values_at_the_limits_are_accepted(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone={"id": 7}))
        body = {
            "email": "a" * 95 + "@b.co",              # 100 chars
            "password": "S1" + "a" * 126,             # 128 chars
            "first_name": "f" * 50,
            "last_name": "l" * 50,
        }
        with patch("app.routes.authentification.send_verification_email"):
            res = await send(client, "POST", "/auth/register", body)
        assert res.status_code == 400

    async def test_names_are_stored_stripped(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchone={"id": 7}))
        with patch("app.routes.authentification.send_verification_email"):
            await send(client, "POST", "/auth/register", {**self.VALID, "first_name": "  Al  "})
        params = mock_db.execute.call_args.args[1]
        assert "Al" in params


class TestResetPasswordInput:
    @pytest.mark.parametrize("body", [
        {"token": SURROGATE, "new_password": "Sup3rsecret!"},
        {"token": f"a{NUL}b", "new_password": "Sup3rsecret!"},
        {"token": "t" * 513, "new_password": "Sup3rsecret!"},
        {"token": 5, "new_password": "Sup3rsecret!"},
        {"token": None, "new_password": "Sup3rsecret!"},
        {"token": "abc", "new_password": 5},
        {"token": "abc", "new_password": None},
        {"token": "abc", "new_password": "S1" + "a" * 127},
        {"token": "abc", "new_password": f"Sup3r{NUL}secret!"},
        {"token": "abc", "new_password": SURROGATE},
        {"token": "abc"},
        {"new_password": "Sup3rsecret!"},
    ])
    async def test_bad_input_is_400_and_never_hits_redis_or_db(self, client, mock_db, mock_redis, body):
        res = await send(client, "POST", "/auth/reset-password", body)
        assert res.status_code == 400
        mock_db.execute.assert_not_called()
        mock_redis.get.assert_not_called()
        mock_redis.set.assert_not_called()


class TestVerifyInput:
    async def test_oversized_token_is_400(self, client, mock_redis):
        res = await client.get("/auth/verify", params={"token": "t" * 513})
        assert res.status_code == 400
        mock_redis.get.assert_not_called()

    async def test_nul_in_token_is_400(self, client, mock_redis):
        res = await client.get("/auth/verify?token=a%00b")
        assert res.status_code == 400
        mock_redis.get.assert_not_called()


# ── profile ───────────────────────────────────────────────────────────────────

class TestPutProfileInput:
    @pytest.mark.parametrize("body", [
        {"bio": {"a": 1}}, {"bio": [1]}, {"bio": 5}, {"bio": True},
        {"bio": "x" * 501}, {"bio": f"a{NUL}b"}, {"bio": SURROGATE}, {"bio": "a\x01b"},
        {"city": 5}, {"city": ["Paris"]}, {"city": "c" * 101}, {"city": f"Pa{NUL}ris"},
        {"city": ""}, {"city": "Paris\nFrance"},
        {"first_name": 5}, {"first_name": ""}, {"first_name": "a" * 51}, {"first_name": f"a{NUL}"},
        {"first_name": SURROGATE}, {"first_name": None},
        {"last_name": 5}, {"last_name": "a" * 51}, {"last_name": f"a{NUL}"}, {"last_name": None},
        {"email": "nope"}, {"email": "a" * 96 + "@b.co"}, {"email": 5}, {"email": f"a{NUL}@b.co"},
        {"email": None}, {"email": "a@b.co\n\n"},
        {"username": 5}, {"username": None}, {"username": ""}, {"username": "ab"}, {"username": "a" * 31},
        {"username": f"al{NUL}ice"}, {"username": SURROGATE}, {"username": "al ice"}, {"username": "al@ice"},
        {"username": "<script>"}, {"username": ["alice"]}, {"username": "-alice"},
        {"gender": "robot"}, {"gender": 5}, {"gender": None}, {"gender": "Male"}, {"gender": f"male{NUL}"},
        {"gender": "x" * 21},
        {"orientation": "robot"}, {"orientation": 5}, {"orientation": None}, {"orientation": "gay"},
        {"orientation": "x" * 10_000},
        {"birth_date": 5}, {"birth_date": f"2000-01-0{NUL}"}, {"birth_date": "not-a-date"},
        {"birth_date": SURROGATE}, {"birth_date": "9" * 10_000}, {"birth_date": None},
        {"tags": "sport"}, {"tags": {"a": 1}}, {"tags": 5}, {"tags": ["sport"] * 6},
        {"tags": [NUL]}, {"tags": [f"sp{NUL}ort"]}, {"tags": ["t" * 51]}, {"tags": [SURROGATE]},
        {"tags": [5]}, {"tags": [""]}, {"tags": [None]}, {"tags": [["sport"]]},
    ])
    async def test_bad_field_is_400_and_never_hits_db(self, authed, mock_db, body):
        res = await send(authed, "PUT", "/profile/me", body)
        assert res.status_code == 400
        mock_db.execute.assert_not_called()

    async def test_one_bad_field_rejects_the_whole_update(self, authed, mock_db):
        res = await send(authed, "PUT", "/profile/me", {"first_name": "Alice", "bio": "x" * 501})
        assert res.status_code == 400
        mock_db.execute.assert_not_called()
        mock_db.commit.assert_not_called()

    async def test_values_at_the_limits_are_accepted_and_stored_stripped(self, authed, mock_db):
        mock_db.execute = AsyncMock(return_value=make_cursor(
            fetchone={"gender": None, "birth_date": None, "city": None, "latitude": None, "longitude": None}
        ))
        body = {
            "first_name": "  " + "f" * 50 + "  ",
            "last_name": "l" * 50,
            "bio": "line one\nline two\n" + "b" * 482,          # 500 chars, newlines allowed
            "city": "c" * 100,
            "gender": "other",
            "orientation": "hetero",
        }
        with patch("app.routes.profile.send_verification_email"):
            res = await send(authed, "PUT", "/profile/me", body)
        assert res.status_code == 200
        update_sql, params = mock_db.execute.call_args_list[-1].args
        assert update_sql.startswith("UPDATE users SET")
        assert "f" * 50 in params and "  " + "f" * 50 + "  " not in params
        assert "other" in params and "hetero" in params

    async def test_bio_and_city_can_be_cleared_with_null(self, authed, mock_db):
        mock_db.execute = AsyncMock(return_value=make_cursor(
            fetchone={"gender": None, "birth_date": None, "city": "Paris", "latitude": None, "longitude": None}
        ))
        res = await send(authed, "PUT", "/profile/me", {"bio": None, "city": None})
        assert res.status_code == 200

    async def test_empty_bio_is_allowed(self, authed, mock_db):
        mock_db.execute = AsyncMock(return_value=make_cursor(
            fetchone={"gender": None, "birth_date": None, "city": None, "latitude": None, "longitude": None}
        ))
        res = await send(authed, "PUT", "/profile/me", {"bio": ""})
        assert res.status_code == 200


class TestLocationInput:
    @pytest.mark.parametrize("body", [
        {"latitude": True, "longitude": 2.3},
        {"latitude": 48.8, "longitude": False},
        {"latitude": float("nan"), "longitude": 2.3},
        {"latitude": 48.8, "longitude": float("inf")},
        {"latitude": None, "longitude": 2.3},
        {"latitude": "48.8", "longitude": "2.3"},
        {"latitude": [48.8], "longitude": 2.3},
        {"latitude": 90.5, "longitude": 2.3},
        {"latitude": 48.8, "longitude": -180.5},
        {"latitude": 48.8},
        {"longitude": 2.3},
        {},
    ])
    async def test_bad_coordinates_are_400_and_never_hit_db(self, authed, mock_db, body):
        res = await send(authed, "PUT", "/profile/location", body)
        assert res.status_code == 400
        mock_db.execute.assert_not_called()

    async def test_exponent_overflow_literal_is_400(self, authed, mock_db):
        """``1e999`` is a valid JSON number that Python parses to infinity."""
        res = await authed.put("/profile/location", content=b'{"latitude": 1e999, "longitude": 2}',
                               headers={"content-type": "application/json"})
        assert res.status_code == 400
        mock_db.execute.assert_not_called()


class TestMovePhotoInput:
    @pytest.mark.parametrize("to", [True, False, "2", 2.5, 2.0, None, [2], {"a": 1}, 0, 6, -1, 10**30])
    async def test_bad_target_is_400_and_never_hits_db(self, authed, mock_db, to):
        res = await send(authed, "PUT", "/profile/photos/1/move", {"to": to})
        assert res.status_code == 400
        mock_db.execute.assert_not_called()

    async def test_exponent_overflow_literal_is_400(self, authed, mock_db):
        """``int(inf)`` raises OverflowError, which the old except-tuple did not cover."""
        res = await authed.put("/profile/photos/1/move", content=b'{"to": 1e999}',
                               headers={"content-type": "application/json"})
        assert res.status_code == 400
        mock_db.execute.assert_not_called()


class TestTagsInput:
    @pytest.mark.parametrize("tag", [NUL, f"a{NUL}", "t" * 51, SURROGATE, 5, None, ""])
    async def test_put_tags_bad_tag_is_400(self, authed, mock_db, tag):
        res = await send(authed, "PUT", "/profile/tags", {"tags": [tag]})
        assert res.status_code == 400
        mock_db.execute.assert_not_called()

    async def test_duplicate_tags_are_merged_so_the_primary_key_is_not_violated(self, authed, mock_db):
        async def execute(sql, params=None):
            if "name = ANY" in sql:
                return make_cursor(fetchall=[{"name": "hiking"}])
            if "SELECT id FROM tags" in sql:
                return make_cursor(fetchone={"id": 3})
            return make_cursor()
        mock_db.execute = AsyncMock(side_effect=execute)

        res = await send(authed, "PUT", "/profile/tags", {"tags": ["Hiking", "hiking", " HIKING "]})

        assert res.status_code == 200
        any_call = next(c for c in mock_db.execute.call_args_list if "name = ANY" in c.args[0])
        assert any_call.args[1] == (["hiking"],)
        inserts = [c for c in mock_db.execute.call_args_list if "INSERT INTO user_tags" in c.args[0]]
        assert len(inserts) == 1

    @pytest.mark.parametrize("search", [NUL, f"a{NUL}b", "s" * 51])
    async def test_search_bad_value_is_400(self, authed, mock_db, search):
        res = await authed.get("/tags", params={"search": search})
        assert res.status_code == 400
        mock_db.execute.assert_not_called()

    async def test_blank_search_falls_back_to_the_full_list(self, authed, mock_db):
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[{"name": "hiking"}]))
        res = await authed.get("/tags", params={"search": "   "})
        assert res.status_code == 200
        assert "ILIKE" not in mock_db.execute.call_args.args[0]

    async def test_search_at_the_limit_is_accepted(self, authed, mock_db):
        mock_db.execute = AsyncMock(return_value=make_cursor(fetchall=[]))
        res = await authed.get("/tags", params={"search": "s" * 50})
        assert res.status_code == 200

    @pytest.mark.parametrize("name", ["%00", "a%00b", "t" * 51])
    async def test_delete_tag_bad_name_is_400(self, authed, mock_db, name):
        res = await authed.delete(f"/profile/tags/{name}")
        assert res.status_code == 400
        mock_db.execute.assert_not_called()


# ── users ─────────────────────────────────────────────────────────────────────

class TestBrowseInput:
    @pytest.mark.parametrize("query", [
        "page=99999999999999999999", "page=-1", "page=10001", "page=1e3", "page=" + "9" * 5000,
        "min_age=15", "min_age=0", "min_age=121", "max_age=15", "max_age=99999999999",
        "max_distance=-1", "max_distance=40001", "max_distance=99999999999999999999",
        "min_fame=-1", "min_fame=1000001", "min_fame=99999999999999999999",
        "min_tags=-1", "min_tags=6",
        "min_age=%00", "min_age=1_8", "min_age=%20", "min_age=%D9%A3", "page=%2B1",
    ])
    async def test_bad_query_param_is_400_and_never_hits_db(self, authed, mock_db, query):
        res = await authed.get(f"/users?{query}")
        assert res.status_code == 400
        mock_db.execute.assert_not_called()


class TestChatHistoryInput:
    @pytest.mark.parametrize("query", [
        "before=0", "before=-1", "before=2147483648", "before=99999999999999999999",
        "before=1e3", "before=%00", "before=%20", "before=%D9%A3", "before=" + "9" * 5000,
        "limit=0", "limit=-1", "limit=51", "limit=99999999999999999999", "limit=abc", "limit=%2B1",
    ])
    async def test_bad_query_param_is_400_and_never_hits_db(self, authed, mock_db, query):
        res = await authed.get(f"/chat/2/messages?{query}")
        assert res.status_code == 400
        mock_db.execute.assert_not_called()


TARGET_ROUTES = [
    ("GET", "/chat/{id}/messages"),
    ("POST", "/chat/{id}/seen"),
    ("GET", "/users/{id}"),
    ("GET", "/users/{id}/photos/1"),
    ("POST", "/users/{id}/like"),
    ("DELETE", "/users/{id}/like"),
    ("POST", "/users/{id}/block"),
    ("DELETE", "/users/{id}/block"),
    ("POST", "/users/{id}/report"),
]


class TestTargetIdInput:
    @pytest.mark.parametrize("method,template", TARGET_ROUTES)
    @pytest.mark.parametrize("target_id", [HUGE_ID, 2**31, 0, -5, 10**400])
    async def test_impossible_id_is_404_and_never_hits_db(self, authed, mock_db, method, template, target_id):
        """An id above int4 used to reach PostgreSQL and fail with 'out of range' (500)."""
        res = await authed.request(method, template.format(id=target_id),
                                   content=b"{}", headers={"content-type": "application/json"})
        assert res.status_code == 404
        mock_db.execute.assert_not_called()

    @pytest.mark.parametrize("method,template", TARGET_ROUTES)
    async def test_non_integer_id_is_422_not_500(self, authed, mock_db, method, template):
        res = await authed.request(method, template.format(id="abc"),
                                   content=b"{}", headers={"content-type": "application/json"})
        assert res.status_code == 422
        mock_db.execute.assert_not_called()

    async def test_largest_valid_id_gets_past_the_check(self, authed, mock_db):
        res = await authed.get(f"/users/{2**31 - 1}")
        assert res.status_code == 404          # no such user, decided by the DB lookup
        mock_db.execute.assert_called()


class TestReportInput:
    @pytest.mark.parametrize("reason", [NUL, f"spam{NUL}", "r" * 501, SURROGATE, 5, ["spam"], {"a": 1}, True, "a\x01b"])
    async def test_bad_reason_is_400_and_never_hits_db(self, authed, mock_db, reason):
        res = await send(authed, "POST", "/users/2/report", {"reason": reason})
        assert res.status_code == 400
        mock_db.execute.assert_not_called()

    async def test_reason_at_the_limit_with_newlines_is_accepted(self, authed, mock_db):
        mock_db.execute = AsyncMock(side_effect=[make_cursor(fetchone={"?column?": 1}), make_cursor(fetchone={"id": 1})])
        res = await send(authed, "POST", "/users/2/report", {"reason": "line1\nline2\n" + "r" * 488})
        assert res.status_code == 200

    async def test_reason_is_optional(self, authed, mock_db):
        mock_db.execute = AsyncMock(side_effect=[make_cursor(fetchone={"?column?": 1}), make_cursor(fetchone={"id": 1})])
        res = await send(authed, "POST", "/users/2/report", {})
        assert res.status_code == 200
