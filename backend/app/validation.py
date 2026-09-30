import math
import re
from fastapi import HTTPException

# Limits mirror the column sizes in the migrations (users.email VARCHAR(100),
# first_name/last_name VARCHAR(50), city VARCHAR(100), tags.name VARCHAR(50)),
# so an oversized value is refused with a 400 instead of failing the INSERT.
MAX_EMAIL = 100
MAX_NAME = 50
MAX_CITY = 100
MAX_BIO = 500
MAX_TAG = 50
MAX_PASSWORD = 128
MAX_REASON = 500
MAX_MESSAGE = 1000
MAX_SEARCH = 50
MAX_TOKEN = 512
MAX_ID = 2**31 - 1  # ids are SERIAL (int4)

GENDERS = ("male", "female", "other")
ORIENTATIONS = ("homo", "hetero", "bi")

_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
# C0 controls and DEL. NUL is the one that matters most: PostgreSQL text
# columns cannot hold it and psycopg raises on it, which used to surface as a 500.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_CONTROL_NO_NEWLINE_RE = re.compile(r"[\x00-\x1f\x7f]")
_INT_PARAM_RE = re.compile(r"-?[0-9]{1,10}")


def clean_str(
    value,
    field: str,
    max_len: int,
    *,
    min_len: int = 1,
    strip: bool = True,
    multiline: bool = False,
    nullable: bool = False,
) -> str | None:
    """Validate a user-supplied string and return the value to store.

    Rejects anything that is not a ``str``, strings that cannot be encoded as
    UTF-8 (lone surrogates such as ``"\\ud800"``, which JSON allows), NUL and
    other control characters, and values that are too short or too long.
    ``min_len`` is always checked against the stripped value, so a
    whitespace-only string counts as empty even when ``strip=False``.

    Args:
        value: The raw value, usually straight from the JSON body.
        field: Field name used in the error message.
        max_len: Maximum length in characters, after stripping if ``strip``.
        min_len: Minimum length in characters of the stripped value.
        strip: Return the value stripped of surrounding whitespace. Pass
            False for passwords, which must be kept exactly as typed.
        multiline: Allow tab, newline and carriage return (bio, messages).
        nullable: Accept ``None`` and return it unchanged.

    Returns:
        The validated string, or ``None`` if ``nullable`` and value is None.

    Raises:
        HTTPException: 400 if the value is not acceptable.
    """
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail=f"{field} must be a string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise HTTPException(status_code=400, detail=f"{field} contains invalid characters")
    if (_CONTROL_RE if multiline else _CONTROL_NO_NEWLINE_RE).search(value):
        raise HTTPException(status_code=400, detail=f"{field} contains invalid characters")

    stripped = value.strip()
    result = stripped if strip else value
    if len(stripped) < min_len:
        if min_len == 1:
            raise HTTPException(status_code=400, detail=f"{field} must be a non-empty string")
        raise HTTPException(status_code=400, detail=f"{field} must be at least {min_len} characters")
    if len(result) > max_len:
        raise HTTPException(status_code=400, detail=f"{field} must be at most {max_len} characters")
    return result


def clean_email(value, field: str = "email") -> str:
    """Validate an email address (length, characters and rough shape).

    Args:
        value: The raw value.
        field: Field name used in the error message.

    Returns:
        The stripped email address.

    Raises:
        HTTPException: 400 if it is not a well-formed address of at most
            ``MAX_EMAIL`` characters.
    """
    email = clean_str(value, field, MAX_EMAIL)
    if not _EMAIL_RE.fullmatch(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    return email


def clean_choice(value, field: str, allowed: tuple[str, ...]) -> str:
    """Validate that a value is exactly one of a closed set of strings.

    Args:
        value: The raw value.
        field: Field name used in the error message.
        allowed: The accepted values.

    Returns:
        The value.

    Raises:
        HTTPException: 400 if the value is not one of ``allowed``.
    """
    if not isinstance(value, str) or value not in allowed:
        raise HTTPException(status_code=400, detail=f"{field} must be one of: {', '.join(allowed)}")
    return value


def clean_int(value, field: str, lo: int, hi: int) -> int:
    """Validate a JSON integer within ``lo..hi``.

    Booleans, floats and numeric strings are refused (``True`` is an ``int``
    in Python, which would otherwise slip through).

    Args:
        value: The raw value.
        field: Field name used in the error message.
        lo: Smallest accepted value.
        hi: Largest accepted value.

    Returns:
        The integer.

    Raises:
        HTTPException: 400 if it is not an integer in range.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise HTTPException(status_code=400, detail=f"{field} must be an integer")
    if not lo <= value <= hi:
        raise HTTPException(status_code=400, detail=f"{field} must be between {lo} and {hi}")
    return value


def clean_float(value, field: str, lo: float, hi: float) -> float:
    """Validate a JSON number within ``lo..hi``.

    Booleans, NaN and infinities are refused.

    Args:
        value: The raw value.
        field: Field name used in the error message.
        lo: Smallest accepted value.
        hi: Largest accepted value.

    Returns:
        The number as a float.

    Raises:
        HTTPException: 400 if it is not a finite number in range.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HTTPException(status_code=400, detail=f"{field} must be a number")
    if not math.isfinite(value) or not lo <= value <= hi:
        raise HTTPException(status_code=400, detail=f"{field} must be between {lo} and {hi}")
    return float(value)


def parse_int_param(value: str | None, name: str, lo: int, hi: int) -> int | None:
    """Parse an optional integer query parameter within ``lo..hi``.

    Only plain ASCII digits with an optional leading minus are accepted, at
    most 10 of them, so huge numbers never reach the database.

    Args:
        value: Raw parameter value, or ``None`` if absent.
        name: Parameter name, used in the error message.
        lo: Smallest accepted value.
        hi: Largest accepted value.

    Returns:
        The integer, or ``None`` if the parameter is absent.

    Raises:
        HTTPException: 400 if the value is not an integer in range.
    """
    if value is None:
        return None
    if not _INT_PARAM_RE.fullmatch(value):
        raise HTTPException(status_code=400, detail=f"'{name}' must be an integer")
    number = int(value)
    if not lo <= number <= hi:
        raise HTTPException(status_code=400, detail=f"'{name}' must be between {lo} and {hi}")
    return number


def valid_target_id(target_id: int) -> int:
    """Route dependency: refuse ids that cannot exist (outside the int4 range).

    Use as ``@router.get(..., dependencies=[Depends(valid_target_id)])`` on
    routes with a ``{target_id}`` path parameter. Without it, an id such as
    ``99999999999999999999`` reaches PostgreSQL and fails with an
    out-of-range error.

    Args:
        target_id: Id from the URL, already parsed as an int by FastAPI.

    Returns:
        The id.

    Raises:
        HTTPException: 404 if the id is outside ``1..MAX_ID``.
    """
    if not 1 <= target_id <= MAX_ID:
        raise HTTPException(status_code=404, detail="user not found")
    return target_id
