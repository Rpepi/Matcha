from itsdangerous import URLSafeTimedSerializer
import os
import smtplib
from email.message import EmailMessage
from app.log import get_logger

logger = get_logger(__name__)

MAIL_SECRET = os.getenv("MAIL_SECRET")
MAIL_HOST = os.getenv("MAIL_HOST")
MAIL_PORT = os.getenv("MAIL_PORT")

if not MAIL_SECRET or not MAIL_HOST or not MAIL_PORT:
    raise RuntimeError("env variable MAIL_SECRET not set")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

serializer = URLSafeTimedSerializer(MAIL_SECRET)

def generate_verification_token(user_id: str) -> str:
    """Create a signed, timestamped email-verification token.

    The user id is signed with the ``email-verify`` salt.

    Args:
        user_id: Id of the user the token is issued for.

    Returns:
        A URL-safe signed token.
    """
    return serializer.dumps(user_id, salt="email-verify")

def _send_email(to: str, subject: str, body: str):
    """Send a plain-text email through the configured SMTP server.

    Sent from ``no-reply@matcha.local`` via ``MAIL_HOST``:``MAIL_PORT``
    (Mailpit in development).

    Args:
        to: Recipient address.
        subject: Subject line.
        body: Plain-text body.

    Raises:
        Exception: Any SMTP failure is logged, then re-raised.
    """
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "no-reply@matcha.local"
    msg["To"] = to
    msg.set_content(body)
    try:
        with smtplib.SMTP(MAIL_HOST, int(MAIL_PORT)) as smtp:
            smtp.send_message(msg)
    except Exception:
        logger.exception("Failed to send email to %s (subject: %s)", to, subject)
        raise


def send_verification_email(to: str, token: str):
    """Email the account-verification link.

    Args:
        to: Recipient address.
        token: Token from ``generate_verification_token``, appended to
            ``<FRONTEND_URL>/verify``.
    """
    link = f"{FRONTEND_URL}/verify?token={token}"
    _send_email(to, "Verify your Matcha account", f"Click to verify your account: {link}")


def send_reset_email(to: str, token: str):
    """Email the password-reset link (valid for 30 minutes).

    Args:
        to: Recipient address.
        token: Signed reset token, appended to
            ``<FRONTEND_URL>/reset-password``.
    """
    link = f"{FRONTEND_URL}/reset-password?token={token}"
    _send_email(to, "Reset your Matcha password", f"Click to reset your password (link expires in 30 minutes): {link}")