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
from app.security.rate_limit import rate_limit
from app.utils import require_json
from app.validation import clean_str, parse_int_param, valid_target_id, MAX_REASON
from app.log import get_logger
from app.routes.notifications import insert_notification, publish_notification
from app.routes.chat import publish_unmatch


logger = get_logger(__name__)

router = APIRouter()


async def _get_user_or_404(conn: AsyncConnection, user_id: str) -> dict:
    """Fetch the public columns of a user.

    Args:
        conn: Database connection.
        user_id: Id of the user to fetch.

    Returns:
        A dict with ``id``, ``first_name``, ``last_name``, ``gender``,
        ``orientation``, ``bio``, ``birth_date``, ``fame_rating``, ``city``,
        ``is_online`` and ``last_seen``.

    Raises:
        HTTPException: 404 if the user does not exist.
    """
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
    """Check whether a block exists between two users, in either direction.

    Args:
        conn: Database connection.
        a: Id of the first user.
        b: Id of the second user.

    Returns:
        True if a blocked b or b blocked a.
    """
    cursor = await conn.execute("""
        SELECT 1 FROM blocks
        WHERE (blocker_id = %s AND blocked_id = %s)
        OR (blocker_id = %s AND blocked_id = %s)
    """, (a, b, b, a))
    return await cursor.fetchone() is not None


async def _recalculate_fame(conn: AsyncConnection, user_id: str):
    """Recompute and store a user's fame rating.

    The rating is the number of likes received plus the number of those
    likes that are reciprocated (matches). Does not commit.

    Args:
        conn: Database connection.
        user_id: Id of the user whose rating is rewritten.
    """
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





def _build_orientation_filter(gender: str | None, orientation: str | None) -> tuple[list[str], list]:
    """Build the SQL conditions restricting candidates by gender/orientation.

    A "homo" user only sees users of the same gender who are "homo" or
    "bi". A "hetero" user only sees users of the opposite gender (male or
    female) who are "hetero" or "bi"; with any other gender only the
    orientation is constrained. "bi" or unknown orientations add no
    condition.

    Args:
        gender: Gender of the current user.
        orientation: Orientation of the current user.

    Returns:
        A tuple ``(sql_conditions, params)``: SQL fragments using the ``u``
        alias of the ``users`` table with ``%s`` placeholders, and the
        matching parameter values. Both lists are empty when nothing is
        restricted.
    """
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


