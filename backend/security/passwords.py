# security/passwords.py

import asyncio
from argon2 import PasswordHasher

ph = PasswordHasher(
    time_cost=2,        # 2 pass (default: 3)
    memory_cost=19456,  # 19 MB (default: 64 MB)
    parallelism=1       # 1 thread (default: 4)
)

async def hash_password(password: str) -> str:
    return await asyncio.to_thread(ph.hash, password)

async def verify_password(hash: str, password: str) -> bool:
    try:
        return await asyncio.to_thread(ph.verify, hash, password)
    except Exception:
        return False