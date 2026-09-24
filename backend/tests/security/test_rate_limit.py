"""Unit tests for ``app/security/rate_limit.py``.

The limiter classes are exercised directly with real Starlette ``Request``
objects. Who-gets-which-budget (per client, per user, X-Forwarded-For, shared
across targets) is deliberately NOT tested here: it depends on how a limiter's
buckets are built, and ``fresh()`` builds its own, so such a test could not tell
a fixed limiter from a broken one. Those contracts are tested on the real,
module-level limiters in ``tests/routes/test_rate_limits.py``.
"""
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from fastapi import HTTPException, Response
from starlette.requests import Request
from pyrate_limiter import Duration, Limiter, Rate

from app.security import rate_limit
from app.security.rate_limit import RateLimiter, user_identifier
from tests.conftest import make_session_cookie


def make_request(path="/auth/login", method="POST", headers=None, client=("10.0.0.1", 5555),
                 redis=None, cookie=None):
    """A real Starlette Request, without a routing table behind it.

    ``scope["app"]`` deliberately has no ``routes`` attribute: the stock
    ``fastapi_limiter.RateLimiter`` walks ``request.app.routes`` and crashes
    on this project's FastAPI (see the ``RateLimiter`` docstring), so a
    request like this one fails with AttributeError if that walk ever comes back.
    """
    hdrs = {k.lower(): v for k, v in (headers or {}).items()}
    if cookie:
        hdrs["cookie"] = f"session={cookie}"
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [(k.encode(), v.encode()) for k, v in hdrs.items()],
        "client": client,
        "app": SimpleNamespace(state=SimpleNamespace(redis=redis)),
    }
    return Request(scope)


def fresh(times=2, **kwargs) -> RateLimiter:
    """A limiter with its own, empty budget of ``times`` requests per minute."""
    return RateLimiter(limiter=Limiter(Rate(times, Duration.MINUTE)), **kwargs)


async def hit(limiter: RateLimiter, request: Request):
    """Send one request through the limiter: returns None, or raises the 429."""
    return await limiter(request, Response())


async def allowed(limiter: RateLimiter, request: Request) -> bool:
    try:
        await hit(limiter, request)
        return True
    except HTTPException as e:
        assert e.status_code == 429
        return False


# ── RateLimiter ───────────────────────────────────────────────────────────────

class TestRateLimiter:
    async def test_allows_the_budget_then_answers_429(self):
        limiter = fresh(times=3)
        request = make_request()

        assert [await allowed(limiter, request) for _ in range(5)] == [True, True, True, False, False]

    async def test_over_budget_error_is_a_429_too_many_requests(self):
        limiter = fresh(times=1)
        request = make_request()
        await hit(limiter, request)

        with pytest.raises(HTTPException) as exc:
            await hit(limiter, request)

        assert exc.value.status_code == 429
        assert exc.value.detail == "Too Many Requests"

    async def test_works_without_the_apps_route_table(self):
        """Regression: the stock RateLimiter walks ``request.app.routes`` and 500s on every request."""
        request = make_request()
        assert not hasattr(request.scope["app"], "routes")

        await hit(fresh(), request)  # must not raise AttributeError

    async def test_each_limiter_has_its_own_budget(self):
        login, register = fresh(times=1), fresh(times=1)
        request = make_request()

        await hit(login, request)

        assert await allowed(register, request)
        assert not await allowed(login, request)


# ── user_identifier ───────────────────────────────────────────────────────────

class TestUserIdentifier:
    async def test_returns_the_session_owner_as_a_string(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value="7")

        identifier = await user_identifier(make_request(redis=redis, cookie=make_session_cookie()))

        assert identifier == "7"
        redis.get.assert_awaited_once_with("session:testsession")

    async def test_no_session_cookie_is_a_401_not_a_500(self):
        redis = AsyncMock()

        with pytest.raises(HTTPException) as exc:
            await user_identifier(make_request(redis=redis))

        assert exc.value.status_code == 401
        redis.get.assert_not_called()

    async def test_forged_session_cookie_is_a_401(self):
        redis = AsyncMock()

        with pytest.raises(HTTPException) as exc:
            await user_identifier(make_request(redis=redis, cookie="abc$" + "0" * 64))

        assert exc.value.status_code == 401
        redis.get.assert_not_called()

    async def test_expired_session_is_a_401(self):
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc:
            await user_identifier(make_request(redis=redis, cookie=make_session_cookie()))

        assert exc.value.status_code == 401

    async def test_unauthenticated_request_costs_no_budget(self):
        """The identifier fails before the limiter is asked, so anonymous traffic cannot burn a user's budget."""
        limiter = fresh(times=1, identifier=user_identifier)
        redis = AsyncMock()
        redis.get = AsyncMock(return_value="7")

        for _ in range(3):
            with pytest.raises(HTTPException) as exc:
                await hit(limiter, make_request(redis=redis))  # no cookie
            assert exc.value.status_code == 401

        assert await allowed(limiter, make_request(redis=redis, cookie=make_session_cookie()))


# ── test-suite wiring ─────────────────────────────────────────────────────────

class TestRouteTestsSwitchLimitersOff:
    def test_every_http_limiter_is_overridden_in_the_shared_test_app(self, mock_db, mock_redis):
        """A limiter added to rate_limit.py but not to conftest would silently
        start rationing every route test, and its counters are process-wide, so
        the failures would depend on test order."""
        from tests.conftest import _build_app

        app = _build_app(mock_db, mock_redis)
        limiters = {name: obj for name, obj in vars(rate_limit).items() if isinstance(obj, RateLimiter)}

        assert limiters, "no RateLimiter found in rate_limit.py: this guard is testing nothing"
        missing = sorted(name for name, obj in limiters.items() if obj not in app.dependency_overrides)
        assert not missing, (
            f"{missing} are not disabled in tests/conftest.py::_build_app: add them to its "
            f"dependency_overrides loop"
        )
