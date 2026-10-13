"""The browser frontend asks for 4xx answers as 200 + X-Status (see SoftErrorsMiddleware)."""


class TestSoftErrors:
    async def test_without_the_header_the_status_is_the_real_one(self, client):
        res = await client.get("/profile/me")
        assert res.status_code == 401
        assert "x-status" not in res.headers

    async def test_with_the_header_a_4xx_becomes_200_with_the_real_status(self, client):
        res = await client.get("/profile/me", headers={"X-Soft-Errors": "1"})
        assert res.status_code == 200
        assert res.headers["x-status"] == "401"
        assert res.json() == {"detail": "Not Authenticated"}

    async def test_a_validation_error_keeps_its_body(self, client):
        res = await client.post("/auth/login", content=b"not json", headers={"X-Soft-Errors": "1", "Content-Type": "text/plain"})
        assert res.status_code == 200
        assert res.headers["x-status"] == "415"
        assert res.json()["detail"] == "Wrong content type"

    async def test_success_is_untouched(self, client):
        res = await client.get("/auth/session", headers={"X-Soft-Errors": "1"})
        assert res.status_code == 200
        assert "x-status" not in res.headers

    async def test_any_other_header_value_changes_nothing(self, client):
        res = await client.get("/profile/me", headers={"X-Soft-Errors": "yes"})
        assert res.status_code == 401


async def run_middleware(status: int, request_headers):
    from app import SoftErrorsMiddleware

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": status, "headers": [(b"retry-after", b"7")]})
        await send({"type": "http.response.body", "body": b"{}"})

    sent = []

    async def send(message):
        sent.append(message)

    await SoftErrorsMiddleware(app)({"type": "http", "headers": request_headers}, None, send)
    return sent[0]


class TestSoftErrorsMiddleware:
    async def test_server_errors_are_never_softened(self):
        start = await run_middleware(503, [(b"x-soft-errors", b"1")])
        assert start["status"] == 503

    async def test_other_headers_are_kept(self):
        start = await run_middleware(429, [(b"x-soft-errors", b"1")])
        assert start["status"] == 200
        assert (b"retry-after", b"7") in start["headers"]
        assert (b"x-status", b"429") in start["headers"]
