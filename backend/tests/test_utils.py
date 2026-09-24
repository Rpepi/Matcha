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


def make_request(content_type="application/json", body=b'{"x": 1}', raise_on_json=False,
                 chunks=None, content_length=None):
    """Minimal async-compatible mock of FastAPI Request.

    ``require_json`` reads ``request.stream()``, so the body is served as
    chunks: ``chunks`` if given, otherwise the whole ``body`` in one piece.
    ``raise_on_json`` is kept for old tests: it swaps the body for bytes
    that are not JSON.
    """
    if raise_on_json:
        body = b"not json {"

    async def stream():
        for chunk in (chunks if chunks is not None else [body]):
            yield chunk

    headers = {"content-type": content_type}
    if content_length is not None:
        headers["content-length"] = str(content_length)

    class _Req:
        pass

    r = _Req()
    r.headers = headers
    r.stream = stream
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

    @pytest.mark.parametrize("body", [b'[1, 2]', b'"text"', b'42', b'null', b'true', b'[]'])
    async def test_non_object_body_raises_400(self, body):
        from app.utils import require_json
        with pytest.raises(HTTPException) as exc:
            await require_json(make_request(body=body))
        assert exc.value.status_code == 400

    @pytest.mark.parametrize("body", [b'', b'{', b'{"a":}', b'\xff\xfe', b'{"a": NaN}', b'{"a": Infinity}', b'{"a": -Infinity}'])
    async def test_malformed_body_raises_400(self, body):
        from app.utils import require_json
        with pytest.raises(HTTPException) as exc:
            await require_json(make_request(body=body))
        assert exc.value.status_code == 400

    async def test_deeply_nested_body_raises_400(self):
        from app.utils import require_json
        body = b"[" * 30_000 + b"]" * 30_000  # 60 KB: under the size cap, over the recursion limit
        with pytest.raises(HTTPException) as exc:
            await require_json(make_request(body=body))
        assert exc.value.status_code == 400

    async def test_oversized_content_length_raises_413_without_reading(self):
        from app.utils import require_json, MAX_JSON_BYTES
        req = make_request(body=b'{}', content_length=MAX_JSON_BYTES + 1)
        with pytest.raises(HTTPException) as exc:
            await require_json(req)
        assert exc.value.status_code == 413

    async def test_oversized_body_without_content_length_raises_413(self):
        """Chunked uploads send no Content-Length; the cap must still hold."""
        from app.utils import require_json, MAX_JSON_BYTES
        chunk = b" " * 8192
        chunks = [chunk] * (MAX_JSON_BYTES // len(chunk) + 2)
        with pytest.raises(HTTPException) as exc:
            await require_json(make_request(chunks=chunks))
        assert exc.value.status_code == 413

    async def test_body_split_across_chunks_is_reassembled(self):
        from app.utils import require_json
        req = make_request(chunks=[b'{"na', b'me": "al', b'ice"}'])
        assert await require_json(req) == {"name": "alice"}

    async def test_body_exactly_at_the_limit_is_accepted(self):
        from app.utils import require_json, MAX_JSON_BYTES
        filler = MAX_JSON_BYTES - len(b'{"a": ""}')
        body = b'{"a": "' + b"x" * filler + b'"}'
        assert len(body) == MAX_JSON_BYTES
        assert (await require_json(make_request(body=body)))["a"] == "x" * filler

    async def test_lone_surrogate_escape_is_parsed_not_crashed(self):
        """JSON allows "\\ud800"; require_json returns it, clean_str refuses it."""
        from app.utils import require_json
        data = await require_json(make_request(body=b'{"a": "\\ud800"}'))
        assert data["a"] == "\ud800"


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
