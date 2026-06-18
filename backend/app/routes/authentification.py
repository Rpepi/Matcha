from fastapi import APIRouter, Depends, Response, Request, HTTPException
from psycopg import AsyncConnection
from psycopg.errors import UniqueViolation
from itsdangerous import SignatureExpired, BadSignature
from datetime import date
import redis.asyncio as redis
from app.db.dependencies import get_db
from app.cache.dependencies import get_redis
from app.security.session import create_session
from app.security.passwords import hash_password, verify_password, ph, is_password_valid
from app.security.token import generate_verification_token, send_verification_email, send_reset_email, serializer
from app.utils import require_json
from app.log import get_logger

logger = get_logger(__name__)

router = APIRouter()


DUMMY_HASH = ph.hash("dummy")


async def authenticate_user(username: str, password: str, conn: AsyncConnection) -> tuple:
    cursor = await conn.execute(
        "SELECT id, password_hash, verified, profile_complete FROM users WHERE username = %s", (username,)
    )
    row = await cursor.fetchone()
    hash_to_check = row["password_hash"] if row else DUMMY_HASH  #cannot now if an account exist mesuring the execution time.
    password_ok = await verify_password(hash_to_check, password)
    if row is None or not password_ok:
        logger.warning("Failed login attempt for username '%s'", username)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not row["verified"]:
        raise HTTPException(status_code=403, detail="Email not verified")
    return str(row["id"]), row["profile_complete"]


@router.post("/auth/login")
async def login(request: Request, response: Response, redis: redis.Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):
    
    body = await require_json(request) # will raise exception if not json format

    try:
        username = body["username"]
        password = body["password"]
    except Exception:
        raise HTTPException(status_code=400, detail="Username and password are required")
    if not isinstance(username, str) or not isinstance(password, str):
        raise HTTPException(status_code=400, detail="Username and password must be strings")
    user_id, profile_complete = await authenticate_user(username, password, conn)
    await create_session(response, user_id, redis)
    logger.info("User %s logged in", user_id)
    return {
        "id": user_id,
        "username": username,
        "profile_complete": profile_complete,
    }


@router.post("/auth/logout")
async def logout(request: Request, response: Response, redis: redis.Redis = Depends(get_redis)):
    cookie = request.cookies.get("session")
    if cookie and "$" in cookie:
        session_id = cookie.split("$")[0]
        await redis.delete("session:" + session_id)
    response.delete_cookie(key="session")
    return {"message": "Logged out"}


@router.post("/auth/forgot-password")
async def forgot_password(request: Request, conn: AsyncConnection = Depends(get_db)):
    
    body = await require_json(request)

    try:
        email = body["email"]
    except Exception:
        raise HTTPException(status_code=400, detail="Email is required")
    if not isinstance(email, str):
        raise HTTPException(status_code=400, detail="Email must be a string")

    cursor = await conn.execute("SELECT id FROM users WHERE email = %s", (email,))
    row = await cursor.fetchone()
    if row:
        token = serializer.dumps(str(row["id"]), salt="password-reset")
        send_reset_email(email, token)
    return {"message": "If this email exists, a reset link has been sent"}


@router.post("/auth/reset-password")
async def reset_password(request: Request, redis: redis.Redis = Depends(get_redis), conn: AsyncConnection = Depends(get_db)):

    body = await require_json(request)

    try:
        token = body["token"]
        new_password = body["new_password"]
    except Exception:
        raise HTTPException(status_code=400, detail="Token and new_password are required")
    if not isinstance(token, str) or not isinstance(new_password, str):
        raise HTTPException(status_code=400, detail="Fields must be strings")
    if not is_password_valid(new_password):
        raise HTTPException(status_code=400, detail="Password too weak or too common")

    try:
        user_id = serializer.loads(token, salt="password-reset", max_age=1800)
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="Reset link has expired")
    except BadSignature:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    redis_key = f"used_reset:{token}"
    if await redis.get(redis_key):
        raise HTTPException(status_code=400, detail="Reset link has already been used")
    await redis.set(redis_key, 1, ex=1800)

    new_hash = await hash_password(new_password)
    await conn.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user_id))
    await conn.commit()
    return {"message": "Password updated. You can now log in."}


@router.post("/auth/register")
async def register(request: Request, response: Response, conn: AsyncConnection = Depends(get_db)):

    body = await require_json(request)
    
    try:
        username = body["username"]
        password = body["password"]
        email = body["email"]
        first_name = body["first_name"]
        last_name = body["last_name"]
        gender = body["gender"]
        orientation = body.get("orientation")
        bio = body.get("bio")
        birth_date = body["birth_date"]
        latitude = body.get("latitude")
        longitude = body.get("longitude")
        city = body.get("city")
    except Exception:
        raise HTTPException(status_code=400, detail="Required Fields are empty")

    if not all(isinstance(body.get(f), str) for f in ["username", "password", "email", "first_name", "last_name", "gender", "birth_date"]):
        raise HTTPException(status_code=400, detail="Required fields must be strings")
    if orientation is not None and not isinstance(orientation, str):
        raise HTTPException(status_code=400, detail="orientation must be a string")
    if bio is not None and not isinstance(bio, str):
        raise HTTPException(status_code=400, detail="bio must be a string")
    
    has_gps = latitude is not None and longitude is not None
    has_city = city is not None   
    if not has_gps and not has_city:
        raise HTTPException(status_code=400, detail="Location is required: provide GPS coordinates or a city")
    if has_gps:
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            raise HTTPException(status_code=400, detail="latitude and longitude must be numbers")
        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            raise HTTPException(status_code=400, detail="Invalid GPS coordinates")
    if has_city and not isinstance(city, str):
        raise HTTPException(status_code=400, detail="city must be a string")
    
    try:
        birth_date = date.fromisoformat(birth_date)  #"YYYY-MM-DD"
    except ValueError:
        raise HTTPException(status_code=400, detail="birth_date must be YYYY-MM-DD")
    
    fields = {
        "username": username,       #required
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "password_hash": await hash_password(password),
        "gender": gender,
        "birth_date": birth_date,
    }

    if orientation is not None:
        fields["orientation"] = orientation
    if bio is not None:
        fields["bio"] = bio
    if latitude is not None:
        fields["latitude"] = latitude
    if longitude is not None:
        fields["longitude"] = longitude
    if city is not None:
        fields["city"] = city
    
    columns = ", ".join(fields.keys())
    placeholders = ", ".join(["%s"] * len(fields))
    try:
        cursor = await conn.execute(f"INSERT INTO users ({columns}) VALUES ({placeholders}) RETURNING id", list(fields.values()))
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="Username or email already taken")
    row = await cursor.fetchone()
    user_id = row["id"]
    await conn.commit()
    logger.info("New account registered: username='%s' id=%s", username, user_id)
    token = generate_verification_token(str(user_id))
    send_verification_email(email, token)
    return {"message": "Account created. Check your email to verify your account."}


@router.get("/auth/verify")
async def verify_email(request: Request, conn: AsyncConnection = Depends(get_db)):
    token = request.query_params.get("token")
    if not token:   
        raise HTTPException(status_code=400, detail="Missing token")
    try:
        user_id = serializer.loads(token, salt="email-verify", max_age=3600)  # expire après 1h
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="Verification link has expired")
    except BadSignature:
        raise HTTPException(status_code=400, detail="Invalid verification token")

    await conn.execute("UPDATE users SET verified = true WHERE id = %s", (user_id,))
    await conn.commit()
    return {"message": "Email verified. You can now log in."}
