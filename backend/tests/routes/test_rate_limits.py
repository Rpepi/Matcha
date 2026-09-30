"""Which routes are rate limited, and with which budget.

This table is the specification of those numbers: change a limit in a route
decorator and this fails until the table is updated too, so the budgets stay
reviewable in one place.

How the limiter *behaves* is tested in tests/security/test_rate_limit.py,
against a real Redis. Here we only check the wiring.
"""
import pytest

from app import create_app

# (method, path) -> scope, limit, seconds, burst, keyed by
EXPECTED = {
    ("POST", "/auth/login"):                  ("login",          10,   60,  3, "ip"),
    ("POST", "/auth/register"):               ("register",        5, 3600,  5, "ip"),
    ("POST", "/auth/forgot-password"):        ("forgot-password", 3, 3600,  3, "ip"),
    ("GET",  "/oauth/google/login"):          ("oauth-login",    10,   60, 10, "ip"),

    ("GET",    "/users"):                     ("browse",         30,   60, 10, "account"),
    ("POST",   "/users/{target_id}/like"):    ("like",           20,   60,  5, "account"),
    ("DELETE", "/users/{target_id}/like"):    ("like",           20,   60,  5, "account"),
    ("POST",   "/users/{target_id}/block"):   ("block",          10,   60, 10, "account"),
    ("DELETE", "/users/{target_id}/block"):   ("block",          10,   60, 10, "account"),
    ("POST",   "/users/{target_id}/report"):  ("report",          5, 3600,  5, "account"),
    ("POST",   "/profile/photos"):            ("upload-photo",    5, 3600,  5, "account"),
    ("PUT",    "/profile/me"):                ("profile-update", 10, 3600, 10, "account"),
}

# Called on nearly every page load by the frontend: a budget here would break
# normal use, so their absence is deliberate and asserted.
MUST_STAY_UNLIMITED = [
    ("GET", "/auth/me"),
    ("GET", "/profile/me"),
    ("GET", "/tags"),
    ("GET", "/notifications/stream"),
    ("GET", "/profile/photos/{position}"),
    ("GET", "/users/{target_id}/photos/{position}"),
]


def flatten(application):
    """Yield (path, methods, route); include_router wraps routers on this FastAPI."""
    for route in application.routes:
        if hasattr(route, "original_router"):
            prefix = getattr(getattr(route, "include_context", None), "prefix", "") or ""
            for inner in route.original_router.routes:
                yield prefix + inner.path, getattr(inner, "methods", None), inner
        else:
            yield route.path, getattr(route, "methods", None), route


def configured_limits():
    """Read every route's rate limit off the app itself."""
    found = {}
    for path, methods, route in flatten(create_app()):
        for dep in getattr(route, "dependencies", []):
            cfg = getattr(dep.dependency, "rate_limit", None)
            if cfg is None:
                continue
            for method in (methods or set()) - {"HEAD", "OPTIONS"}:
                found[(method, path)] = (
                    cfg["scope"], cfg["limit"], cfg["seconds"], cfg["burst"], cfg["by"],
                )
    return found


class TestBudgets:
    @pytest.mark.parametrize("route", sorted(EXPECTED), ids=lambda r: f"{r[0]} {r[1]}")
    def test_route_has_the_expected_budget(self, route):
        assert configured_limits().get(route) == EXPECTED[route]

    def test_no_route_is_limited_without_being_listed_here(self):
        """A new limiter must be declared in this table, so budgets stay reviewable."""
        assert set(configured_limits()) == set(EXPECTED)

    @pytest.mark.parametrize("route", MUST_STAY_UNLIMITED, ids=lambda r: f"{r[0]} {r[1]}")
    def test_hot_read_routes_are_not_limited(self, route):
        assert route not in configured_limits()


class TestKeying:
    def test_pre_login_routes_are_keyed_by_ip(self):
        """Before a session exists there is no account to key on."""
        for (method, path), cfg in configured_limits().items():
            if path.startswith(("/auth/", "/oauth/")):
                assert cfg[4] == "ip", f"{method} {path} should be keyed by ip"

    def test_authenticated_routes_are_keyed_by_account(self):
        """An IP is shared (campus, mobile carrier) and trivially changed."""
        for (method, path), cfg in configured_limits().items():
            if not path.startswith(("/auth/", "/oauth/")):
                assert cfg[4] == "account", f"{method} {path} should be keyed by account"

    def test_like_and_unlike_share_one_budget(self):
        """Otherwise alternating between them doubles the effective rate."""
        limits = configured_limits()

        assert limits[("POST", "/users/{target_id}/like")][0] == \
               limits[("DELETE", "/users/{target_id}/like")][0]

    def test_block_and_unblock_share_one_budget(self):
        limits = configured_limits()

        assert limits[("POST", "/users/{target_id}/block")][0] == \
               limits[("DELETE", "/users/{target_id}/block")][0]


class TestRouteTestsAreNotRationed:
    async def test_the_limiter_is_stubbed_out_for_route_tests(self, client):
        """Real counters are process-wide; without this, tests would starve each other."""
        responses = [await client.post("/auth/login", json={}) for _ in range(30)]

        assert not any(r.status_code == 429 for r in responses)
