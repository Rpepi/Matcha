import asyncio
from argon2 import PasswordHasher
from pathlib import Path

ph = PasswordHasher(
    time_cost=2,
    memory_cost=19456,
    parallelism=1,
)

_COMMON_PASSWORDS = set(Path(__file__).with_name("10k-most-common.txt").read_text().splitlines())

async def hash_password(password: str) -> str:
    return await asyncio.to_thread(ph.hash, password)


async def verify_password(hashed: str, password: str) -> bool:
    try:
        return await asyncio.to_thread(ph.verify, hashed, password)
    except Exception:
        return False


def is_password_valid(pw: str) -> bool:
    if pw.isdigit():
        return False
    if pw.isalpha():
        return False
    if pw.lower() in _COMMON_PASSWORDS:
        return False
    return True
