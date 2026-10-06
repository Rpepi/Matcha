"""Who is online.

A user is online while at least one of their notification streams is open: the
frontend opens one on every page once the user is logged in and closes it when
they leave or log out, so an open stream is the best signal the app has that
somebody is there.

The number of open streams of a user is kept in Redis (``presence:connections:<id>``),
not in a Python variable, so it counts every tab and stays right whichever
process serves a stream. ``users.is_online`` and ``users.last_seen`` are only
written when the count goes from 0 to 1 and back to 0.

If the server stops while streams are open, their counters would stay above
zero for ever: ``reset_presence`` starts every run from a clean slate. It
assumes a single server process, which is how the app is started; with several
workers it would have to run once, outside of them.
"""
from redis.asyncio import Redis
from app.db import pool as pool_module
from app.log import get_logger

logger = get_logger(__name__)

CONNECTIONS_KEY = "presence:connections:{user_id}"


async def user_connected(redis: Redis, user_id: int | str) -> None:
    """Record one more open stream for a user.

    The first one marks the user online.

    Args:
        redis: Redis client.
        user_id: Id of the user who opened the stream.
    """
    count = await redis.incr(CONNECTIONS_KEY.format(user_id=user_id))
    if count == 1:
        async with pool_module.pool.connection() as conn:
            await conn.execute("UPDATE users SET is_online = true WHERE id = %s", (user_id,))
            await conn.commit()


async def user_disconnected(redis: Redis, user_id: int | str) -> None:
    """Record one stream less for a user.

    When it was their last one, the user goes offline and ``last_seen`` is set
    to now.

    Args:
        redis: Redis client.
        user_id: Id of the user whose stream closed.
    """
    key = CONNECTIONS_KEY.format(user_id=user_id)
    count = await redis.decr(key)
    if count <= 0:
        await redis.delete(key)  # never keep a zero or a negative count around
        async with pool_module.pool.connection() as conn:
            await conn.execute(
                "UPDATE users SET is_online = false, last_seen = NOW() WHERE id = %s", (user_id,)
            )
            await conn.commit()


async def reset_presence(redis: Redis) -> None:
    """Forget every open stream: nobody can be connected to a server that just started.

    Deletes all the counters and marks the users still flagged online as
    offline, last seen now (the closest the app knows to when they left).

    Args:
        redis: Redis client.
    """
    async for key in redis.scan_iter(match=CONNECTIONS_KEY.format(user_id="*")):
        await redis.delete(key)
    async with pool_module.pool.connection() as conn:
        cursor = await conn.execute(
            "UPDATE users SET is_online = false, last_seen = NOW() WHERE is_online"
        )
        await conn.commit()
    if cursor.rowcount:
        logger.info("Presence reset: %d user(s) were still flagged online", cursor.rowcount)
