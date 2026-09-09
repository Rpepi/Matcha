import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_db_row(user_id=1, password="correct_password", verified=True, profile_complete=False):
    from app.security.passwords import ph
    return {
        "id": user_id,
        "password_hash": ph.hash(password),
        "verified": verified,
        "profile_complete": profile_complete,
    }


def make_mock_conn(row=None):
    cursor = AsyncMock()
    cursor.fetchone = AsyncMock(return_value=row)
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=cursor)
    conn.commit = AsyncMock()
    return conn


VALID_REGISTER_BODY = {
    "password": "Val1dP@ss!",
    "email": "alice@test.com",
    "first_name": "Alice",
    "last_name": "Smith",
}


# ── authenticate_user ─────────────────────────────────────────────────────────

class TestAuthenticateUser:
    async def test_valid_credentials_returns_id_and_profile_complete(self):
        from app.routes.authentification import authenticate_user
        row = make_db_row(user_id=7, password="Val1dP@ss!", verified=True, profile_complete=True)
        conn = make_mock_conn(row)

        user_id, profile_complete = await authenticate_user("alice@test.com", "Val1dP@ss!", conn)

        assert user_id == "7"
        assert profile_complete is True

    async def test_unknown_email_raises_401(self):
        from app.routes.authentification import authenticate_user
        conn = make_mock_conn(row=None)

        with pytest.raises(HTTPException) as exc_info:
            await authenticate_user("ghost@test.com", "anything", conn)

        assert exc_info.value.status_code == 401

    async def test_wrong_password_raises_401(self):
        from app.routes.authentification import authenticate_user
        conn = make_mock_conn(make_db_row(password="correct_password"))

        with pytest.raises(HTTPException) as exc_info:
            await authenticate_user("alice@test.com", "wrong_password", conn)

        assert exc_info.value.status_code == 401

    async def test_unverified_user_raises_403(self):
        from app.routes.authentification import authenticate_user
        conn = make_mock_conn(make_db_row(password="Val1dP@ss!", verified=False))

        with pytest.raises(HTTPException) as exc_info:
            await authenticate_user("alice@test.com", "Val1dP@ss!", conn)

        assert exc_info.value.status_code == 403

    async def test_unknown_user_never_crashes(self):
        """row=None must always return 401, never 500."""
        from app.routes.authentification import authenticate_user
        conn = make_mock_conn(row=None)

        with pytest.raises(HTTPException) as exc_info:
            await authenticate_user("ghost@test.com", "dummy", conn)

        assert exc_info.value.status_code == 401

    async def test_same_error_for_unknown_user_and_wrong_password(self):
        from app.routes.authentification import authenticate_user

        with pytest.raises(HTTPException) as e1:
            await authenticate_user("ghost@test.com", "anything", make_mock_conn(row=None))

        with pytest.raises(HTTPException) as e2:
            await authenticate_user("alice@test.com", "wrong", make_mock_conn(make_db_row(password="correct")))

        assert e1.value.detail == e2.value.detail


# ── /auth/login ───────────────────────────────────────────────────────────────

