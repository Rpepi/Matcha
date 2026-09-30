"""Token bucket rate limiting, backed by Redis and a Lua script.

The script itself lives in ``token_bucket.lua`` next to this module. It is
registered once at startup (``app/__init__.py``) and stored on
``app.state.rate_limit_script``, so every request reuses the same cached
script (``EVALSHA``) instead of shipping the source each time.

Running the check inside Lua is what makes it correct: Redis executes the
whole script as one indivisible step, so two requests arriving together
cannot both read "one token left" and both be allowed.

Each budget is one Redis key, ``rl:<scope>:<ip|account>:<id>``:

- ``scope`` keeps routes independent — hitting the like limit must not block
  reporting.
- the identity half is the IP for routes reached before login, and the user id
  once there is a session. Keying an authenticated route on the IP would let
  one person on a shared network (a campus, a mobile carrier) exhaust everyone
  else's budget, and would let an attacker reset their own by changing address.
"""
from fastapi import Depends, HTTPException, Request, WebSocket

from app.cache.dependencies import get_redis
from app.security.session import get_current_user_id


async def consume(script, key: str, limit: int, seconds: int, burst: int | None = None) -> tuple[bool, int]:
    """Take one token out of ``key``'s bucket.

    Args:
        script: The registered Lua script (``app.state.rate_limit_script``).
        key: Full Redis key for this bucket.
        limit: Requests allowed per ``seconds``.
        seconds: Length of the window the limit is expressed over.
        burst: Bucket size — how many requests may arrive back to back.
            Defaults to ``limit``, i.e. a full window's worth at once.

    Returns:
        ``(allowed, retry_after_seconds)``. ``retry_after_seconds`` is 0 when
        the request was allowed.
    """
    rate = limit / seconds
    size = burst if burst is not None else limit
    allowed, _remaining, retry_after = await script(keys=[key], args=[size, rate])
    return bool(allowed), int(retry_after)


def rate_limit(scope: str, limit: int, seconds: int, burst: int | None = None, by: str = "ip"):
    """Build a FastAPI dependency that rate limits one route.

    Attach it on the decorator, not as a handler parameter, so it runs before
    the handler reads or validates the body — a malformed flood costs budget
    too:

        @router.post("/auth/login", dependencies=[Depends(rate_limit("login", 10, 60))])

    The returned dependency raises and returns nothing: FastAPI discards the
    value of a dependency declared this way and only cares whether it raised.

    Args:
        scope: Budget name, shared by every route that should share a counter
            (``like`` and ``unlike`` use the same one on purpose, so alternating
            between them cannot double the effective rate).
        limit: Requests allowed per ``seconds``.
        seconds: Window length the limit is expressed over.
        burst: Bucket size; defaults to ``limit``.
        by: ``"ip"`` for routes reached before login, ``"account"`` once a
            session exists.

    Returns:
        An async dependency callable.

    Raises:
        ValueError: If ``by`` is neither ``"ip"`` nor ``"account"`` — caught at
            import time rather than silently falling back to the wrong identity.
    """
    if by not in ("ip", "account"):
        raise ValueError(f"rate_limit(by=...) must be 'ip' or 'account', got {by!r}")

    async def dependency(request: Request, redis=Depends(get_redis)):
        if by == "account":
            # Raises 401 when there is no valid session, before any budget is
            # spent — an anonymous caller cannot drain someone else's bucket.
            user_id = await get_current_user_id(request.cookies.get("session"), redis)
            identity = f"account:{user_id}"
        else:
            identity = f"ip:{request.client.host if request.client else 'unknown'}"

        allowed, retry_after = await consume(
            request.app.state.rate_limit_script,
            f"rl:{scope}:{identity}",
            limit,
            seconds,
            burst,
        )
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Too many requests",
                headers={"Retry-After": str(retry_after)},
            )

    # Lets tests read a route's configured budget off the route itself, so the
    # table in tests/routes/test_rate_limits.py is the spec for these numbers.
    dependency.rate_limit = {
        "scope": scope,
        "limit": limit,
        "seconds": seconds,
        "burst": burst if burst is not None else limit,
        "by": by,
    }
    return dependency


async def check_chat_message_limit(websocket: WebSocket, user_id: int | str) -> tuple[bool, int]:
    """Rate limit one chat frame: 60 per minute, up to 10 back to back.

    A WebSocket cannot use the dependency above: a dependency on a WebSocket
    route is resolved once, at connection time, while what needs limiting is
    every frame sent over a socket that stays open. So the handler calls this
    directly inside its receive loop.

    Sending several short messages in a row is normal, hence the burst of 10;
    the sustained rate is what stops a flood.

    Args:
        websocket: The live connection (used to reach the registered script).
        user_id: Id of the sender.

    Returns:
        ``(allowed, retry_after_seconds)``.
    """
    return await consume(
        websocket.app.state.rate_limit_script,
        f"rl:chat:account:{user_id}",
        limit=60,
        seconds=60,
        burst=10,
    )
