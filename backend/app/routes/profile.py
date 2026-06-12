from fastapi import APIRouter, Depends, Response, Request, HTTPException
from psycopg import AsyncConnection
from redis import Redis
from psycopg.rows import DictRow
from psycopg.errors import UniqueViolation
from app.db.dependencies import get_db
from app.cache.dependencies import get_redis
from app.security.session import get_current_user_id
from app.utils import require_json


router = APIRouter()

@router.get("/profile/me")
async def get_profile(request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    
    user_id = get_current_user_id(request, redis)

    cursor = await conn.execute("""
        SELECT id, username, email, first_name, last_name,
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
async def post_profile(request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):

    body = await require_json(request)
    user_id = get_current_user_id(request, redis)

    updatable_fields = ["bio","orientation", "city"]
    tags = body.get("tags")
    
    updates = {k: body[k] for k in updatable_fields if k in body}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{k} = %s" for k in updates.keys()) #bio = %s,  ...
    values = list(updates.values())
    try:
        await conn.execute(
                f"UPDATE users SET {set_clause} WHERE id = %s", 
                values + [user_id]
        )
        await conn.execute("DELETE FROM user_tags WHERE user_id = %s", (user_id,))

        for tag_name in tags:
            await conn.execute(
                "INSERT INTO tags (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                (tag_name,)
            )
            cursor = await conn.execute("SELECT id FROM tags WHERE name = %s", (tag_name,))
            tag = await cursor.fetchone()
            await conn.execute(
                "INSERT INTO user_tags (user_id, tag_id) VALUES (%s, %s)",
                (user_id, tag["id"]))
            await conn.commit()

    except Exception as e:
        await conn.rollback()
        raise HTTPException(status_code=500, detail=f"failed to update tags: {e}")
    
    return {"message": "profile updated"}


@router.put("/profile/location")
async def update_location(request: Request, redis: Redis = Depends(get_redis),conn: AsyncConnection = Depends(get_db)):

    body = await require_json(request)
    user_id = get_current_user_id(request, redis)

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
        await conn.execute(
            "UPDATE users SET latitude = %s, longitude = %s WHERE id = %s",
            (latitude, longitude, user_id)
        )
        await conn.commit()
    except Exception as e:
        await conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update location: {e}")
    return {"message": "Location updated"}


@router.get("/profile/me/visits")
async def get_my_visits(request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):

    user_id = get_current_user_id(request, redis)

    cursor = await conn.execute("""
        SELECT id, visitor_id, created_at FROM visits WHERE visited_id = %s
    """, (user_id,))

    rows = await cursor.fetchall()
    return [dict(r) for r in rows]

@router.get("/profile/me/likes")
async def get_my_visits(request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):

    user_id = get_current_user_id(request, redis)

    cursor = await conn.execute("""
        SELECT id, liker_id, created_at FROM likes WHERE liked_id = %s
    """, (user_id,))

    rows = await cursor.fetchall()
    return [dict(r) for r in rows]