class TestLoginRoute:
    async def test_successful_login_returns_user_data(self, client, mock_cursor):
        from app.security.passwords import ph
        mock_cursor.fetchone = AsyncMock(return_value={
            "id": 1, "password_hash": ph.hash("Val1dP@ss!"),
            "verified": True, "profile_complete": False,
        })

        resp = await client.post("/auth/login", json={"email": "alice@test.com", "password": "Val1dP@ss!"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "alice@test.com"
        assert "id" in data
        assert "profile_complete" in data

    async def test_successful_login_sets_session_cookie(self, client, mock_cursor):
        from app.security.passwords import ph
        mock_cursor.fetchone = AsyncMock(return_value={
            "id": 1, "password_hash": ph.hash("Val1dP@ss!"),
            "verified": True, "profile_complete": False,
        })

        resp = await client.post("/auth/login", json={"email": "alice@test.com", "password": "Val1dP@ss!"})

        assert "session" in resp.cookies

    async def test_wrong_content_type_returns_415(self, client):
        resp = await client.post(
            "/auth/login",
            content="email=alice@test.com&password=Val1dP@ss!",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 415

    async def test_invalid_json_returns_400(self, client):
        resp = await client.post(
            "/auth/login",
            content="not json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400

    async def test_missing_email_returns_400(self, client):
        resp = await client.post("/auth/login", json={"password": "Val1dP@ss!"})
        assert resp.status_code == 400

    async def test_missing_password_returns_400(self, client):
        resp = await client.post("/auth/login", json={"email": "alice@test.com"})
        assert resp.status_code == 400

    async def test_null_email_returns_400(self, client):
        resp = await client.post("/auth/login", json={"email": None, "password": "Val1dP@ss!"})
        assert resp.status_code == 400

    async def test_integer_password_returns_400(self, client):
        resp = await client.post("/auth/login", json={"email": "alice@test.com", "password": 12345})
        assert resp.status_code == 400

    async def test_unknown_user_returns_401(self, client, mock_cursor):
        mock_cursor.fetchone = AsyncMock(return_value=None)
        resp = await client.post("/auth/login", json={"email": "ghost@test.com", "password": "anything"})
        assert resp.status_code == 401

    async def test_wrong_password_returns_401(self, client, mock_cursor):
        from app.security.passwords import ph
        mock_cursor.fetchone = AsyncMock(return_value={
            "id": 1, "password_hash": ph.hash("correct_password"),
            "verified": True, "profile_complete": False,
        })
        resp = await client.post("/auth/login", json={"email": "alice@test.com", "password": "wrong_password"})
        assert resp.status_code == 401

    async def test_unverified_user_returns_403(self, client, mock_cursor):
        from app.security.passwords import ph
        mock_cursor.fetchone = AsyncMock(return_value={
            "id": 1, "password_hash": ph.hash("Val1dP@ss!"),
            "verified": False, "profile_complete": False,
        })
        resp = await client.post("/auth/login", json={"email": "alice@test.com", "password": "Val1dP@ss!"})
        assert resp.status_code == 403


# ── /auth/register ────────────────────────────────────────────────────────────

class TestRegisterRoute:
    async def test_successful_register_returns_message(self, client, mock_cursor):
        mock_cursor.fetchone = AsyncMock(return_value={"id": 42})

        with patch("app.routes.authentification.send_verification_email"):
            resp = await client.post("/auth/register", json=VALID_REGISTER_BODY)

        assert resp.status_code == 200
        assert "message" in resp.json()

    async def test_register_sends_verification_email(self, client, mock_cursor):
        mock_cursor.fetchone = AsyncMock(return_value={"id": 42})

        with patch("app.routes.authentification.send_verification_email") as mock_send:
            await client.post("/auth/register", json=VALID_REGISTER_BODY)

        mock_send.assert_called_once()
        assert mock_send.call_args.args[0] == VALID_REGISTER_BODY["email"]

    async def test_wrong_content_type_returns_415(self, client):
        resp = await client.post(
            "/auth/register",
            content="email=alice@test.com",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 415

    async def test_invalid_json_returns_400(self, client):
        resp = await client.post(
            "/auth/register",
            content="not json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400

    @pytest.mark.parametrize("missing_field", [
        "password", "email", "first_name", "last_name"
    ])
    async def test_missing_required_field_returns_400(self, client, missing_field):
        body = {k: v for k, v in VALID_REGISTER_BODY.items() if k != missing_field}
        resp = await client.post("/auth/register", json=body)
        assert resp.status_code == 400

    async def test_non_string_required_field_returns_400(self, client):
        body = {**VALID_REGISTER_BODY, "first_name": 123}
        resp = await client.post("/auth/register", json=body)
        assert resp.status_code == 400


# ── /auth/verify ──────────────────────────────────────────────────────────────

class TestVerifyEmailRoute:
    async def test_valid_token_verifies_user(self, client, mock_db):
        from app.security.token import generate_verification_token
        token = generate_verification_token("42")

        resp = await client.get(f"/auth/verify?token={token}")

        assert resp.status_code == 200
        mock_db.execute.assert_called_once()
        assert "UPDATE users SET verified" in str(mock_db.execute.call_args)

    async def test_missing_token_returns_400(self, client):
        resp = await client.get("/auth/verify")
        assert resp.status_code == 400

    async def test_invalid_token_returns_400(self, client):
        resp = await client.get("/auth/verify?token=tampered.invalid.token")
        assert resp.status_code == 400

    async def test_expired_token_returns_400(self, client):
        from app.security.token import serializer
        from itsdangerous import SignatureExpired

        with patch.object(serializer, "loads", side_effect=SignatureExpired("expired")):
            resp = await client.get("/auth/verify?token=sometoken")

        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower()


# ── /auth/forgot-password ─────────────────────────────────────────────────────

class TestForgotPasswordRoute:
    async def test_existing_email_sends_reset_email(self, client, mock_cursor):
        mock_cursor.fetchone = AsyncMock(return_value={"id": 1})

        with patch("app.routes.authentification.send_reset_email") as mock_send:
            resp = await client.post("/auth/forgot-password", json={"email": "alice@test.com"})

        assert resp.status_code == 200
        mock_send.assert_called_once()
        assert mock_send.call_args.args[0] == "alice@test.com"

    async def test_unknown_email_returns_200_without_sending(self, client, mock_cursor):
        mock_cursor.fetchone = AsyncMock(return_value=None)

        with patch("app.routes.authentification.send_reset_email") as mock_send:
            resp = await client.post("/auth/forgot-password", json={"email": "ghost@test.com"})

        assert resp.status_code == 200
        mock_send.assert_not_called()

    async def test_same_response_for_existing_and_unknown_email(self, client, mock_cursor):
        """Anti-enumeration: same message regardless of whether email exists."""
        mock_cursor.fetchone = AsyncMock(return_value={"id": 1})
        with patch("app.routes.authentification.send_reset_email"):
            r1 = await client.post("/auth/forgot-password", json={"email": "alice@test.com"})

        mock_cursor.fetchone = AsyncMock(return_value=None)
        with patch("app.routes.authentification.send_reset_email"):
            r2 = await client.post("/auth/forgot-password", json={"email": "ghost@test.com"})

        assert r1.json()["message"] == r2.json()["message"]

    async def test_missing_email_returns_400(self, client):
        resp = await client.post("/auth/forgot-password", json={})
        assert resp.status_code == 400

    async def test_non_string_email_returns_400(self, client):
        resp = await client.post("/auth/forgot-password", json={"email": 123})
        assert resp.status_code == 400

    async def test_wrong_content_type_returns_415(self, client):
        resp = await client.post(
            "/auth/forgot-password",
            content="email=alice@test.com",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 415

    async def test_reset_token_uses_different_salt_than_verify(self, client, mock_cursor):
        """A verify token must not work as a reset token."""
        from app.security.token import generate_verification_token, serializer
        from itsdangerous import BadSignature
        verify_token = generate_verification_token("1")
        with pytest.raises(BadSignature):
            serializer.loads(verify_token, salt="password-reset", max_age=1800)


# ── /auth/reset-password ──────────────────────────────────────────────────────

class TestResetPasswordRoute:
    def _make_reset_token(self, user_id="1"):
        from app.security.token import serializer
        return serializer.dumps(user_id, salt="password-reset")

    async def test_valid_token_updates_password(self, client, mock_db):
        token = self._make_reset_token("1")

        resp = await client.post("/auth/reset-password", json={
            "token": token,
            "new_password": "NewP@ss123!",
        })

        assert resp.status_code == 200
        update_calls = [c for c in mock_db.execute.call_args_list if "UPDATE users SET password_hash" in str(c)]
        assert len(update_calls) == 1

    async def test_commits_after_update(self, client, mock_db):
        token = self._make_reset_token("1")

        await client.post("/auth/reset-password", json={
            "token": token,
            "new_password": "NewP@ss123!",
        })

        mock_db.commit.assert_called_once()

    async def test_expired_token_returns_400(self, client):
        from app.security.token import serializer
        from itsdangerous import SignatureExpired
        with patch.object(serializer, "loads", side_effect=SignatureExpired("expired")):
            resp = await client.post("/auth/reset-password", json={
                "token": "sometoken",
                "new_password": "NewP@ss123!",
            })
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower()

    async def test_invalid_token_returns_400(self, client):
        resp = await client.post("/auth/reset-password", json={
            "token": "tampered.invalid.token",
            "new_password": "NewP@ss123!",
        })
        assert resp.status_code == 400

    async def test_weak_password_returns_400(self, client):
        token = self._make_reset_token("1")
        resp = await client.post("/auth/reset-password", json={
            "token": token,
            "new_password": "password",
        })
        assert resp.status_code == 400

    async def test_all_digits_password_returns_400(self, client):
        token = self._make_reset_token("1")
        resp = await client.post("/auth/reset-password", json={
            "token": token,
            "new_password": "123456789",
        })
        assert resp.status_code == 400

    async def test_missing_token_returns_400(self, client):
        resp = await client.post("/auth/reset-password", json={"new_password": "NewP@ss123!"})
        assert resp.status_code == 400

    async def test_missing_new_password_returns_400(self, client):
        resp = await client.post("/auth/reset-password", json={"token": "sometoken"})
        assert resp.status_code == 400

    async def test_wrong_content_type_returns_415(self, client):
        resp = await client.post(
            "/auth/reset-password",
            content="token=x&new_password=y",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 415

    async def test_verify_token_cannot_be_used_for_reset(self, client):
        """Salt isolation: a verify token must be rejected by reset endpoint."""
        from app.security.token import generate_verification_token
        verify_token = generate_verification_token("1")
        resp = await client.post("/auth/reset-password", json={
            "token": verify_token,
            "new_password": "NewP@ss123!",
        })
        assert resp.status_code == 400

    async def test_token_cannot_be_reused(self, client, mock_db, mock_redis):
        """Token is single-use: second call must be rejected."""
        token = self._make_reset_token("1")

        mock_redis.get = AsyncMock(return_value=None)
        resp1 = await client.post("/auth/reset-password", json={
            "token": token, "new_password": "NewP@ss123!",
        })
        assert resp1.status_code == 200

        mock_redis.get = AsyncMock(return_value=1)
        resp2 = await client.post("/auth/reset-password", json={
            "token": token, "new_password": "AnotherP@ss1!",
        })
        assert resp2.status_code == 400
        assert "already been used" in resp2.json()["detail"]
