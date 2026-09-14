from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import FileResponse
from psycopg import AsyncConnection
from redis.asyncio import Redis
from datetime import date
import json
import os
from app.db.dependencies import get_db
from app.cache.dependencies import get_redis
from app.security.session import get_current_user_id
from app.utils import require_json
from app.log import get_logger
from app.routes.notifications import _notify

logger = get_logger(__name__)

router = APIRouter()


async def _get_user_or_404(conn: AsyncConnection, user_id: str) -> dict:
    cursor = await conn.execute("""
        SELECT id, first_name, last_name, gender, orientation,
            bio, birth_date, fame_rating, city, is_online, last_seen
        FROM users WHERE id = %s
    """, (user_id,))
    row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="user not found")
    return dict(row)


async def _is_blocked(conn: AsyncConnection, a: str, b: str) -> bool:
    cursor = await conn.execute("""
        SELECT 1 FROM blocks
        WHERE (blocker_id = %s AND blocked_id = %s)
        OR (blocker_id = %s AND blocked_id = %s)
    """, (a, b, b, a))
    return await cursor.fetchone() is not None


async def _recalculate_fame(conn: AsyncConnection, user_id: str):
    await conn.execute("""
        UPDATE users SET fame_rating = (
            SELECT COUNT(*) FROM likes WHERE liked_id = %s
        ) + (
            SELECT COUNT(*) FROM likes l1
            WHERE l1.liked_id = %s
            AND EXISTS (
                SELECT 1 FROM likes l2
                WHERE l2.liker_id = l1.liked_id AND l2.liked_id = %s
            )
        )
        WHERE id = %s
    """, (user_id, user_id, user_id, user_id))





def _parse_int_param(value: str | None, name: str) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"'{name}' must be an integer")


def _build_orientation_filter(gender: str | None, orientation: str | None) -> tuple[list[str], list]:
    """Return (sql_conditions, params) for gender/orientation compatibility."""
    if orientation == "homo":
        return (
            ["u.gender = %s", "u.orientation = ANY(%s)"],
            [gender, ["homo", "bi"]],
        )
    if orientation == "hetero":
        opposite = {"male": "female", "female": "male"}.get(gender or "")
        if opposite:
            return (
                ["u.gender = %s", "u.orientation = ANY(%s)"],
                [opposite, ["hetero", "bi"]],
            )
        return ["u.orientation = ANY(%s)"], [["hetero", "bi"]]
    # bi or unknown — no gender constraint, but target must be potentially interested
    return [], []


