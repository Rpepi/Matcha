from faker import Faker
import random
import os
from argon2 import PasswordHasher
import psycopg
from psycopg import errors

DATABASE_URL = os.getenv("DATABASE_URL")


fake = Faker('EN_US')
ph = PasswordHasher(
    time_cost=2,
    memory_cost=19456,
    parallelism=1
)


TAGS = [
    "vegan", "geek", "piercing", "tattoo", "sport",
    "music", "travel", "cinema", "cooking", "gaming",
    "yoga", "art", "photography", "reading", "hiking",
    "dancing", "coffee", "wine", "cat", "dog"
]


def generate_user() -> dict:
    user = {
            "username": fake.unique.user_name(),
            "email": fake.unique.email(),
            "first_name": fake.unique.first_name(),
            "last_name": fake.unique.last_name(),
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
