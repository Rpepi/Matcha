"""The token bucket itself, against a real Redis.

These tests do not mock Redis: the whole point of running the decision inside
a Lua script is what Redis guarantees while executing it, which a mock cannot
reproduce. They use logical DB 15, flushed before each test, so they never
touch the dev data in DB 0.

Route tests (everywhere else) replace the script with an always-allow stub in
``tests/conftest.py`` — the limiter is covered here, once.
"""
import asyncio
import os
from pathlib import Path

import pytest
import redis.asyncio as aredis
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.cache.dependencies import get_redis
from app.security.rate_limit import consume, rate_limit

LUA = (Path(__file__).resolve().parents[2] / "app" / "security" / "token_bucket.lua").read_text()


@pytest.fixture
async def redis_client():
    client = aredis.Redis(
        host=os.getenv("REDIS_HOST", "cache"),
        port=6379,
        password=os.environ["REDIS_PASSWORD"],
        db=15,
        decode_responses=True,
    )
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.fixture
def script(redis_client):
    return redis_client.register_script(LUA)


def build_app(script, redis_client, *, by="ip", limit=3, seconds=60, burst=None):
    """A one-route app carrying a real limiter, driven over ASGI."""
    application = FastAPI()
    application.state.rate_limit_script = script
    application.state.redis = redis_client
    application.dependency_overrides[get_redis] = lambda: redis_client

    @application.get("/x", dependencies=[Depends(rate_limit("probe", limit, seconds, burst, by=by))])
    async def endpoint():
        return {"ok": True}

    return application


def client_for(application, ip="1.1.1.1", cookie=None):
    cookies = {"session": cookie} if cookie else None
    return AsyncClient(
        transport=ASGITransport(app=application, client=(ip, 5000)),
        base_url="http://test",
        cookies=cookies,
    )


# ── the script ────────────────────────────────────────────────────────────────

class TestTokenBucket:
    async def test_first_request_is_allowed(self, script):
        allowed, retry_after = await consume(script, "k", limit=5, seconds=60)
        assert allowed is True
        assert retry_after == 0

    async def test_bucket_starts_full_then_refuses(self, script):
        """burst=3 means exactly 3 back to back, the 4th is refused."""
        results = [await consume(script, "k", limit=3, seconds=60) for _ in range(4)]

        assert [allowed for allowed, _ in results] == [True, True, True, False]

    async def test_refusal_says_when_to_retry(self, script):
        for _ in range(2):
            await consume(script, "k", limit=2, seconds=60)

        allowed, retry_after = await consume(script, "k", limit=2, seconds=60)

        assert allowed is False
        assert retry_after > 0

    async def test_tokens_refill_over_time(self, script):
        # 10/second: one token is back roughly 100 ms after the bucket empties.
        for _ in range(2):
            await consume(script, "k", limit=10, seconds=1, burst=2)
        assert (await consume(script, "k", limit=10, seconds=1, burst=2))[0] is False

        await asyncio.sleep(0.3)

        assert (await consume(script, "k", limit=10, seconds=1, burst=2))[0] is True

    async def test_every_key_gets_a_ttl(self, redis_client, script):
        """Without one, a bucket would sit in Redis forever: a memory leak."""
        await consume(script, "k", limit=5, seconds=60)

        assert await redis_client.ttl("k") > 0

    async def test_refused_requests_do_not_extend_the_block(self, script):
        """Hammering while over budget must not push the recovery further away."""
        for _ in range(2):
            await consume(script, "k", limit=2, seconds=10)
        _, first = await consume(script, "k", limit=2, seconds=10)

        for _ in range(20):
            await consume(script, "k", limit=2, seconds=10)
        _, after_hammering = await consume(script, "k", limit=2, seconds=10)

        assert after_hammering <= first


class TestConcurrency:
    async def test_parallel_requests_cannot_overshoot_the_budget(self, script):
        """The reason the decision lives in Lua.

        Read-then-write from Python would let concurrent callers all read the
        same count and all be allowed. Here 50 requests race for a budget of 5
        and exactly 5 get through.
        """
        results = await asyncio.gather(
            *[consume(script, "k", limit=5, seconds=60) for _ in range(50)]
        )

        assert sum(1 for allowed, _ in results if allowed) == 5


class TestBucketsAreSeparate:
    async def test_two_accounts_do_not_share_a_budget(self, script):
        for _ in range(3):
            await consume(script, "rl:like:account:1", limit=3, seconds=60)
        assert (await consume(script, "rl:like:account:1", limit=3, seconds=60))[0] is False

        allowed, _ = await consume(script, "rl:like:account:2", limit=3, seconds=60)

        assert allowed is True

    async def test_two_ips_do_not_share_a_budget(self, script):
        for _ in range(3):
            await consume(script, "rl:login:ip:1.1.1.1", limit=3, seconds=60)
        assert (await consume(script, "rl:login:ip:1.1.1.1", limit=3, seconds=60))[0] is False

        allowed, _ = await consume(script, "rl:login:ip:2.2.2.2", limit=3, seconds=60)

        assert allowed is True

    async def test_two_scopes_do_not_share_a_budget(self, script):
        """Exhausting likes must not also block reporting."""
        for _ in range(3):
            await consume(script, "rl:like:account:1", limit=3, seconds=60)

        allowed, _ = await consume(script, "rl:report:account:1", limit=3, seconds=60)

        assert allowed is True


# ── the FastAPI dependency ────────────────────────────────────────────────────

class TestRateLimitDependency:
    async def test_over_budget_returns_429_with_retry_after(self, script, redis_client):
        application = build_app(script, redis_client, limit=2, seconds=60)

        async with client_for(application) as c:
            assert [(await c.get("/x")).status_code for _ in range(2)] == [200, 200]
            response = await c.get("/x")

        assert response.status_code == 429
        assert int(response.headers["Retry-After"]) > 0

    async def test_separate_ips_have_separate_budgets_through_the_route(self, script, redis_client):
        application = build_app(script, redis_client, limit=2, seconds=60)

        async with client_for(application, ip="10.0.0.1") as a:
            for _ in range(2):
                await a.get("/x")
            assert (await a.get("/x")).status_code == 429

        async with client_for(application, ip="10.0.0.2") as b:
            assert (await b.get("/x")).status_code == 200

    async def test_account_keying_uses_the_session_owner(self, script, redis_client, monkeypatch):
        """Two sessions belonging to different users get different buckets."""
        async def fake_user(cookie, _redis):
            return {"cookie-a": "1", "cookie-b": "2"}[cookie]

        monkeypatch.setattr("app.security.rate_limit.get_current_user_id", fake_user)
        application = build_app(script, redis_client, by="account", limit=2, seconds=60)

        async with client_for(application, cookie="cookie-a") as a:
            for _ in range(2):
                await a.get("/x")
            assert (await a.get("/x")).status_code == 429

        async with client_for(application, cookie="cookie-b") as b:
            assert (await b.get("/x")).status_code == 200

    async def test_account_keying_without_a_session_is_401_and_costs_nothing(self, script, redis_client):
        """An anonymous caller cannot drain someone else's bucket."""
        application = build_app(script, redis_client, by="account", limit=2, seconds=60)

        async with client_for(application) as c:
            assert (await c.get("/x")).status_code == 401

        assert await redis_client.keys("rl:*") == []

    def test_an_invalid_by_is_rejected_at_import_time(self):
        """A typo must fail loudly, not silently fall back to IP keying."""
        with pytest.raises(ValueError):
            rate_limit("probe", limit=1, seconds=60, by="acount")
