import pytest
from datetime import date
from unittest.mock import MagicMock, patch, call
from psycopg import errors as psycopg_errors
from app.seed import generate_user, TAGS


REQUIRED_KEYS = {
    "email", "first_name", "last_name",
    "password_hash", "birth_date", "bio",
    "gender", "orientation",
    "latitude", "longitude",
    "profile_complete", "verified",
}

VALID_GENDERS = {"male", "female", "other"}
VALID_ORIENTATIONS = {"hetero", "homo", "bi"}


class TestGenerateUser:
    def test_contains_all_required_fields(self):
        user = generate_user()
        assert REQUIRED_KEYS.issubset(user.keys())

    def test_password_is_argon2_hash(self):
        user = generate_user()
        assert user["password_hash"].startswith("$argon2")

    def test_user_is_at_least_18(self):
        user = generate_user()
        age = (date.today() - user["birth_date"]).days / 365.25
        assert age >= 18

    def test_user_is_at_most_60(self):
        user = generate_user()
        age = (date.today() - user["birth_date"]).days / 365.25
        assert age <= 61

    def test_gender_is_valid(self):
        user = generate_user()
        assert user["gender"] in VALID_GENDERS

    def test_orientation_is_valid(self):
        user = generate_user()
        assert user["orientation"] in VALID_ORIENTATIONS

    def test_latitude_in_valid_range(self):
        user = generate_user()
        assert -90 <= float(user["latitude"]) <= 90

    def test_longitude_in_valid_range(self):
        user = generate_user()
        assert -180 <= float(user["longitude"]) <= 180

    def test_profile_complete_is_true(self):
        user = generate_user()
        assert user["profile_complete"] is True

    def test_verified_is_true(self):
        user = generate_user()
        assert user["verified"] is True

    def test_bio_is_non_empty_string(self):
        user = generate_user()
        assert isinstance(user["bio"], str)
        assert len(user["bio"]) > 0

    def test_two_users_have_different_emails(self):
        u1 = generate_user()
        u2 = generate_user()
        assert u1["email"] != u2["email"]


# ── seed() function ───────────────────────────────────────────────────────────

from datetime import date as _date


def _fake_user(n: int) -> dict:
    return {
        "email": f"user{n}@test.com",
        "first_name": "A", "last_name": "B",
        "password_hash": "$argon2id$v=19$m=19456,t=2,p=1$fake",
        "birth_date": _date(1990, 1, 1), "bio": "bio",
        "gender": "male", "orientation": "bi",
        "latitude": 48.8, "longitude": 2.3,
        "profile_complete": True, "verified": True,
    }


def _make_conn(user_id=1, tag_id=10):
    conn = MagicMock()

    def execute_side_effect(sql, params=None):
        cursor = MagicMock()
        if "RETURNING id" in sql:
            cursor.fetchone.return_value = (user_id,)
        elif "SELECT id FROM tags" in sql:
            cursor.fetchone.return_value = (tag_id,)
        else:
            cursor.fetchone.return_value = None
        return cursor

    conn.execute.side_effect = execute_side_effect
    conn.commit = MagicMock()
    conn.rollback = MagicMock()
    return conn


class TestSeed:
    def test_seed_inserts_500_users(self):
        from app.seed import seed
        conn = _make_conn()
        fake_users = [_fake_user(i) for i in range(500)]

        with patch("psycopg.connect", return_value=conn), \
             patch("app.seed.generate_user", side_effect=fake_users), \
             patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}):
            seed()

        insert_calls = [c for c in conn.execute.call_args_list if "INSERT INTO users" in str(c)]
        assert len(insert_calls) == 500

    def test_seed_assigns_tags_to_each_user(self):
        from app.seed import seed
        conn = _make_conn()
        fake_users = [_fake_user(i) for i in range(500)]

        with patch("psycopg.connect", return_value=conn), \
             patch("app.seed.generate_user", side_effect=fake_users), \
             patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}):
            seed()

        tag_inserts = [c for c in conn.execute.call_args_list if "INSERT INTO user_tags" in str(c)]
        assert len(tag_inserts) >= 500

    def test_seed_commits_after_each_user(self):
        from app.seed import seed
        conn = _make_conn()
        fake_users = [_fake_user(i) for i in range(500)]

        with patch("psycopg.connect", return_value=conn), \
             patch("app.seed.generate_user", side_effect=fake_users), \
             patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}):
            seed()

        assert conn.commit.call_count == 500

    def test_seed_rolls_back_and_continues_on_unique_violation(self):
        from app.seed import seed
        conn = MagicMock()
        call_count = [0]

        def execute_side_effect(sql, params=None):
            cursor = MagicMock()
            call_count[0] += 1
            if "INSERT INTO users" in sql and call_count[0] == 1:
                raise psycopg_errors.UniqueViolation("duplicate key")
            if "RETURNING id" in sql:
                cursor.fetchone.return_value = (1,)
            elif "SELECT id FROM tags" in sql:
                cursor.fetchone.return_value = (1,)
            return cursor

        conn.execute.side_effect = execute_side_effect
        conn.commit = MagicMock()
        conn.rollback = MagicMock()
        fake_users = [_fake_user(i) for i in range(500)]

        with patch("psycopg.connect", return_value=conn), \
             patch("app.seed.generate_user", side_effect=fake_users), \
             patch.dict("os.environ", {"DATABASE_URL": "postgresql://test"}):
            seed()

        conn.rollback.assert_called()

    def test_tags_constant_contains_expected_entries(self):
        assert "vegan" in TAGS
        assert "geek" in TAGS
        assert len(TAGS) >= 10
