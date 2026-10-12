from faker import Faker
from datetime import datetime, timedelta, timezone
import random
import re
import os
from argon2 import PasswordHasher
import psycopg
from psycopg import errors
from app.matching import is_interested

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL: 
    raise RuntimeError("env variable DATABASE_URL variable is not set")


fake = Faker('EN_US')
ph = PasswordHasher(
    time_cost=2,
    memory_cost=19456,
    parallelism=1
)


TAGS = [
    'travel',
    'coffee',
    'hiking',
    'movies',
    'music',
    'gaming',
    'fitness',
    'foodie',
    'art',
    'photography',
    'dogs',
    'cats',
    'yoga',
    'reading',
    'dancing',
    'cooking',
    'wine',
    'beach',
    'nature',
    'tech'
]


# Seeded users live around a few cities instead of anywhere on Earth, so that
# "same geographic area" means something: most people have neighbours within a
# few dozen km, and the other cities are a believable distance away (Bangkok is
# about 100 km from Pattaya and 580 km from Chiang Mai). Bangkok gets the biggest
# share, like a real user base would.
# Each entry: name, latitude, longitude, relative weight.
CITIES = [
    ("Bangkok", 13.7563, 100.5018, 40),
    ("Chiang Mai", 18.7883, 98.9853, 15),
    ("Phuket", 7.8804, 98.3923, 12),
    ("Pattaya", 12.9236, 100.8825, 8),
    ("Khon Kaen", 16.4419, 102.8360, 8),
    ("Hat Yai", 7.0086, 100.4747, 7),
    ("Nakhon Ratchasima", 14.9799, 102.0977, 6),
    ("Chiang Rai", 19.9105, 99.8406, 4),
]
CITY_SPREAD_DEGREES = 0.15  # about 17 km around the centre
LAST_SEEN_WITHIN_DAYS = 30

# Interactions between seeded users (see plan_likes / seed_interactions).
LIKES_PER_USER = (0, 12)
EXTRA_VISITS_PER_USER = (0, 8)
SAME_CITY_SHARE = 0.75  # how often a like goes to someone of the same city

# Same formula as routes.users._recalculate_fame (likes received + matches), for many users at once.
FAME_SQL = """
    UPDATE users u SET fame_rating = (
        SELECT COUNT(*) FROM likes l WHERE l.liked_id = u.id
    ) + (
        SELECT COUNT(*) FROM likes l1
        WHERE l1.liked_id = u.id
        AND EXISTS (SELECT 1 FROM likes l2 WHERE l2.liker_id = l1.liked_id AND l2.liked_id = l1.liker_id)
    )
    WHERE u.id = ANY(%s)
"""

_NOT_USERNAME_RE = re.compile(r"[^a-z0-9.]")


def make_username(first_name: str, last_name: str) -> str:
    """Build a username like ``eileen.cox`` from a name.

    Only lowercase letters, digits and dots are kept (the rules of
    ``app.validation.clean_username``), cut to the 30 characters of the column.
    The seed's first names are unique, which makes the usernames unique.

    Args:
        first_name: First name of the user.
        last_name: Last name of the user.

    Returns:
        The username.
    """
    return _NOT_USERNAME_RE.sub("", f"{first_name}.{last_name}".lower()).lstrip(".")[:30]


def generate_user() -> dict:
    """Generate the data of one random fake user.

    Returns:
        A mapping of ``users`` column to value: unique email, username and
        names, a hashed random password, a birth date (18 to 60 years old),
        bio, gender, orientation, a city with coordinates near it, and when
        the user was last seen (within the last 30 days, offline).
        ``profile_complete`` and ``verified`` are already True.
    """
    gender = random.choice(["male", "female", "other"])
    # A first name that goes with the gender ("other" takes any).
    first_name = {
        "male": fake.unique.first_name_male,
        "female": fake.unique.first_name_female,
    }.get(gender, fake.unique.first_name)()
    last_name = fake.unique.last_name()
    city, latitude, longitude, _ = random.choices(CITIES, weights=[c[3] for c in CITIES])[0]
    last_seen = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
        minutes=random.randint(5, LAST_SEEN_WITHIN_DAYS * 24 * 60)
    )
    user = {
            "email": fake.unique.email(),
            "username": make_username(first_name, last_name),
            "first_name": first_name,
            "last_name": last_name,
            "password_hash": ph.hash(fake.unique.password()),
            "birth_date": fake.unique.date_of_birth(minimum_age=18, maximum_age=60),
            "bio": fake.unique.text(max_nb_chars=200),
            "gender": gender,
            "orientation": random.choice(["hetero", "homo", "bi"]),
            "city": city,
            "latitude": latitude + random.uniform(-CITY_SPREAD_DEGREES, CITY_SPREAD_DEGREES),
            "longitude": longitude + random.uniform(-CITY_SPREAD_DEGREES, CITY_SPREAD_DEGREES),
            "last_seen": last_seen,
            "profile_complete": True,
            "verified": True
        }
    return user


