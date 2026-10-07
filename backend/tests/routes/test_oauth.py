import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from psycopg.errors import UniqueViolation


GOOGLE_CLAIMS = {
    "email": "alice@gmail.com",
    "given_name": "Alice",
    "family_name": "Martin",
    "email_verified": True,
}


def make_cursor(fetchone=None):
    c = AsyncMock()
    c.fetchone = AsyncMock(return_value=fetchone)
    return c


def mock_httpx_token_exchange(status_code=200, id_token="fake-id-token"):
    """Patch httpx.AsyncClient so POSTing to Google's token endpoint
    returns a canned response, without any real network call."""
    response = MagicMock()
    response.status_code = status_code
    response.json = MagicMock(return_value={"id_token": id_token} if id_token else {})

    client_instance = AsyncMock()
    client_instance.post = AsyncMock(return_value=response)

    client_cm = AsyncMock()
    client_cm.__aenter__ = AsyncMock(return_value=client_instance)
    client_cm.__aexit__ = AsyncMock(return_value=False)

    return patch("httpx.AsyncClient", return_value=client_cm)


async def do_callback(client, mock_redis, state="validstate", code="validcode",
                       claims=None, id_token="fake-id-token", token_status=200):
    """Drive /oauth/google/callback through the state check, token exchange
    and id_token verification steps with working defaults, so each test only
    overrides the one thing it's exercising."""
    mock_redis.get = AsyncMock(return_value=1)   # state exists in Redis
    mock_redis.delete = AsyncMock(return_value=1)

    claims = GOOGLE_CLAIMS if claims is None else claims

    with mock_httpx_token_exchange(status_code=token_status, id_token=id_token), \
         patch("app.routes.oauth.id_token_check.verify_oauth2_token", return_value=claims):
        return await client.get(
            f"/oauth/google/callback?state={state}&code={code}",
            follow_redirects=False,
        )


# ── GET /oauth/google/login ─────────────────────────────────────────────────

class TestOauthLogin:
    async def test_redirects_to_google(self, client, mock_redis):
        resp = await client.get("/oauth/google/login", follow_redirects=False)

        assert resp.status_code == 307
        assert resp.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth")

    async def test_stores_state_in_redis(self, client, mock_redis):
        await client.get("/oauth/google/login", follow_redirects=False)

        mock_redis.set.assert_called_once()
        key = mock_redis.set.call_args.args[0]
        assert key.startswith("oauth_state:")
        assert mock_redis.set.call_args.kwargs.get("ex") == 300

    async def test_state_is_included_in_redirect_url(self, client, mock_redis):
        resp = await client.get("/oauth/google/login", follow_redirects=False)

        state_in_redis = mock_redis.set.call_args.args[0].removeprefix("oauth_state:")
        assert f"state={state_in_redis}" in resp.headers["location"]

    async def test_redis_error_returns_503(self, client, mock_redis):
        from redis import RedisError
        mock_redis.set = AsyncMock(side_effect=RedisError("down"))

        resp = await client.get("/oauth/google/login")

        assert resp.status_code == 503


# ── GET /oauth/google/callback ──────────────────────────────────────────────

