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
        tags = _validate_tags(tags)

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
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    cursor = await conn.execute("""
        SELECT tags.name FROM tags
        JOIN user_tags ON user_tags.tag_id = tags.id
        WHERE user_tags.user_id = %s
        ORDER BY tags.name
    """, (user_id,))
    rows = await cursor.fetchall()
    return {"tags": [r["name"] for r in rows]}


def _validate_tags(tags) -> list[str]:
    if not isinstance(tags, list):
        raise HTTPException(status_code=400, detail="tags must be a list")
    if len(tags) > 5:
        raise HTTPException(status_code=400, detail="maximum 5 tags allowed")
    for tag in tags:
        if not isinstance(tag, str) or not tag.strip():
            raise HTTPException(status_code=400, detail="each tag must be a non-empty string")
    # Normalized (trimmed + lowercased) so "Hiking" and "hiking" reuse the
    # same row instead of splitting the common_tags matching signal.
    return [tag.strip().lower() for tag in tags]


async def _replace_tags(conn: AsyncConnection, user_id: str, tags: list[str]):
    await conn.execute("DELETE FROM user_tags WHERE user_id = %s", (user_id,))
    for name in tags:
        await conn.execute(
            "INSERT INTO tags (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
            (name,)
        )
        cursor = await conn.execute("SELECT id FROM tags WHERE name = %s", (name,))
        tag = await cursor.fetchone()
        await conn.execute(
            "INSERT INTO user_tags (user_id, tag_id) VALUES (%s, %s)",
            (user_id, tag["id"])
        )


@router.put("/profile/tags")
async def put_tags(request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    user_id = await get_current_user_id(request.cookies.get("session"), redis)
    body = await require_json(request)

    tags = _validate_tags(body.get("tags"))

    try:
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
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    cursor = await conn.execute(
        "SELECT id, visitor_id, created_at FROM visits WHERE visited_id = %s",
        (user_id,)
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.get("/profile/me/likes")
async def get_my_likes(request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    cursor = await conn.execute(
        "SELECT id, liker_id, created_at FROM likes WHERE liked_id = %s",
        (user_id,)
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.get("/profile/photos")
async def get_photos(request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    cursor = await conn.execute(
        "SELECT position, path, is_profile FROM photos WHERE user_id = %s ORDER BY position",
        (user_id,)
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.post("/profile/photos")
async def upload_photos(request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
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
            data = await photo.read()

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