@router.get("/users", dependencies=[Depends(rate_limit("browse", limit=30, seconds=60, burst=10, by="account"))])
async def browse_users(request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """List suggested profiles for the current user.

    Candidates are verified users with a complete profile and a location,
    excluding the user themself, blocked users (both directions) and users
    not compatible with the orientation rules. They are ranked by a score
    combining shared tags (x20), fame (x0.5), age closeness and distance
    (x0.1 per km), best first, 20 per page. The current user must have set
    their location.

    Args:
        request: Incoming request with the ``session`` cookie and optional
            integer query parameters ``page`` (0-based), ``min_age``,
            ``max_age``, ``max_distance`` (km), ``min_fame`` and ``min_tags``
            (minimum number of tags in common).
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        A list of dicts with ``id``, ``first_name``, ``last_name``,
        ``gender``, ``bio``, ``birth_date``, ``fame_rating``, ``city``,
        ``is_online``, ``last_seen``, ``age``, ``distance_km``,
        ``common_tags``, ``score`` and ``photo``.

    Raises:
        HTTPException: 400 if a query parameter is not an integer or is out
            of range (``page`` 0-10000, ``min_age``/``max_age`` 16-120,
            ``max_distance`` 0-40000, ``min_fame`` 0-1000000, ``min_tags``
            0-5) or the user's location is not set; 401 if the session is
            missing or invalid.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    qp = request.query_params
    page        = parse_int_param(qp.get("page"), "page", 0, 10_000) or 0
    min_age     = parse_int_param(qp.get("min_age"), "min_age", 16, 120)
    max_age     = parse_int_param(qp.get("max_age"), "max_age", 16, 120)
    max_dist    = parse_int_param(qp.get("max_distance"), "max_distance", 0, 40_000)
    min_fame    = parse_int_param(qp.get("min_fame"), "min_fame", 0, 1_000_000)
    min_tags    = parse_int_param(qp.get("min_tags"), "min_tags", 0, 5)

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


@router.get("/users/{target_id}", dependencies=[Depends(valid_target_id)])
async def get_user_profile(target_id: int, request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Return another user's profile and record the visit.

    Side effect: upserts a row in ``visits`` keyed on ``(visitor_id,
    visited_id)`` (see the ``UNIQUE`` constraint in migration 006) and
    sends a "visit" notification to the viewed user — but only when that
    upsert actually changes the row, i.e. on the first visit ever, or the
    first one after the previous visit is more than 15 days old. Repeat
    views inside that window are silently skipped: no new row, no
    notification. If the upsert fails, the error is logged and rolled
    back, and the profile is still returned.

    Args:
        target_id: Id of the user to view.
        request: Incoming request, carrying the ``session`` cookie.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        The public fields of the user (see ``_get_user_or_404``) plus
        ``photos``, ``tags``, ``is_liked_by_me`` and ``is_match``.

    Raises:
        HTTPException: 400 if ``target_id`` is the current user; 401 if not
            authenticated; 404 if the user does not exist or a block exists
            between the two users.
    """
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
        cursor = await conn.execute("""
            INSERT INTO visits (visitor_id, visited_id, created_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (visitor_id, visited_id)
            DO UPDATE SET created_at = NOW()
            WHERE visits.created_at < NOW() - INTERVAL '15 days'
            RETURNING id
        """,
            (user_id, target_id)
        )
        row = await cursor.fetchone()
        if row:
            await insert_notification(conn, str(target_id), user_id, "visit")
        await conn.commit()
        if row:
            await publish_notification(str(target_id), user_id, "visit", redis)
    except Exception:
        logger.exception("Failed to record visit from user %s to %s", user_id, target_id)
        await conn.rollback()

    return profile


@router.get("/users/{target_id}/photos/{position}", dependencies=[Depends(valid_target_id)])
async def get_user_photo(target_id: int, position: int, request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Serve another user's photo as a JPEG.

    Args:
        target_id: Id of the photo's owner.
        position: Photo position, from 1 to 5.
        request: Incoming request, carrying the ``session`` cookie.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        The image file.

    Raises:
        HTTPException: 400 if ``target_id`` is the current user or the
            position is out of range; 401 if not authenticated; 404 if a
            block exists, there is no photo at that position, or the file
            is missing on disk.
    """
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


@router.post("/users/{target_id}/like", dependencies=[Depends(valid_target_id), Depends(rate_limit("like", limit=20, seconds=60, burst=5, by="account"))])
async def like_user(target_id: int, request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Like a user, creating a match if the like is reciprocated.

    Liking again is harmless and returns "already liked". A new like
    notifies the target with "like", or both users with "match" when the
    target already liked back. Fame ratings are recalculated in the same
    transaction.

    Args:
        target_id: Id of the user to like.
        request: Incoming request, carrying the ``session`` cookie.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        ``{"message": "liked" | "match" | "already liked"}``.

    Raises:
        HTTPException: 400 if ``target_id`` is the current user; 401 if not
            authenticated; 404 if the user does not exist, a block exists,
            or the target has no profile picture; 500 if the like fails.
    """
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
            await insert_notification(conn, str(target_id), user_id, "match")
            await insert_notification(conn, user_id, str(target_id), "match")
            await _recalculate_fame(conn, user_id)
            await _recalculate_fame(conn, str(target_id))
            await conn.commit()
            await publish_notification(str(target_id), user_id, "match", redis)
            await publish_notification(str(user_id), target_id, "match", redis)
        else:
            await insert_notification(conn, str(target_id), user_id, "like")
            await _recalculate_fame(conn, str(target_id))
            await conn.commit()
            await publish_notification(str(target_id), user_id, "like", redis)

    except Exception:
        logger.exception("Like failed: user %s → target %s", user_id, target_id)
        raise HTTPException(status_code=500, detail="like failed")

    return {"message": "match" if is_match else "liked"}


@router.delete("/users/{target_id}/like", dependencies=[Depends(valid_target_id), Depends(rate_limit("like", limit=20, seconds=60, burst=5, by="account"))])
async def unlike_user(target_id: int, request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Remove the current user's like on another user.

    Notifies the target with "unlike" and recalculates their fame rating.
    Also publishes an "unmatch" event on their chat room's Redis channel
    (see ``routes/chat.py::publish_unmatch``), closing any open chat
    websocket between the two.

    Args:
        target_id: Id of the user whose like is removed.
        request: Incoming request, carrying the ``session`` cookie.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        ``{"message": "unliked"}``.

    Raises:
        HTTPException: 401 if not authenticated; 404 if there was no like
            to remove; 500 if the operation fails.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    try:
        cursor = await conn.execute(
            "DELETE FROM likes WHERE liker_id = %s AND liked_id = %s RETURNING id",
            (user_id, target_id)
        )
        if await cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="like not found")

        await insert_notification(conn, str(target_id), user_id, "unlike")
        await _recalculate_fame(conn, str(target_id))
        await conn.commit()
        await publish_notification(str(target_id), user_id, "unlike", redis)
        await publish_unmatch(user_id, target_id, redis)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unlike failed: user %s → target %s", user_id, target_id)
        raise HTTPException(status_code=500, detail="unlike failed")

    return {"message": "unliked"}


@router.post("/users/{target_id}/block", dependencies=[Depends(valid_target_id), Depends(rate_limit("block", limit=10, seconds=60, by="account"))])
async def block_user(target_id: int, request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Block a user.

    Records the block (blocking twice is harmless) and deletes any like
    between the two users in both directions, which also ends a match.
    Publishes an "unmatch" event on their chat room's Redis channel (see
    ``routes/chat.py::publish_unmatch``), closing any open chat websocket
    between the two.

    Args:
        target_id: Id of the user to block.
        request: Incoming request, carrying the ``session`` cookie.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        ``{"message": "user blocked"}``.

    Raises:
        HTTPException: 400 if ``target_id`` is the current user; 401 if not
            authenticated; 404 if the user does not exist; 500 if the block
            fails.
    """
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
        await publish_unmatch(user_id, target_id, redis)
    except Exception:
        logger.exception("Block failed: user %s → target %s", user_id, target_id)
        raise HTTPException(status_code=500, detail="block failed")

    return {"message": "user blocked"}


@router.delete("/users/{target_id}/block", dependencies=[Depends(valid_target_id), Depends(rate_limit("block", limit=10, seconds=60, by="account"))])
async def unblock_user(target_id: int, request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Remove a block placed by the current user.

    The likes deleted when the block was created are not restored.

    Args:
        target_id: Id of the user to unblock.
        request: Incoming request, carrying the ``session`` cookie.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        ``{"message": "user unblocked"}``.

    Raises:
        HTTPException: 401 if not authenticated; 404 if the user was not
            blocked; 500 if the operation fails.
    """
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


@router.post("/users/{target_id}/report", dependencies=[Depends(valid_target_id), Depends(rate_limit("report", limit=5, seconds=3600, by="account"))])
async def report_user(target_id: int, request: Request, redis: Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    """Report a user for abuse.

    Expects a JSON body with an optional string ``reason`` (max 500
    characters, control characters other than newlines refused). Each user can
    report another user only once; repeating returns "already reported".

    Args:
        target_id: Id of the user to report.
        request: Incoming request with the ``session`` cookie and JSON body.
        redis: Redis client (injected dependency).
        conn: Database connection (injected dependency).

    Returns:
        ``{"message": "user reported" | "already reported"}``.

    Raises:
        HTTPException: 400 if ``target_id`` is the current user or
            ``reason`` is not a string; 401 if not authenticated; 404 if
            the user does not exist; 500 if the report fails.
    """
    user_id = await get_current_user_id(request.cookies.get("session"), redis)

    if str(target_id) == str(user_id):
        raise HTTPException(status_code=400, detail="cannot report yourself")

    body = await require_json(request)
    reason = clean_str(body.get("reason"), "reason", MAX_REASON, min_len=0, multiline=True, nullable=True)

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
