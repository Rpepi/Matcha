from faker import Faker
from datetime import datetime, timedelta, timezone
import random
import re
import os
from argon2 import PasswordHasher
import psycopg
from psycopg import errors

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
    first_name = fake.unique.first_name()
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
            "gender": random.choice(["male", "female", "other"]),
            "orientation": random.choice(["hetero", "homo", "bi"]),
            "city": city,
            "latitude": latitude + random.uniform(-CITY_SPREAD_DEGREES, CITY_SPREAD_DEGREES),
            "longitude": longitude + random.uniform(-CITY_SPREAD_DEGREES, CITY_SPREAD_DEGREES),
            "last_seen": last_seen,
            "profile_complete": True,
            "verified": True
        }
    return user


def seed():
    """Insert 500 fake users, each with 1 to 5 random tags.

    Missing tags are created on the fly and each user is committed on its
    own. Progress is printed every 100 users. A user that fails to insert is
    reported and rolled back without stopping the run, so fewer than 500 rows
    may end up in the database. Uses a synchronous connection built from
    ``DATABASE_URL``.
    """
    conn = psycopg.connect(DATABASE_URL)
    for i in range(500):
        try:
            user = generate_user()
            columns = list(user.keys())
            values = list(user.values())

            placeholders = ", ".join(["%s"] * len(values))
            query = f"INSERT INTO users ({', '.join(columns)}) VALUES ({placeholders}) RETURNING id"
            row =conn.execute(query, values).fetchone()
            user_id = row[0]

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
            if i+1 == 500:
                print("Done. 500 users seeded.")

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


if __name__ == "__main__":
    seed()
