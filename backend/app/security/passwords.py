import asyncio
from argon2 import PasswordHasher
from pathlib import Path
from app.log import get_logger


ph = PasswordHasher(
    time_cost=2,
    memory_cost=19456,
    parallelism=1,
)

logger = get_logger(__name__)

_COMMON_PASSWORDS = set(Path(__file__).with_name("10k-most-common.txt").read_text().splitlines())

async def hash_password(password: str) -> str:
    """Hash a password with Argon2id.

    Runs in a worker thread so the CPU-heavy hashing does not block the
    event loop.

    Args:
        password: Plaintext password.

    Returns:
        The encoded Argon2 hash.
    """
    return await asyncio.to_thread(ph.hash, password)


async def verify_password(hashed: str, password: str) -> bool:
    """Check a password against an Argon2 hash.

    Runs in a worker thread. Any error (mismatch, malformed hash) counts as
    a failed verification.

    Args:
        hashed: Stored Argon2 hash.
        password: Plaintext password to check.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    try:
        return await asyncio.to_thread(ph.verify, hashed, password)
    except Exception:
        return False


def is_password_valid(pw: str) -> bool :
    """Check that a password is not trivially weak.

    Rejects passwords made only of digits, only of letters, or found
    (case-insensitively) in the list of the 10,000 most common passwords.

    Args:
        pw: Plaintext password.

    Returns:
        True if the password is acceptable, False otherwise.
    """
    if len(pw) < 8:
        logger.info("Password too short")
        return False
    if len(pw) > 64:
        logger.info("Password too long")
        return False
    if pw.isdigit():
        logger.info("Password contain only digits")
        return False
    if pw.isalpha():
        logger.info("Password contain only letters")
        return False
    if pw.lower() in _COMMON_PASSWORDS:
        logger.info("Password is too common")
        return False
    

    return True