class TestOauthCallbackEarlyFailures:
    async def test_google_error_param_redirects_to_login(self, client, mock_redis):
        resp = await client.get("/oauth/google/callback?error=access_denied", follow_redirects=False)

        assert resp.status_code == 307
        assert "error=user_denied" in resp.headers["location"]

    async def test_missing_code_redirects_to_login(self, client, mock_redis):
        resp = await client.get("/oauth/google/callback?state=x", follow_redirects=False)

        assert "error=google_denied" in resp.headers["location"]

    async def test_missing_state_redirects_to_login(self, client, mock_redis):
        resp = await client.get("/oauth/google/callback?code=x", follow_redirects=False)

        assert "error=google_denied" in resp.headers["location"]

    async def test_unknown_state_redirects_with_state_error(self, client, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)

        resp = await client.get("/oauth/google/callback?state=bad&code=x", follow_redirects=False)

        assert "error=state_error" in resp.headers["location"]

    async def test_redis_error_checking_state_redirects(self, client, mock_redis):
        from redis import RedisError
        mock_redis.get = AsyncMock(side_effect=RedisError("down"))

        resp = await client.get("/oauth/google/callback?state=x&code=y", follow_redirects=False)

        assert "error=redis_error" in resp.headers["location"]

    async def test_token_exchange_http_failure_redirects(self, client, mock_redis):
        """A real network failure raises httpx.RequestError (or a subclass) —
        that's the type the handler's except clause actually catches."""
        import httpx
        mock_redis.get = AsyncMock(return_value=1)
        with patch("httpx.AsyncClient", side_effect=httpx.ConnectError("network down")):
            resp = await client.get("/oauth/google/callback?state=x&code=y", follow_redirects=False)

        assert "error=httpx_error" in resp.headers["location"]

    async def test_token_exchange_non_200_redirects(self, client, mock_redis):
        resp = await do_callback(client, mock_redis, token_status=400)

        assert "error=google_error" in resp.headers["location"]

    async def test_missing_id_token_redirects(self, client, mock_redis):
        resp = await do_callback(client, mock_redis, id_token=None)

        assert "error=google_error" in resp.headers["location"]

    async def test_invalid_id_token_redirects(self, client, mock_redis):
        mock_redis.get = AsyncMock(return_value=1)
        mock_redis.delete = AsyncMock(return_value=1)
        with mock_httpx_token_exchange(), \
             patch("app.routes.oauth.id_token_check.verify_oauth2_token", side_effect=ValueError("bad token")):
            resp = await client.get("/oauth/google/callback?state=x&code=y", follow_redirects=False)

        assert "error=google_error" in resp.headers["location"]

    async def test_email_not_verified_by_google_redirects(self, client, mock_redis):
        claims = {**GOOGLE_CLAIMS, "email_verified": False}
        resp = await do_callback(client, mock_redis, claims=claims)

        assert "error=email_error" in resp.headers["location"]

    async def test_missing_name_from_google_redirects(self, client, mock_redis):
        claims = {**GOOGLE_CLAIMS, "given_name": None}
        resp = await do_callback(client, mock_redis, claims=claims)

        assert "error=google_error" in resp.headers["location"]


class TestOauthCallbackNewUser:
    @staticmethod
    def new_user_queries(*, insert=None):
        """The DB calls for a first Google sign-in, in order."""
        return [
            make_cursor(fetchone=None),  # SELECT: no existing user
            make_cursor(fetchone=None),  # SELECT: the generated username is free
            insert if insert is not None else make_cursor(fetchone={"id": 7, "profile_complete": False}),  # INSERT ... RETURNING
        ]

    async def test_creates_account_and_redirects_to_complete_profile(self, client, mock_db, mock_redis):
        mock_db.execute = AsyncMock(side_effect=self.new_user_queries())

        resp = await do_callback(client, mock_redis)

        assert resp.status_code == 307
        assert "/complete-profile" in resp.headers["location"]

    async def test_insert_marks_account_verified(self, client, mock_db, mock_redis):
        mock_db.execute = AsyncMock(side_effect=self.new_user_queries())

        await do_callback(client, mock_redis)

        insert_call = mock_db.execute.call_args_list[2]
        query, params = insert_call.args
        assert "INSERT INTO users" in query
        assert params[-1] is True  # verified

    async def test_new_account_gets_a_username_derived_from_the_first_name(self, client, mock_db, mock_redis):
        mock_db.execute = AsyncMock(side_effect=self.new_user_queries())

        await do_callback(client, mock_redis)

        query, params = mock_db.execute.call_args_list[2].args
        assert "username" in query
        assert params[1].startswith("alice") and params[1][len("alice"):].isdigit()

    async def test_taken_username_is_not_reused(self, client, mock_db, mock_redis):
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),            # no existing user
            make_cursor(fetchone={"?column?": 1}), # first candidate is taken
            make_cursor(fetchone=None),            # second one is free
            make_cursor(fetchone={"id": 7, "profile_complete": False}),
        ])

        resp = await do_callback(client, mock_redis)

        assert "/complete-profile" in resp.headers["location"]
        taken = mock_db.execute.call_args_list[1].args[1][0]
        chosen = mock_db.execute.call_args_list[3].args[1][1]
        assert chosen != taken

    async def test_commits_after_insert(self, client, mock_db, mock_redis):
        mock_db.execute = AsyncMock(side_effect=self.new_user_queries())

        await do_callback(client, mock_redis)

        mock_db.commit.assert_called_once()

    async def test_race_condition_on_insert_redirects_email_taken(self, client, mock_db, mock_redis):
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),
            make_cursor(fetchone=None),
            UniqueViolation("duplicate key"),
        ])

        resp = await do_callback(client, mock_redis)

        assert "error=email_already_taken" in resp.headers["location"]
        mock_db.rollback.assert_called_once()

    async def test_race_on_the_username_is_not_reported_as_a_taken_email(self, client, mock_db, mock_redis):
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone=None),
            make_cursor(fetchone=None),
            UniqueViolation("duplicate key"),
        ])

        with patch("app.routes.oauth.is_username_conflict", return_value=True):
            resp = await do_callback(client, mock_redis)

        assert "error=db_error" in resp.headers["location"]
        mock_db.rollback.assert_called_once()

    async def test_sets_session_cookie(self, client, mock_db, mock_redis):
        mock_db.execute = AsyncMock(side_effect=self.new_user_queries())

        resp = await do_callback(client, mock_redis)

        assert "session=" in resp.headers.get("set-cookie", "")


