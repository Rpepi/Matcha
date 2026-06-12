from itsdangerous import URLSafeTimedSerializer
import os
import smtplib
from email.message import EmailMessage

MAIL_SECRET = os.getenv("MAIL_SECRET")
FRONTEND_URL = os.getenv("FRONTED_URL", "http://localhost:5173")
serializer = URLSafeTimedSerializer(MAIL_SECRET)

def generate_verification_token(user_id: str) -> str:
    return serializer.dumps(user_id, salt="email-verify")

def _send_email(to: str, subject: str, body: str):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "no-reply@matcha.local"
    msg["To"] = to
    msg.set_content(body)
    with smtplib.SMTP(os.getenv("MAIL_HOST"), int(os.getenv("MAIL_PORT"))) as smtp:
        smtp.send_message(msg)


def send_verification_email(to: str, token: str):
    link = f"{FRONTEND_URL}/verify?token={token}"
    _send_email(to, "Verify your Matcha account", f"Click to verify your account: {link}")


def send_reset_email(to: str, token: str):
    link = f"{FRONTEND_URL}/reset-password?token={token}"
    _send_email(to, "Reset your Matcha password", f"Click to reset your password (link expires in 30 minutes): {link}")