"""Rate limiting, end to end through the real routes.

``tests/conftest.py`` switches every limiter off so route tests do not
ration each other. Here the limiter under test is switched back on, on the
*real* module-level singletons with their configured budgets, so these tests
are also the specification of those budgets. The limiters keep process-wide
counters, hence the reset before and after every test (``flush`` on each
bucket: public API that works whatever way the buckets are organised).

Tests that state the intended per-client behaviour but fail today are
``xfail(strict=True)``: once the limiter is fixed they flip to XPASS, which
strict mode reports as a failure, prompting removal of the marker.
"""
import inspect
import json
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from app.security import rate_limit
from tests.conftest import _build_app, make_session_cookie

HTTP_LIMITERS = (
    rate_limit.loginLimiter, rate_limit.registerLimiter, rate_limit.forgotPasswordLimiter,
    rate_limit.oauthLoginLimiter, rate_limit.LikeLimiter, rate_limit.blockLimiter,
    rate_limit.uploadPhotoLimiter, rate_limit.reportLimiter,
)

# (test id, limiter, method, path, requests allowed per window)
IP_KEYED = [
    ("login", rate_limit.loginLimiter, "POST", "/auth/login", 10),
    ("register", rate_limit.registerLimiter, "POST", "/auth/register", 5),
    ("forgot-password", rate_limit.forgotPasswordLimiter, "POST", "/auth/forgot-password", 3),
    ("oauth-login", rate_limit.oauthLoginLimiter, "GET", "/oauth/google/login", 10),
]
USER_KEYED = [
    ("like", rate_limit.LikeLimiter, "POST", "/users/{id}/like", 20),
    ("unlike", rate_limit.LikeLimiter, "DELETE", "/users/{id}/like", 20),
    ("block", rate_limit.blockLimiter, "POST", "/users/{id}/block", 10),
    ("unblock", rate_limit.blockLimiter, "DELETE", "/users/{id}/block", 10),
    ("report", rate_limit.reportLimiter, "POST", "/users/{id}/report", 5),
    ("upload-photo", rate_limit.uploadPhotoLimiter, "POST", "/profile/photos", 50),
]

# Invalid on every endpoint above, so a request never reaches the database and is
# answered by the route's own validation (400/404) unless the limiter stops it first.
HOSTILE_BODY = {"email": "a\x00b@x.co", "password": "x"}


async def _reset_all():
    for limiter in (*HTTP_LIMITERS, rate_limit.messageLimiter):
        for bucket in limiter.limiter.buckets():
            result = bucket.flush()
            if inspect.isawaitable(result):
                await result


@pytest.fixture(autouse=True)
async def fresh_budgets():
    await _reset_all()
    yield
    await _reset_all()


@pytest.fixture
def limited_app(mock_db, mock_redis):
    """The test app with the HTTP limiters switched back ON."""
    mock_redis.get = AsyncMock(return_value="1")  # session -> user 1
    with patch("app.db.pool.open_pool", new_callable=AsyncMock), \
         patch("app.db.pool.close_pool", new_callable=AsyncMock), \
         patch("redis.asyncio.Redis", return_value=mock_redis):
        app = _build_app(mock_db, mock_redis)
        for limiter in HTTP_LIMITERS:
            app.dependency_overrides.pop(limiter, None)
        yield app


def client_for(app, host="10.0.0.1", session=True) -> AsyncClient:
    """A client whose requests come from ``host``, logged in unless ``session=False``."""
    return AsyncClient(
        transport=ASGITransport(app=app, client=(host, 4321)),
        base_url="http://test",
        cookies={"session": make_session_cookie()} if session else None,
    )


async def fire(client: AsyncClient, method: str, path: str, body=None, headers=None):
    h = {"content-type": "application/json", **(headers or {})}
    content = None if method == "GET" else (b"{}" if body is None else json.dumps(body).encode())
    return await client.request(method, path, content=content, headers=h)


async def count_until_429(client, method, path, cap, **kwargs) -> int:
    """How many requests are accepted before the first 429 (at most ``cap``)."""
    for accepted in range(cap):
        if (await fire(client, method, path, **kwargs)).status_code == 429:
            return accepted
    return cap


# ── every limited endpoint ────────────────────────────────────────────────────

