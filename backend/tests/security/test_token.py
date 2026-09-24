import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestGenerateVerificationToken:
    def test_returns_a_string(self):
        from app.security.token import generate_verification_token
        token = generate_verification_token("42", "alice@test.com")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_contains_user_id_and_email(self):
        from app.security.token import generate_verification_token, serializer
        token = generate_verification_token("42", "alice@test.com")
        payload = serializer.loads(token, salt="email-verify", max_age=3600)
        assert payload == {"user_id": "42", "email": "alice@test.com"}

    def test_different_users_get_different_tokens(self):
        from app.security.token import generate_verification_token
        t1 = generate_verification_token("1", "a@test.com")
        t2 = generate_verification_token("2", "b@test.com")
        assert t1 != t2

    def test_token_is_verifiable_after_generation(self):
        """Token can be decoded back to the original user_id and email."""
        from app.security.token import generate_verification_token, serializer
        token = generate_verification_token("99", "carol@test.com")
        decoded = serializer.loads(token, salt="email-verify", max_age=3600)
        assert decoded["user_id"] == "99"
        assert decoded["email"] == "carol@test.com"

    def test_same_user_different_email_gives_different_payload(self):
        """The token is bound to the address it was issued for, not just
        the user id — a token for an old address must be distinguishable
        from one for a new address on the same account."""
        from app.security.token import generate_verification_token, serializer
        token_old = generate_verification_token("1", "old@test.com")
        token_new = generate_verification_token("1", "new@test.com")
        payload_old = serializer.loads(token_old, salt="email-verify", max_age=3600)
        payload_new = serializer.loads(token_new, salt="email-verify", max_age=3600)
        assert payload_old["email"] != payload_new["email"]


class TestSendVerificationEmail:
    def test_sends_to_correct_address(self):
        from app.security.token import send_verification_email
        mock_smtp = MagicMock()

        with patch("smtplib.SMTP", return_value=mock_smtp.__enter__.return_value):
            mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
            mock_smtp.__exit__ = MagicMock(return_value=False)
            with patch("smtplib.SMTP") as smtp_cls:
                smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
                smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
                send_verification_email("alice@test.com", "sometoken")
                mock_smtp.send_message.assert_called_once()
                msg = mock_smtp.send_message.call_args.args[0]
                assert msg["To"] == "alice@test.com"

    def test_email_contains_token_link(self):
        from app.security.token import send_verification_email
        mock_smtp = MagicMock()

        with patch("smtplib.SMTP") as smtp_cls:
            smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
            smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            send_verification_email("alice@test.com", "mytoken123")
            msg = mock_smtp.send_message.call_args.args[0]
            assert "mytoken123" in msg.get_content()

    def test_connects_to_configured_mail_host(self):
        from app.security.token import send_verification_email

        with patch("smtplib.SMTP") as smtp_cls, \
             patch("os.getenv", side_effect=lambda k, *a: {"MAIL_HOST": "mailpit", "MAIL_PORT": "1025"}.get(k, "")):
            smtp_cls.return_value.__enter__ = MagicMock(return_value=MagicMock())
            smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            send_verification_email("alice@test.com", "token")
            smtp_cls.assert_called_once_with("mailpit", 1025, timeout=10)


class TestSendResetEmail:
    def test_sends_to_correct_address(self):
        from app.security.token import send_reset_email
        mock_smtp = MagicMock()

        with patch("smtplib.SMTP") as smtp_cls:
            smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
            smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            send_reset_email("alice@test.com", "resettoken")
            msg = mock_smtp.send_message.call_args.args[0]
            assert msg["To"] == "alice@test.com"

    def test_email_contains_token(self):
        from app.security.token import send_reset_email
        mock_smtp = MagicMock()

        with patch("smtplib.SMTP") as smtp_cls:
            smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
            smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            send_reset_email("alice@test.com", "myresettoken")
            msg = mock_smtp.send_message.call_args.args[0]
            assert "myresettoken" in msg.get_content()

    def test_link_points_to_reset_password_path(self):
        from app.security.token import send_reset_email
        mock_smtp = MagicMock()

        with patch("smtplib.SMTP") as smtp_cls:
            smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
            smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            send_reset_email("alice@test.com", "tok")
            msg = mock_smtp.send_message.call_args.args[0]
            assert "/reset-password" in msg.get_content()

    def test_smtp_failure_is_logged_and_reraised(self):
        from app.security.token import send_verification_email
        with patch("smtplib.SMTP", side_effect=ConnectionRefusedError("mailpit down")), \
             patch("app.security.token.logger") as mock_logger:
            with pytest.raises(ConnectionRefusedError):
                send_verification_email("alice@test.com", "token")
        mock_logger.exception.assert_called_once()

    def test_different_subject_than_verification_email(self):
        from app.security.token import send_reset_email, send_verification_email
        msgs = []
        mock_smtp = MagicMock()
        mock_smtp.send_message = MagicMock(side_effect=lambda m: msgs.append(m))

        with patch("smtplib.SMTP") as smtp_cls:
            smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
            smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            send_verification_email("a@test.com", "t1")
            send_reset_email("a@test.com", "t2")

        assert msgs[0]["Subject"] != msgs[1]["Subject"]
