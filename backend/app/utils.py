from fastapi import HTTPException, Request
from PIL import Image, UnidentifiedImageError
import io, json, uuid, os
from app.log import get_logger

logger = get_logger(__name__)

MAX_JSON_BYTES = 64 * 1024


ALLOWED_MAGIC = {
    b'\xff\xd8\xff': 'jpeg',
    b'\x89PNG\r\n\x1a\n': 'png',
}


def is_valid_image(data: bytes) -> bool:
    """Check whether some bytes start with a JPEG or PNG signature.

    Only the magic bytes are inspected, never the content type sent by the
    client. This does not guarantee the file is a well-formed image; see
    ``process_photo`` for the full parse.

    Args:
        data: Raw file content.

    Returns:
        True if the data starts with a JPEG or PNG signature.
    """
    for sig in ALLOWED_MAGIC:
        if data.startswith(sig):
            return True
    return False


def _reject_json_constant(name: str):
    """``json.loads`` hook refusing ``NaN``/``Infinity``, which JSON does not allow."""
    raise ValueError(f"invalid JSON constant {name}")


async def require_json(request: Request) -> dict:
    """Parse the request body as a JSON object.

    The body is read in chunks and refused as soon as it passes
    ``MAX_JSON_BYTES``, so an oversized or endless body is never held in
    memory in full (this also covers chunked uploads that send no
    ``Content-Length``).

    Args:
        request: Incoming request.

    Returns:
        The decoded JSON object.

    Raises:
        HTTPException: 415 if ``Content-Type`` is not ``application/json``;
            413 if the body is larger than ``MAX_JSON_BYTES``; 400 if the
            body is not valid JSON or is not a JSON object.
    """
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(status_code=415, detail="Wrong content type")

    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_JSON_BYTES:
        raise HTTPException(status_code=413, detail="Request body too large")

    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_JSON_BYTES:
            raise HTTPException(status_code=413, detail="Request body too large")
        chunks.append(chunk)

    try:
        body = json.loads(b"".join(chunks), parse_constant=_reject_json_constant)
    except (ValueError, RecursionError):  # ValueError covers bad UTF-8 and bad JSON
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")
    return body


def process_photo(data: bytes, user_id: int) -> str:
    """Validate, normalise and store an uploaded photo.

    Parses the image with Pillow (``verify()`` then reopen, since verify
    consumes the image), converts RGBA/P images to RGB, shrinks it to fit
    within 1280x1280 and saves it as a JPEG (quality 92) to
    ``/backend/uploads/<user_id>/<uuid>.jpg``, creating the directory if
    needed.

    Args:
        data: Raw image bytes.
        user_id: Id of the user owning the photo.

    Returns:
        Filesystem path of the saved JPEG.

    Raises:
        HTTPException: 400 if Pillow cannot parse the data as an image.
    """
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
    except (UnidentifiedImageError, Exception):
        logger.warning("process_photo: invalid image data for user %s", user_id)
        raise HTTPException(status_code=400, detail="image file invalid")

    img = Image.open(io.BytesIO(data))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    img.thumbnail((1280, 1280), Image.Resampling.LANCZOS)

    filename = f"{uuid.uuid4().hex}.jpg"
    path = f"/backend/uploads/{user_id}/{filename}"
    os.makedirs(f"/backend/uploads/{user_id}", exist_ok=True)
    img.save(path, format="JPEG", quality=92)

    return path
