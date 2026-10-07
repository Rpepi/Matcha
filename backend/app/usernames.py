import re
import secrets
import unicodedata
from psycopg import AsyncConnection
from psycopg.errors import UniqueViolation

_NOT_ALNUM_RE = re.compile(r"[^a-z0-9]")
_BASE_MAX_LEN = 20


def username_base(first_name: str) -> str:
    """Turn a first name into the letters-and-digits start of a username.

    Accents are dropped (``"José"`` gives ``"jose"``), everything that is not a
    letter or a digit is removed, and the result is lowercase and cut to 20
    characters so a numeric suffix always fits in the 30 of the column.

    Args:
        first_name: The name to start from.

    Returns:
        The base, or ``"user"`` if nothing usable is left.
    """
    ascii_name = unicodedata.normalize("NFKD", first_name).encode("ascii", "ignore").decode()
    base = _NOT_ALNUM_RE.sub("", ascii_name.lower())[:_BASE_MAX_LEN]
    return base or "user"


async def generate_username(conn: AsyncConnection, first_name: str) -> str:
    """Pick a free username for an account created without one (Google sign-in).

    Tries the first name followed by four random digits. The check is not a
    lock: the unique index is what really guards against two accounts racing
    for the same name, see ``is_username_conflict``.

    Args:
        conn: Database connection.
        first_name: First name given by the identity provider.

    Returns:
        A username that was free when it was checked.
    """
    base = username_base(first_name)
    for _ in range(10):
        candidate = f"{base}{secrets.randbelow(9000) + 1000}"
        cursor = await conn.execute(
            "SELECT 1 FROM users WHERE lower(username) = lower(%s)", (candidate,)
        )
        if await cursor.fetchone() is None:
            return candidate
    # Ten collisions in a row: widen the space instead of looping forever.
    return f"{base}{secrets.token_hex(4)}"


def is_username_conflict(error: UniqueViolation) -> bool:
    """Tell a duplicate username from a duplicate email in a unique violation.

    Args:
        error: The exception raised by the INSERT or UPDATE.

    Returns:
        True if the violated constraint is the username one.
    """
    diag = getattr(error, "diag", None)
    return "username" in (getattr(diag, "constraint_name", None) or "")