class TestOauthCallbackExistingVerifiedUser:
    async def test_complete_profile_redirects_to_browse(self, client, mock_db, mock_redis):
        mock_db.execute = AsyncMock(return_value=make_cursor(
            fetchone={"id": 3, "profile_complete": True, "verified": True}
        ))

        resp = await do_callback(client, mock_redis)

        assert "/browse" in resp.headers["location"]

    async def test_incomplete_profile_redirects_to_complete_profile(self, client, mock_db, mock_redis):
        mock_db.execute = AsyncMock(return_value=make_cursor(
            fetchone={"id": 3, "profile_complete": False, "verified": True}
        ))

        resp = await do_callback(client, mock_redis)

        assert "/complete-profile" in resp.headers["location"]

    async def test_does_not_touch_password_or_verified(self, client, mock_db, mock_redis):
        """A verified account is logged into as-is — no UPDATE at all."""
        mock_db.execute = AsyncMock(return_value=make_cursor(
            fetchone={"id": 3, "profile_complete": True, "verified": True}
        ))

        await do_callback(client, mock_redis)

        assert mock_db.execute.call_count == 1  # only the SELECT


class TestOauthCallbackReclaimsUnverifiedAccount:
    """Regression coverage for the pre-registration hijack: an existing but
    unverified row for this email must be reclaimed for the Google identity,
    not silently logged into as-is."""

    async def test_overwrites_password_and_marks_verified(self, client, mock_db, mock_redis):
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"id": 5, "profile_complete": False, "verified": False}),
            make_cursor(),  # UPDATE
        ])

        await do_callback(client, mock_redis)

        update_call = mock_db.execute.call_args_list[1]
        query, params = update_call.args
        assert "UPDATE users SET" in query
        assert "verified" in query
        assert params[-1] == 5  # WHERE id = user_id
        assert True in params  # verified set to True

    async def test_overwrites_name_with_googles_claims(self, client, mock_db, mock_redis):
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"id": 5, "profile_complete": False, "verified": False}),
            make_cursor(),
        ])

        await do_callback(client, mock_redis)

        _, params = mock_db.execute.call_args_list[1].args
        assert GOOGLE_CLAIMS["given_name"] in params
        assert GOOGLE_CLAIMS["family_name"] in params

    async def test_commits_the_reclaim(self, client, mock_db, mock_redis):
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"id": 5, "profile_complete": False, "verified": False}),
            make_cursor(),
        ])

        await do_callback(client, mock_redis)

        mock_db.commit.assert_called_once()

    async def test_incomplete_profile_redirects_to_complete_profile(self, client, mock_db, mock_redis):
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"id": 5, "profile_complete": False, "verified": False}),
            make_cursor(),
        ])

        resp = await do_callback(client, mock_redis)

        assert "/complete-profile" in resp.headers["location"]

    async def test_complete_profile_redirects_to_browse(self, client, mock_db, mock_redis):
        """Defensive case: profile_complete somehow true on an unverified
        row — still reclaimed, but sent straight to browse."""
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"id": 5, "profile_complete": True, "verified": False}),
            make_cursor(),
        ])

        resp = await do_callback(client, mock_redis)

        assert "/browse" in resp.headers["location"]

    async def test_reclaimed_account_gets_a_session(self, client, mock_db, mock_redis):
        mock_db.execute = AsyncMock(side_effect=[
            make_cursor(fetchone={"id": 5, "profile_complete": False, "verified": False}),
            make_cursor(),
        ])

        resp = await do_callback(client, mock_redis)

        assert "session=" in resp.headers.get("set-cookie", "")


class TestOauthCallbackDbFailure:
    async def test_db_error_rolls_back_and_redirects(self, client, mock_db, mock_redis):
        mock_db.execute = AsyncMock(side_effect=Exception("db down"))

        resp = await do_callback(client, mock_redis)

        assert "error=db_error" in resp.headers["location"]
        mock_db.rollback.assert_called_once()