def plan_likes(profiles: list[dict], rng: random.Random) -> list[tuple[int, int]]:
    """Choose who likes whom among the seeded profiles.

    Each person likes between ``LIKES_PER_USER`` people they could be
    interested in (``app.matching.is_interested``), mostly in their own city.
    Everyone gets an "appeal" drawn from a long-tailed distribution and is
    picked in proportion to it, so, like on a real app, a few profiles collect
    many likes and most collect a handful: the fame ratings come out spread
    instead of all at zero. Likes in both directions are matches.

    Args:
        profiles: Dicts with ``id``, ``gender``, ``orientation`` and ``city``.
        rng: Random generator (seeded in tests).

    Returns:
        Distinct ``(liker_id, liked_id)`` pairs, never someone liking themself.
    """
    appeal = {p["id"]: rng.paretovariate(1.5) for p in profiles}
    likes: set[tuple[int, int]] = set()
    for person in profiles:
        candidates = [
            other for other in profiles
            if other["id"] != person["id"] and is_interested(person["orientation"], person["gender"], other["gender"])
        ]
        neighbours = [other for other in candidates if other["city"] == person["city"]]
        for _ in range(rng.randint(*LIKES_PER_USER)):
            pool = neighbours if neighbours and rng.random() < SAME_CITY_SHARE else candidates
            if not pool:
                break
            liked = rng.choices(pool, weights=[appeal[other["id"]] for other in pool])[0]
            likes.add((person["id"], liked["id"]))
    return sorted(likes)


def seed_interactions(conn, user_ids: list[int], rng: random.Random | None = None):
    """Give the seeded users likes, visits and the fame rating that follows.

    Every like comes with a visit a little before it, and everyone also
    visits a few profiles they did not like. Dates fall within the last 30
    days. The fame rating is then computed with the app's own formula (likes
    received + matches, see ``routes.users._recalculate_fame``). No
    notification is created: nobody logs in as a seeded user.

    Args:
        conn: Synchronous database connection; committed at the end.
        user_ids: Ids of the users just created.
        rng: Random generator; a fresh one when None.
    """
    rng = rng or random.Random()
    rows = conn.execute(
        "SELECT id, gender, orientation, city FROM users WHERE id = ANY(%s)", (user_ids,)
    ).fetchall()
    profiles = [{"id": r[0], "gender": r[1], "orientation": r[2], "city": r[3]} for r in rows]
    likes = plan_likes(profiles, rng)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    def some_time_ago() -> datetime:
        return now - timedelta(minutes=rng.randint(60, LAST_SEEN_WITHIN_DAYS * 24 * 60))

    visits, like_rows = {}, []
    for liker, liked in likes:
        liked_at = some_time_ago()
        visits[(liker, liked)] = liked_at - timedelta(minutes=rng.randint(1, 30))
        like_rows.append((liker, liked, liked_at))
    ids = [p["id"] for p in profiles]
    for visitor in ids:
        for visited in rng.sample(ids, min(len(ids), rng.randint(*EXTRA_VISITS_PER_USER))):
            if visited != visitor:
                visits.setdefault((visitor, visited), some_time_ago())

    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO visits (visitor_id, visited_id, created_at) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            [(visitor, visited, at) for (visitor, visited), at in visits.items()],
        )
        cur.executemany(
            "INSERT INTO likes (liker_id, liked_id, created_at) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            like_rows,
        )
    conn.execute(FAME_SQL, (ids,))
    conn.commit()
    like_set = set(likes)
    matches = sum(1 for liker, liked in likes if (liked, liker) in like_set) // 2
    print(f"  {len(like_rows)} likes ({matches} matches) and {len(visits)} visits created")


def seed():
    """Insert 500 fake users, each with 1 to 5 random tags, then their likes and visits.

    Missing tags are created on the fly and each user is committed on its
    own. Progress is printed every 100 users. A user that fails to insert is
    reported and rolled back without stopping the run, so fewer than 500 rows
    may end up in the database. The likes and visits between the users
    created (see ``seed_interactions``) come last. Uses a synchronous
    connection built from ``DATABASE_URL``.
    """
    conn = psycopg.connect(DATABASE_URL)
    created: list[int] = []
    for i in range(500):
        try:
            user = generate_user()
            columns = list(user.keys())
            values = list(user.values())

            placeholders = ", ".join(["%s"] * len(values))
            query = f"INSERT INTO users ({', '.join(columns)}) VALUES ({placeholders}) RETURNING id"
            row =conn.execute(query, values).fetchone()
            user_id = row[0]
            created.append(user_id)

            # Assign 1-5 random tags
            user_tags = random.sample(TAGS, random.randint(1, 5))
            for tag_name in user_tags:
                # Insert tag if it doesn't exist
                conn.execute(
                    "INSERT INTO tags (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                    (tag_name,)
                )
                tag = conn.execute(
                    "SELECT id FROM tags WHERE name = %s",
                    (tag_name,)
                ).fetchone()
                conn.execute(
                    "INSERT INTO user_tags (user_id, tag_id) VALUES (%s, %s)",
                    (user_id, tag[0])
                )

            conn.commit()
            if (i + 1) % 100 == 0:
                print(f"  {i + 1}/500 users created")

        except errors.UniqueViolation as e:
            conn.rollback()
            print("ERROR: ", e)
        except errors.SyntaxError as e:
            conn.rollback()
            print("ERROR:", e)
        except psycopg.Error as e:
            conn.rollback()
            print("ERROR:", e)
        except Exception as e:
            conn.rollback()
            print(f"ERROR: ", e)

    print(f"Done. {len(created)} users seeded.")
    seed_interactions(conn, created)


if __name__ == "__main__":
    seed()
