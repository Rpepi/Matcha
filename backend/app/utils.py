from fastapi import HTTPException, Request
from PIL import Image, UnidentifiedImageError
import io, uuid, os
from app.log import get_logger

logger = get_logger(__name__)


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


async def require_json(request: Request):
    """Parse the request body as JSON.

    Args:
        request: Incoming request.

    Returns:
        The decoded JSON value. It is not guaranteed to be an object.

    Raises:
        HTTPException: 415 if ``Content-Type`` is not ``application/json``;
            400 if the body is not valid JSON.
    """
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(status_code=415, detail="Wrong content type")
    try:
        return await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")


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
