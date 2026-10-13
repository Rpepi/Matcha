"""A trailing slash in FRONTEND_URL must not leak into links, redirects or the Origin check.

With "http://localhost:5173/" the Google sign-in redirected to "//browse" (the
frontend's "Page not found"), emailed links pointed to "//verify", and every
chat WebSocket was refused, since a browser's Origin never ends with "/".
"""
import importlib
import pytest
import app.routes.chat as chat
import app.routes.oauth as oauth
import app.security.token as token

MODULES = [chat, oauth, token]


@pytest.fixture
def frontend_url_with_slash(monkeypatch):
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173/")
    for module in MODULES:
        importlib.reload(module)
    yield
    monkeypatch.undo()
    for module in MODULES:
        importlib.reload(module)


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.__name__)
def test_trailing_slash_is_dropped(frontend_url_with_slash, module):
    assert module.FRONTEND_URL == "http://localhost:5173"


def test_emailed_links_have_a_single_slash(frontend_url_with_slash, monkeypatch):
    sent = {}
    monkeypatch.setattr(token, "_send_email", lambda to, subject, body: sent.update(body=body))

    token.send_verification_email("a@b.c", "tok")

    assert "http://localhost:5173/verify?token=tok" in sent["body"]
