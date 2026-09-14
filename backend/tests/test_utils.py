import io
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from PIL import Image


# ── helpers ───────────────────────────────────────────────────────────────────

JPEG_MAGIC = b'\xff\xd8\xff\xe0' + b'\x00' * 10
PNG_MAGIC  = b'\x89PNG\r\n\x1a\n' + b'\x00' * 10
GARBAGE    = b'GIF89a' + b'\x00' * 20


def make_jpeg_bytes(mode="RGB", size=(100, 100)):
    img = Image.new(mode, size, color=(128, 64, 32))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def make_png_bytes(mode="RGB", size=(50, 50)):
    img = Image.new(mode, size, color=(10, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_request(content_type="application/json", body=b'{"x": 1}', raise_on_json=False):
    """Minimal async-compatible mock of FastAPI Request."""
    async def json():
        if raise_on_json:
            raise ValueError("bad json")
        import json as _json
        return _json.loads(body)

    class _Req:
        headers = {"content-type": content_type}

    r = _Req()
    r.json = json
    return r


# ── is_valid_image ────────────────────────────────────────────────────────────

class TestIsValidImage:
    def test_jpeg_magic_accepted(self):
        from app.utils import is_valid_image
        assert is_valid_image(JPEG_MAGIC) is True

    def test_png_magic_accepted(self):
        from app.utils import is_valid_image
        assert is_valid_image(PNG_MAGIC) is True

    def test_gif_rejected(self):
        from app.utils import is_valid_image
        assert is_valid_image(GARBAGE) is False

    def test_empty_bytes_rejected(self):
        from app.utils import is_valid_image
        assert is_valid_image(b"") is False

    def test_truncated_magic_rejected(self):
        from app.utils import is_valid_image
        assert is_valid_image(b'\xff\xd8') is False

    def test_real_jpeg_accepted(self):
        from app.utils import is_valid_image
        assert is_valid_image(make_jpeg_bytes()) is True

    def test_real_png_accepted(self):
        from app.utils import is_valid_image
        assert is_valid_image(make_png_bytes()) is True


# ── require_json ──────────────────────────────────────────────────────────────

class TestRequireJson:
    async def test_valid_json_returns_parsed_body(self):
        from app.utils import require_json
        req = make_request(body=b'{"name": "alice", "age": 30}')
        data = await require_json(req)
        assert data == {"name": "alice", "age": 30}

    async def test_wrong_content_type_raises_415(self):
        from app.utils import require_json
        req = make_request(content_type="text/plain")
        with pytest.raises(HTTPException) as exc:
            await require_json(req)
        assert exc.value.status_code == 415

    async def test_form_content_type_raises_415(self):
        from app.utils import require_json
        req = make_request(content_type="application/x-www-form-urlencoded")
        with pytest.raises(HTTPException) as exc:
            await require_json(req)
        assert exc.value.status_code == 415

    async def test_invalid_json_body_raises_400(self):
        from app.utils import require_json
        req = make_request(raise_on_json=True)
        with pytest.raises(HTTPException) as exc:
            await require_json(req)
        assert exc.value.status_code == 400

    async def test_json_subtype_accepted(self):
        from app.utils import require_json
        req = make_request(content_type="application/json; charset=utf-8", body=b'{"ok": true}')
        data = await require_json(req)
        assert data["ok"] is True

    async def test_empty_json_object_accepted(self):
        from app.utils import require_json
        req = make_request(body=b'{}')
        assert await require_json(req) == {}


# ── process_photo ─────────────────────────────────────────────────────────────

class TestProcessPhoto:
    def test_valid_jpeg_returns_jpg_path(self):
        from app.utils import process_photo
        data = make_jpeg_bytes()
        with patch("os.makedirs"), patch.object(Image.Image, "save"):
            path = process_photo(data, "42")
        assert path.startswith("/backend/uploads/42/")
        assert path.endswith(".jpg")

    def test_valid_png_converted_to_jpeg(self):
        from app.utils import process_photo
        data = make_png_bytes()
        with patch("os.makedirs"), patch.object(Image.Image, "save"):
            path = process_photo(data, "1")
        assert path.endswith(".jpg")

    def test_rgba_image_converted_to_rgb(self):
        from app.utils import process_photo
        data = make_png_bytes(mode="RGBA")
        with patch("os.makedirs"), patch.object(Image.Image, "save") as mock_save:
            process_photo(data, "1")
        # save should have been called (no RGBA mode error)
        mock_save.assert_called_once()

    def test_invalid_image_bytes_raise_400(self):
        from app.utils import process_photo
        with pytest.raises(HTTPException) as exc:
            process_photo(b"not an image at all", "1")
        assert exc.value.status_code == 400

    def test_each_upload_gets_unique_filename(self):
        from app.utils import process_photo
        data = make_jpeg_bytes()
        with patch("os.makedirs"), patch.object(Image.Image, "save"):
            p1 = process_photo(data, "1")
            p2 = process_photo(data, "1")
        assert p1 != p2  # uuid4 is different each time

    def test_path_contains_user_id(self):
        from app.utils import process_photo
        data = make_jpeg_bytes()
        with patch("os.makedirs"), patch.object(Image.Image, "save"):
            path = process_photo(data, "99")
        assert "/99/" in path

    def test_makedirs_called_for_user_upload_dir(self):
        from app.utils import process_photo
        data = make_jpeg_bytes()
        with patch("os.makedirs") as mock_makedirs, patch.object(Image.Image, "save"):
            process_photo(data, "7")
        mock_makedirs.assert_called_once_with("/backend/uploads/7", exist_ok=True)
