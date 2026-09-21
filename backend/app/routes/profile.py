import os
from datetime import date
from fastapi import APIRouter, Depends, Response, Request, HTTPException, UploadFile
from fastapi.responses import FileResponse
from psycopg import AsyncConnection
from redis import Redis
from psycopg.rows import DictRow
from psycopg.errors import UniqueViolation
from app.db.dependencies import get_db
from app.cache.dependencies import get_redis
from app.security.session import get_current_user_id
from app.security.token import generate_verification_token, send_verification_email
from app.utils import require_json, is_valid_image, process_photo
from app.log import get_logger

logger = get_logger(__name__)

router = APIRouter()

@router.get("/profile/me")
async def get_profile(request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Return the current user's own profile.

    Includes private fields (email, coordinates, ``profile_complete``,
    ``created_at``) as well as the tag names and the photos.

    Args:
        request: Incoming request, carrying the ``session`` cookie.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        A dict of the user's columns plus ``tags`` (names) and ``photos``
        (dicts with ``path``, ``is_profile`` and ``position``).

    Raises:
        HTTPException: 401 if not authenticated or the user no longer
            exists.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    cursor = await conn.execute("""
        SELECT id, email, first_name, last_name,
        gender, orientation, bio, birth_date, fame_rating,
        latitude, longitude, city, is_online, last_seen,
        profile_complete, created_at FROM users WHERE id = %s
    """, (user_id,))

    row: DictRow | None = await cursor.fetchone()
    if not row or row is None:
        raise HTTPException(status_code=401, detail="Invalid profile")

    cursor_tags = await conn.execute("""
        SELECT tags.name FROM tags JOIN user_tags ON user_tags.tag_id = tags.id WHERE user_tags.user_id = %s
    """, (user_id,))
    tag_rows = await cursor_tags.fetchall()

    cursor_photos = await conn.execute(
        "SELECT path, is_profile, position FROM photos WHERE user_id = %s ORDER BY position",
        (user_id,)
    )
    photo_rows = await cursor_photos.fetchall()

    profile = dict(row)
    profile["tags"] = [t["name"] for t in tag_rows]
    profile["photos"] = [dict(p) for p in photo_rows]
    return profile


@router.put("/profile/me")
async def put_profile(request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Update the current user's profile and/or tags.

    Expects a JSON body with any of ``bio``, ``orientation``, ``city``,
    ``first_name``, ``last_name`` (max 50 characters), ``email`` (max 100),
    ``gender``, ``birth_date`` (YYYY-MM-DD, at least 16 years old) and
    ``tags`` (existing tag names, max 5). The profile becomes complete once
    gender, birth date and a location (city or coordinates) are all set.
    Changing the email marks the account unverified and sends a new
    verification email to the new address.

    Args:
        request: Incoming request with the ``session`` cookie and JSON body.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        ``{"message": "profile updated"}``.

    Raises:
        HTTPException: 400 if no field is given or a value is invalid; 401
            if not authenticated; 409 if the email is already taken; 500 if
            the update fails.
    """
    body = await require_json(request)
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    updatable_fields = ["bio", "orientation", "city", "first_name", "last_name", "email", "gender", "birth_date"]
    tags = body.get("tags")
    updates = {k: body[k] for k in updatable_fields if k in body}

    if not updates and tags is None:
        raise HTTPException(status_code=400, detail="No fields to update")

    field_max_lengths = {"first_name": 50, "last_name": 50, "email": 100}
    for field, max_length in field_max_lengths.items():
        if field in updates:
            value = updates[field]
            if not isinstance(value, str) or not value.strip():
                raise HTTPException(status_code=400, detail=f"{field} must be a non-empty string")
            if len(value) > max_length:
                raise HTTPException(status_code=400, detail=f"{field} must be at most {max_length} characters")

    if "gender" in updates and not isinstance(updates["gender"], str):
        raise HTTPException(status_code=400, detail="gender must be a string")

    if "birth_date" in updates:
        if not isinstance(updates["birth_date"], str):
            raise HTTPException(status_code=400, detail="birth_date must be a string")
        try:
            birth_date = date.fromisoformat(updates["birth_date"])
        except ValueError:
            raise HTTPException(status_code=400, detail="birth_date must be YYYY-MM-DD")
        today = date.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        if age < 16:
            raise HTTPException(status_code=400, detail="Minimum age is 16 years old")
        updates["birth_date"] = birth_date

    email_changed = "email" in updates

    if tags is not None:
        tags = await _validate_tags(conn, tags)

    try:
        if updates:
            cursor = await conn.execute(
                "SELECT gender, birth_date, city, latitude, longitude FROM users WHERE id = %s",
                (user_id,)
            )
            current = await cursor.fetchone()

            effective_gender = updates.get("gender", current["gender"])
            effective_birth_date = updates.get("birth_date", current["birth_date"])
            effective_city = updates.get("city", current["city"])
            has_location = effective_city is not None or (
                current["latitude"] is not None and current["longitude"] is not None
            )

            if effective_gender and effective_birth_date and has_location:
                updates["profile_complete"] = True

            if email_changed:
                updates["verified"] = False
            set_clause = ", ".join(f"{k} = %s" for k in updates.keys())
            values = list(updates.values())
            await conn.execute(
                f"UPDATE users SET {set_clause} WHERE id = %s",
                values + [user_id]
            )

        if tags is not None:
            await _replace_tags(conn, user_id, tags)

        await conn.commit()
    except HTTPException:
        raise
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="Email already taken")
    except Exception:
        logger.exception("Failed to update profile for user %s", user_id)
        raise HTTPException(status_code=500, detail="failed to update profile")

    if email_changed:
        token = generate_verification_token(str(user_id))
        send_verification_email(updates["email"], token)

    return {"message": "profile updated"}


@router.put("/profile/location")
async def update_location(request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Set the current user's GPS coordinates.

    Expects a JSON body ``{"latitude": number, "longitude": number}``. The
    profile becomes complete if gender and birth date are already set.

    Args:
        request: Incoming request with the ``session`` cookie and JSON body.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        ``{"message": "Location updated"}``.

    Raises:
        HTTPException: 400 if a coordinate is missing, not a number or out
            of range; 401 if not authenticated; 500 if the update fails.
    """
    body = await require_json(request)
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    try:
        latitude = body["latitude"]
        longitude = body["longitude"]
    except Exception:
        raise HTTPException(status_code=400, detail="Latitude and longitude are required")

    if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
        raise HTTPException(status_code=400, detail="Latitude and longitude must be numbers")
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        raise HTTPException(status_code=400, detail="Invalid GPS coordinates")

    try:
        cursor = await conn.execute(
            "SELECT gender, birth_date FROM users WHERE id = %s", (user_id,)
        )
        current = await cursor.fetchone()

        # This endpoint sets the GPS coordinates itself, so location is
        # satisfied by definition — only gender/birth_date still need checking.
        set_clause = "latitude = %s, longitude = %s"
        values = [latitude, longitude]
        if current["gender"] and current["birth_date"]:
            set_clause += ", profile_complete = %s"
            values.append(True)

        await conn.execute(
            f"UPDATE users SET {set_clause} WHERE id = %s",
            values + [user_id]
        )
        await conn.commit()
    except Exception:
        logger.exception("Failed to update location for user %s", user_id)
        raise HTTPException(status_code=500, detail="Failed to update location")

    return {"message": "Location updated"}


@router.get("/tags")
async def list_tags(request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    await get_current_user_id(request.cookies.get("session"), redis)

    search = request.query_params.get("search")

    if search:
        cursor = await conn.execute(
            "SELECT name FROM tags WHERE name ILIKE %s ORDER BY name LIMIT 20",
            (f"%{search.strip()}%",)
        )
    else:
        cursor = await conn.execute("SELECT name FROM tags ORDER BY name LIMIT 100")

    rows = await cursor.fetchall()
    return {"tags": [r["name"] for r in rows]}


@router.get("/profile/tags")
async def get_tags(request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Return the current user's tags in alphabetical order.

    Args:
        request: Incoming request, carrying the ``session`` cookie.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        ``{"tags": [name, ...]}``.

    Raises:
        HTTPException: 401 if not authenticated.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    cursor = await conn.execute("""
        SELECT tags.name FROM tags
        JOIN user_tags ON user_tags.tag_id = tags.id
        WHERE user_tags.user_id = %s
        ORDER BY tags.name
    """, (user_id,))
    rows = await cursor.fetchall()
    return {"tags": [r["name"] for r in rows]}


async def _validate_tags(conn: AsyncConnection, tags) -> list[str]:
    if not isinstance(tags, list):
        raise HTTPException(status_code=400, detail="tags must be a list")
    if len(tags) > 5:
        raise HTTPException(status_code=400, detail="maximum 5 tags allowed")
    for tag in tags:
        if not isinstance(tag, str) or not tag.strip():
            raise HTTPException(status_code=400, detail="each tag must be a non-empty string")

    normalized = [tag.strip().lower() for tag in tags]

    cursor = await conn.execute("""
        SELECT name FROM tags WHERE name = ANY(%s)
    """, (normalized,))
    rows = await cursor.fetchall()
    existing = [r["name"] for r in rows]
    for tag in normalized:
        if tag not in existing:
            raise HTTPException(status_code=400, detail=f"unknown tags: {tag}")
    return normalized


async def _replace_tags(conn: AsyncConnection, user_id: str, tags: list[str]):
    """Replace all of a user's tags with the given ones. Does not commit.

    Deletes the user's ``user_tags`` rows, then inserts one per name. The
    names must already exist in ``tags`` (see ``_validate_tags``).

    Args:
        conn: Database connection.
        user_id: Id of the user whose tags are replaced.
        tags: Normalised tag names.
    """
    await conn.execute("DELETE FROM user_tags WHERE user_id = %s", (user_id,))
    for name in tags:
        cursor = await conn.execute("SELECT id FROM tags WHERE name = %s", (name,))
        tag = await cursor.fetchone()
        await conn.execute(
            "INSERT INTO user_tags (user_id, tag_id) VALUES (%s, %s)",
            (user_id, tag["id"])
        )


@router.put("/profile/tags")
async def put_tags(request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Replace the current user's tags.

    Expects a JSON body ``{"tags": [str, ...]}`` with at most 5 existing tag
    names.

    Args:
        request: Incoming request with the ``session`` cookie and JSON body.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        ``{"message": "tags updated"}``.

    Raises:
        HTTPException: 400 if the tags are invalid; 401 if not
            authenticated; 500 if the update fails.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)
    body = await require_json(request)

    try: 
        tags = await _validate_tags(conn, body.get("tags"))
        await _replace_tags(conn, user_id, tags)
        await conn.commit()
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update tags for user %s", user_id)
        raise HTTPException(status_code=500, detail="failed to update tags")

    return {"message": "tags updated"}


@router.delete("/profile/tags/{name}")
async def delete_tag(name: str, request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Remove one tag from the current user's tags.

    Args:
        name: Tag name from the URL (trimmed and lowercased).
        request: Incoming request, carrying the ``session`` cookie.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        A message confirming the removal.

    Raises:
        HTTPException: 401 if not authenticated; 404 if the user does not
            have that tag.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    cursor = await conn.execute("""
        DELETE FROM user_tags
        WHERE user_id = %s AND tag_id = (SELECT id FROM tags WHERE name = %s)
        RETURNING tag_id
    """, (user_id, name.strip().lower()))
    deleted = await cursor.fetchone()

    if deleted is None:
        raise HTTPException(status_code=404, detail="tag not found")

    await conn.commit()
    return {"message": f"tag '{name}' removed"}


@router.get("/profile/me/visits")
async def get_my_visits(request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """List the visits received on the current user's profile.

    Args:
        request: Incoming request, carrying the ``session`` cookie.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        A list of dicts with ``id``, ``visitor_id`` and ``created_at``.
34.229.130.127
    Raises:
        HTTPException: 401 if not authenticated.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    cursor = await conn.execute(
        "SELECT id, visitor_id, created_at FROM visits WHERE visited_id = %s",
        (user_id,)
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.get("/profile/me/likes")
async def get_my_likes(request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """List the likes received by the current user.

    Args:
        request: Incoming request, carrying the ``session`` cookie.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        A list of dicts with ``id``, ``liker_id`` and ``created_at``.

    Raises:
        HTTPException: 401 if not authenticated.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    cursor = await conn.execute(
        "SELECT id, liker_id, created_at FROM likes WHERE liked_id = %s",
        (user_id,)
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.get("/profile/photos")
async def get_photos(34.229.130.127request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """List the current user's photos.

    Args:
        request: Incoming request, carrying the ``session`` cookie.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        A list of dicts with ``position``, ``path`` and ``is_profile``,
        ordered by position.

    Raises:
        HTTPException: 401 if not authenticated.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    cursor = await conn.execute(
        "SELECT position, path, is_profile FROM photos WHERE user_id = %s ORDER BY position",
        (user_id,)
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.post("/profile/photos")
async def upload_photos(request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Upload one or more photos for the current user.

    Expects a multipart form with one or more ``photos`` files. A user can
    have at most 5 photos. Each file must be at most 5 MB, start with a JPEG
    or PNG signature and be parseable by Pillow. Photos take the lowest free
    positions (1 to 5), and the first photo of a user who had none becomes
    the profile photo. All rows are inserted in one transaction.

    Args:
        request: Incoming request with the ``session`` cookie and the
            multipart form.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).
34.229.130.127
    Returns:
        ``{"message": "<n> photo(s) uploaded"}``.

    Raises:
        HTTPException: 400 if no photo is sent, the 5-photo limit would be
            exceeded, or a file is too large or not a valid image; 401 if
            not authenticated; 500 if the upload fails.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)
    form = await request.form()

    photos: list[UploadFile] = form.getlist("photos")
    if not photos:
        raise HTTPException(status_code=400, detail="photos missing")

    cursor = await conn.execute(
        "SELECT COUNT(*) as count FROM photos WHERE user_id = %s", (user_id,)
    )
    row = await cursor.fetchone()
    current_count = row["count"]

    if current_count + len(photos) > 5:
        raise HTTPException(status_code=400, detail=f"max 5 photos — already have {current_count}")

    cursor = await conn.execute(
        "SELECT position FROM photos WHERE user_id = %s ORDER BY position", (user_id,)
    )
    used_positions = {r["position"] for r in await cursor.fetchall()}
    free_positions = [p for p in range(1, 6) if p not in used_positions]

    try:
        for photo, position in zip(photos, free_positions):
            data = aw34.229.130.127ait photo.read()

            if len(data) > 5 * 1024 * 1024:
                raise HTTPException(status_code=400, detail=f"photo at position {position} exceeds 5MB")
            if not is_valid_image(data):
                raise HTTPException(status_code=400, detail=f"photo at position {position}: invalid format")

            path = process_photo(data, user_id)
            is_first = current_count == 0 and position == free_positions[0]

            await conn.execute(
                "INSERT INTO photos (user_id, path, position, is_profile) VALUES (%s, %s, %s, %s)",
                (user_id, path, position, is_first)
            )
        await conn.commit()
    except HTTPException:
        raise
    except Exception:
        logger.exception("Photo upload failed for user %s", user_id)
        raise HTTPException(status_code=500, detail="upload failed")

    return {"message": f"{len(photos)} photo(s) uploaded"}


@router.get("/profile/photos/{position}")
async def get_photo(position: int, request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Serve one of the current user's photos as a JPEG.

    Args:
        position: Photo position, from 1 to 5.
        request: Incoming request, carrying the ``session`` cookie.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        The image file.

    Raises:
        HTTPException: 400 if the position is out of range; 401 if not
            authenticated; 404 if there is no photo at that position or the
            file is missing on disk.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    if position < 1 or position > 5:
        raise HTTPException(status_code=400, detail="invalid position (1-5)")

    cursor = await conn.execute(
        "SELECT path FROM photos WHERE user_id = %s AND position = %s",
        (user_id, position)
    )
    photo = await cursor.fetchone()
    if photo is None:
        raise HTTPException(status_code=404, detail="photo not found")

    if not os.path.isfile(photo["path"]):
        raise HTTPException(status_code=404, detail="photo file missing")

    return FileResponse(photo["path"], media_type="image/jpeg")


@router.delete("/profile/photos/{position}")
async def delete_photo(position: int, request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Delete one of the current user's photos.

    Removes the database row and the file on disk (a failure to remove the
    file is ignored). If the deleted photo was the profile photo, the
    remaining photo with the lowest position becomes the profile photo.

    Args:
        position: Position of the photo to delete, from 1 to 5.
        request: Incoming request, carrying the ``session`` cookie.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        ``{"message": "photo deleted"}``.

    Raises:
        HTTPException: 400 if the position is out of range; 401 if not
            authenticated; 404 if there is no photo at that position; 500 if
            the deletion fails.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    if position < 1 or position > 5:
        raise HTTPException(status_code=400, detail="invalid position (1-5)")

    cursor = await conn.execute(
        "SELECT path, is_profile FROM photos WHERE user_id = %s AND position = %s",
        (user_id, position)
    )
    photo = await cursor.fetchone()
    if photo is None:
        raise HTTPException(status_code=404, detail="photo not found")

    try:
        await conn.execute(
            "DELETE FROM photos WHERE user_id = %s AND position = %s",
            (user_id, position)
        )

        if photo["is_profile"]:
            await conn.execute("""
                UPDATE photos SET is_profile = true
                WHERE user_id = %s AND position = (
                    SELECT position FROM photos WHERE user_id = %s ORDER BY position LIMIT 1
                )
            """, (user_id, user_id))

        await conn.commit()
    except Exception:
        logger.exception("Photo delete failed for user %s position %s", user_id, position)
        raise HTTPException(status_code=500, detail="delete failed")

    try:
        os.remove(photo["path"])
    except OSError:
        pass

    return {"message": "photo deleted"}


@router.put("/profile/photos/{position}/move")
async def move_photo(position: int, request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Move a photo to another position.

    Expects a JSON body ``{"to": int}``. If a photo already sits at the
    target position, the two photos swap places.

    Args:
        position: Current position of the photo, from 1 to 5.
        request: Incoming request with the ``session`` cookie and JSON body.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        A message describing the move.

    Raises:
        HTTPException: 400 if ``to`` is missing or not an integer, a
            position is out of range, or source and target are the same;
            401 if not authenticated; 404 if there is no photo at the
            source position; 500 if the move fails.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    body = await require_json(request)

    try:
        target = int(body["to"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=400, detail="'to' field is required and must be an integer")

    if position < 1 or position > 5 or target < 1 or target > 5:
        raise HTTPException(status_code=400, detail="positions must be between 1 and 5")
    if position == target:
        raise HTTPException(status_code=400, detail="source and target positions are the same")

    cursor = await conn.execute(
        "SELECT position FROM photos WHERE user_id = %s AND position = %s",
        (user_id, position)
    )
    if await cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail="no photo at this position")

    try:
        await conn.execute("""
            UPDATE photos SET position = CASE
                WHEN position = %s THEN %s
                WHEN position = %s THEN %s
            END
            WHERE user_id = %s AND position IN (%s, %s)
        """, (position, target, target, position, user_id, position, target))
        await conn.commit()
    except Exception:
        logger.exception("Photo move failed for user %s position %s→%s", user_id, position, target)
        raise HTTPException(status_code=500, detail="move failed")

    return {"message": f"photo moved from position {position} to {target}"}