@pytest.mark.parametrize("name,limiter,method,path,budget", IP_KEYED + USER_KEYED, ids=[c[0] for c in IP_KEYED + USER_KEYED])
class TestEachEndpointIsLimited:
    async def test_the_configured_budget_is_enforced(self, limited_app, name, limiter, method, path, budget):
        path = path.format(id=2)
        async with client_for(limited_app) as client:
            accepted = await count_until_429(client, method, path, cap=budget + 5)
            blocked = await fire(client, method, path)

        assert accepted == budget
        assert blocked.status_code == 429
        assert blocked.json() == {"detail": "Too Many Requests"}


@pytest.mark.parametrize("name,limiter,method,path,budget", IP_KEYED[:3], ids=[c[0] for c in IP_KEYED[:3]])
class TestHostileRequestsAreRationed:
    async def test_invalid_requests_count_against_the_budget(self, limited_app, mock_db, name, limiter, method, path, budget):
        """The limiter runs before the body is read or validated, so garbage costs budget too."""
        async with client_for(limited_app) as client:
            statuses = [(await fire(client, method, path, body=HOSTILE_BODY)).status_code for _ in range(budget + 2)]

        assert statuses == [400] * budget + [429] * 2
        mock_db.execute.assert_not_called()

    async def test_a_throttled_request_is_refused_before_its_body_is_read(self, limited_app, name, limiter, method, path, budget):
        async with client_for(limited_app) as client:
            await count_until_429(client, method, path, cap=budget + 5)
            oversized = await client.request(method, path, content=b" " * 200_000,
                                             headers={"content-type": "application/json"})

        assert oversized.status_code == 429  # not 413: require_json never ran


@pytest.mark.parametrize("name,limiter,method,path,budget", USER_KEYED[:5], ids=[c[0] for c in USER_KEYED[:5]])
class TestUserBudgetsFollowTheUserNotTheTarget:
    async def test_budget_is_shared_across_targets(self, limited_app, name, limiter, method, path, budget):
        """The like limit is on likes, not on likes per person: every target counts towards it."""
        async with client_for(limited_app) as client:
            statuses = [(await fire(client, method, path.format(id=target))).status_code
                        for target in range(2, budget + 5)]

        assert 429 not in statuses[:budget]
        assert statuses[budget:] == [429] * 3


# ── who is being counted ──────────────────────────────────────────────────────

class TestBudgetIdentity:
    async def test_rotating_x_forwarded_for_cannot_reset_the_login_budget(self, limited_app):
        """The header is client-controlled, so it must never be a way around the limit."""
        async with client_for(limited_app) as client:
            statuses = [
                (await fire(client, "POST", "/auth/login", body=HOSTILE_BODY,
                            headers={"X-Forwarded-For": f"203.0.113.{i}"})).status_code
                for i in range(1, 15)
            ]

        assert statuses == [400] * 10 + [429] * 4

    async def test_anonymous_request_to_a_user_limited_route_is_401_and_costs_nothing(self, limited_app):
        async with client_for(limited_app, session=False) as anonymous:
            statuses = [(await fire(anonymous, "POST", "/users/2/block")).status_code for _ in range(12)]
        assert statuses == [401] * 12

        async with client_for(limited_app) as user:  # the budget was not touched
            assert (await fire(user, "POST", "/users/2/block")).status_code == 404

    @pytest.mark.xfail(
        strict=True, raises=AssertionError,
        reason="Limiter(Rate(...)) builds ONE bucket shared by every key: 10 bad logins a minute "
               "from anywhere lock every visitor out of /auth/login. Needs a per-key BucketFactory.",
    )
    async def test_login_budget_is_per_client_address(self, limited_app):
        async with client_for(limited_app, host="10.0.0.1") as attacker:
            await count_until_429(attacker, "POST", "/auth/login", cap=15, body=HOSTILE_BODY)
            assert (await fire(attacker, "POST", "/auth/login", body=HOSTILE_BODY)).status_code == 429

        async with client_for(limited_app, host="10.0.0.2") as bystander:
            assert (await fire(bystander, "POST", "/auth/login", body=HOSTILE_BODY)).status_code != 429

    @pytest.mark.xfail(
        strict=True, raises=AssertionError,
        reason="Same root cause: one user's blocks/likes/reports use up everybody's budget.",
    )
    async def test_user_budget_is_per_user(self, limited_app, mock_redis):
        async with client_for(limited_app) as client:
            await count_until_429(client, "POST", "/users/2/block", cap=15)
            assert (await fire(client, "POST", "/users/2/block")).status_code == 429

            mock_redis.get = AsyncMock(return_value="2")  # the same browser, now another user's session
            assert (await fire(client, "POST", "/users/3/block")).status_code != 429
