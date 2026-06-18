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
    for sig in ALLOWED_MAGIC:
        if data.startswith(sig):
            return True
    return False


async def require_json(request: Request):
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(status_code=415, detail="Wrong content type")
    try:
        return await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")


def process_photo(data: bytes, user_id: int) -> str:
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
    except (UnidentifiedImageError, Exception):
        logger.warning("process_photo: invalid image data for user %s", user_id)
        raise HTTPException(status_code=400, detail="image file invalid")

    img = Image.open(io.BytesIO(data))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    img.thumbnail((800, 800))

    filename = f"{uuid.uuid4().hex}.jpg"
    path = f"/uploads/{user_id}/{filename}"
    os.makedirs(f"/uploads/{user_id}", exist_ok=True)
    img.save(path, format="JPEG", quality=85)

    return path
