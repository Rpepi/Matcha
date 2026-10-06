from faker import Faker
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
        A mapping of ``users`` column to value: unique email, username and names, a
        hashed random password, a birth date (18 to 60 years old), bio,
        gender, orientation and coordinates. ``profile_complete`` and
        ``verified`` are already True.
    """
    first_name = fake.unique.first_name()
    last_name = fake.unique.last_name()
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
            "latitude": fake.unique.latitude(),
            "longitude": fake.unique.longitude(),
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