@router.get("/users")
async def browse_users(request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    qp = request.query_params
    page        = max(0, _parse_int_param(qp.get("page"), "page") or 0)
    min_age     = _parse_int_param(qp.get("min_age"), "min_age")
    max_age     = _parse_int_param(qp.get("max_age"), "max_age")
    max_dist    = _parse_int_param(qp.get("max_distance"), "max_distance")
    min_fame    = _parse_int_param(qp.get("min_fame"), "min_fame")
    min_tags    = _parse_int_param(qp.get("min_tags"), "min_tags")

    cursor = await conn.execute(
        "SELECT gender, orientation, latitude, longitude, birth_date FROM users WHERE id = %s",
        (user_id,)
    )
    me = await cursor.fetchone()
    if me is None:
        raise HTTPException(status_code=401, detail="invalid session")
    if me["latitude"] is None or me["longitude"] is None:
        raise HTTPException(status_code=400, detail="set your location first")

    my_age = (date.today() - me["birth_date"]).days // 365 if me["birth_date"] else None
    my_lat, my_lon = me["latitude"], me["longitude"]

    orient_conds, orient_params = _build_orientation_filter(me["gender"], me["orientation"])

    # --- build WHERE ---
    conditions = [
        "u.profile_complete = true",
        "u.verified = true",
        "u.id != %s",
        "u.latitude IS NOT NULL AND u.longitude IS NOT NULL",
        """NOT EXISTS (
            SELECT 1 FROM blocks
            WHERE (blocker_id = %s AND blocked_id = u.id)
            OR (blocker_id = u.id AND blocked_id = %s)
        )""",
    ] + orient_conds

    where_params: list = [user_id, user_id, user_id] + orient_params

    if min_age is not None:
        conditions.append("DATE_PART('year', AGE(u.birth_date)) >= %s")
        where_params.append(min_age)
    if max_age is not None:
        conditions.append("DATE_PART('year', AGE(u.birth_date)) <= %s")
        where_params.append(max_age)
    if max_dist is not None:
        conditions.append(
            "earth_distance(ll_to_earth(u.latitude, u.longitude), ll_to_earth(%s, %s)) / 1000 <= %s"
        )
        where_params.extend([my_lat, my_lon, max_dist])
    if min_fame is not None:
        conditions.append("u.fame_rating >= %s")
        where_params.append(min_fame)
    if min_tags is not None:
        conditions.append("""(
            SELECT COUNT(*) FROM user_tags a
            JOIN user_tags b ON a.tag_id = b.tag_id
            WHERE a.user_id = u.id AND b.user_id = %s
        ) >= %s""")
        where_params.extend([user_id, min_tags])

    where_clause = " AND ".join(conditions)

    # age diff term: embed as literal (my_age comes from the DB, not user input)
    age_term = f"- ABS(DATE_PART('year', AGE(u.birth_date)) - {my_age}) * 1.0" if my_age else ""

    query = f"""
        SELECT
            u.id, u.first_name, u.last_name, u.gender,
            u.bio, u.birth_date, u.fame_rating, u.city, u.is_online, u.last_seen,
            DATE_PART('year', AGE(u.birth_date))::int                                AS age,
            ROUND(earth_distance(
                ll_to_earth(u.latitude, u.longitude),
                ll_to_earth(%s, %s)
            ) / 1000)::int                                                            AS distance_km,
            (SELECT COUNT(*) FROM user_tags a
            JOIN user_tags b ON a.tag_id = b.tag_id
            WHERE a.user_id = u.id AND b.user_id = %s)::int                         AS common_tags,
            (
                (SELECT COUNT(*) FROM user_tags a
                JOIN user_tags b ON a.tag_id = b.tag_id
                WHERE a.user_id = u.id AND b.user_id = %s) * 20
                + u.fame_rating * 0.5
                {age_term}
                - earth_distance(ll_to_earth(u.latitude, u.longitude), ll_to_earth(%s, %s)) / 1000 * 0.1
            )                                                                         AS score,
            (SELECT path FROM photos WHERE user_id = u.id AND is_profile = true LIMIT 1) AS photo
        FROM users u
        WHERE {where_clause}
        ORDER BY score DESC
        LIMIT 20 OFFSET %s
    """

    # params order matches %s appearances in query: SELECT then WHERE then OFFSET
    all_params = [
        my_lat, my_lon,   # distance_km
        user_id,           # common_tags display
        user_id,           # common_tags in score
        my_lat, my_lon,   # distance in score
        *where_params,
        page * 20,
    ]

    cursor = await conn.execute(query, all_params)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.get("/users/{target_id}")
async def get_user_profile(target_id: int, request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    if str(target_id) == str(user_id):
        raise HTTPException(status_code=400, detail="use /profile/me for your own profile")

    if await _is_blocked(conn, user_id, str(target_id)):
        raise HTTPException(status_code=404, detail="user not found")

    profile = await _get_user_or_404(conn, str(target_id))

    cursor = await conn.execute(
        "SELECT position, path, is_profile FROM photos WHERE user_id = %s ORDER BY position",
        (target_id,)
    )
    profile["photos"] = [dict(r) for r in await cursor.fetchall()]

    cursor = await conn.execute("""
        SELECT tags.name FROM tags
        JOIN user_tags ON user_tags.tag_id = tags.id
        WHERE user_tags.user_id = %s
    """, (target_id,))
    profile["tags"] = [r["name"] for r in await cursor.fetchall()]

    cursor = await conn.execute("""
        SELECT
            EXISTS (SELECT 1 FROM likes WHERE liker_id = %s AND liked_id = %s) AS liked_by_me,
            EXISTS (SELECT 1 FROM likes WHERE liker_id = %s AND liked_id = %s) AS liked_by_them
    """, (user_id, target_id, target_id, user_id))
    like_status = await cursor.fetchone()
    profile["is_liked_by_me"] = like_status["liked_by_me"]
    profile["is_match"] = like_status["liked_by_me"] and like_status["liked_by_them"]

    try:
        await conn.execute(
            "INSERT INTO visits (visitor_id, visited_id) VALUES (%s, %s)",
            (user_id, target_id)
        )
        await _notify(conn, str(target_id), user_id, "visit", redis)
        await conn.commit()
    except Exception:
        logger.exception("Failed to record visit from user %s to %s", user_id, target_id)
        await conn.rollback()

    return profile


@router.get("/users/{target_id}/photos/{position}")
async def get_user_photo(target_id: int, position: int, request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    if str(target_id) == str(user_id):
        raise HTTPException(status_code=400, detail="use /profile/photos/{position} for your own photos")

    if position < 1 or position > 5:
        raise HTTPException(status_code=400, detail="invalid position (1-5)")

    if await _is_blocked(conn, user_id, str(target_id)):
        raise HTTPException(status_code=404, detail="user not found")

    cursor = await conn.execute(
        "SELECT path FROM photos WHERE user_id = %s AND position = %s",
        (target_id, position)
    )
    photo = await cursor.fetchone()
    if photo is None:
        raise HTTPException(status_code=404, detail="photo not found")

    if not os.path.isfile(photo["path"]):
        raise HTTPException(status_code=404, detail="photo file missing")

    return FileResponse(photo["path"], media_type="image/jpeg")


@router.post("/users/{target_id}/like")
async def like_user(target_id: int, request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    if str(target_id) == str(user_id):
        raise HTTPException(status_code=400, detail="cannot like yourself")

    if await _is_blocked(conn, user_id, str(target_id)):
        raise HTTPException(status_code=404, detail="user not found")

    cursor = await conn.execute(
        "SELECT 1 FROM users WHERE id = %s", (target_id,)
    )
    if await cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail="user not found")
    
    photo_cursor = await conn.execute(
        "SELECT EXISTS (SELECT 1 FROM photos WHERE user_id = %s AND is_profile = true)", (target_id,)
    )
    has_profile_picture = await photo_cursor.fetchone()

    if not has_profile_picture["exists"]:
        raise HTTPException(status_code=404, detail="can't like a user who doesn't have a profile picture")

    try:
        cursor = await conn.execute(
            "INSERT INTO likes (liker_id, liked_id) VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING id",
            (user_id, target_id)
        )
        already_liked = await cursor.fetchone() is None

        if already_liked:
            return {"message": "already liked"}

        cursor = await conn.execute(
            "SELECT 1 FROM likes WHERE liker_id = %s AND liked_id = %s",
            (target_id, user_id)
        )
        is_match = await cursor.fetchone() is not None

        if is_match:
            await _notify(conn, str(target_id), user_id, "match", redis)
            await _notify(conn, user_id, str(target_id), "match", redis)
            await _recalculate_fame(conn, user_id)
        else:
            await _notify(conn, str(target_id), user_id, "like", redis)

        await _recalculate_fame(conn, str(target_id))
        await conn.commit()
    except Exception:
        logger.exception("Like failed: user %s → target %s", user_id, target_id)
        raise HTTPException(status_code=500, detail="like failed")

    return {"message": "match" if is_match else "liked"}


@router.delete("/users/{target_id}/like")
async def unlike_user(target_id: int, request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    try:
        cursor = await conn.execute(
            "DELETE FROM likes WHERE liker_id = %s AND liked_id = %s RETURNING id",
            (user_id, target_id)
        )
        if await cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="like not found")

        await _notify(conn, str(target_id), user_id, "unlike", redis)
        await _recalculate_fame(conn, str(target_id))
        await conn.commit()
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unlike failed: user %s → target %s", user_id, target_id)
        raise HTTPException(status_code=500, detail="unlike failed")

    return {"message": "unliked"}


@router.post("/users/{target_id}/block")
async def block_user(target_id: int, request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    if str(target_id) == str(user_id):
        raise HTTPException(status_code=400, detail="cannot block yourself")

    cursor = await conn.execute(
        "SELECT 1 FROM users WHERE id = %s", (target_id,)
    )
    if await cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail="user not found")

    try:
        await conn.execute(
            "INSERT INTO blocks (blocker_id, blocked_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (user_id, target_id)
        )
        await conn.execute(
            "DELETE FROM likes WHERE (liker_id = %s AND liked_id = %s) OR (liker_id = %s AND liked_id = %s)",
            (user_id, target_id, target_id, user_id)
        )
        await conn.commit()
    except Exception:
        logger.exception("Block failed: user %s → target %s", user_id, target_id)
        raise HTTPException(status_code=500, detail="block failed")

    return {"message": "user blocked"}


@router.delete("/users/{target_id}/block")
async def unblock_user(target_id: int, request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    try:
        cursor = await conn.execute(
            "DELETE FROM blocks WHERE blocker_id = %s AND blocked_id = %s RETURNING id",
            (user_id, target_id)
        )
        if await cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="block not found")

        await conn.commit()
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unblock failed: user %s → target %s", user_id, target_id)
        raise HTTPException(status_code=500, detail="unblock failed")

    return {"message": "user unblocked"}


@router.post("/users/{target_id}/report")
async def report_user(target_id: int, request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    if str(target_id) == str(user_id):
        raise HTTPException(status_code=400, detail="cannot report yourself")

    body = await require_json(request)
    reason = body.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise HTTPException(status_code=400, detail="reason must be a string")

    cursor = await conn.execute(
        "SELECT 1 FROM users WHERE id = %s", (target_id,)
    )
    if await cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail="user not found")

    try:
        cursor = await conn.execute(
            "INSERT INTO reports (reporter_id, reported_id, reason) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING RETURNING id",
            (user_id, target_id, reason)
        )
        already_reported = await cursor.fetchone() is None
        await conn.commit()
    except Exception:
        logger.exception("Report failed: user %s → target %s", user_id, target_id)
        raise HTTPException(status_code=500, detail="report failed")

    if already_reported:
        return {"message": "already reported"}
    return {"message": "user reported"}
