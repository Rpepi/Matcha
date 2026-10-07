import re
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from psycopg.errors import UniqueViolation

from app.usernames import username_base, generate_username, is_username_conflict
from app.validation import clean_username


def make_conn(*taken_flags):
    """A connection whose successive username lookups say taken (True) or free (False)."""
    cursors = []
    for taken in taken_flags:
        cursor = AsyncMock()
        cursor.fetchone = AsyncMock(return_value={"?column?": 1} if taken else None)
        cursors.append(cursor)
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=cursors)
    return conn


class TestUsernameBase:
    @pytest.mark.parametrize("first_name, expected", [
        ("Alice", "alice"),
        ("José", "jose"),
        ("Anne-Marie", "annemarie"),
        ("O'Brien", "obrien"),
        ("Zoë Élise", "zoeelise"),
        ("A" * 50, "a" * 20),
    ])
    def test_keeps_only_lowercase_ascii_letters_and_digits(self, first_name, expected):
        assert username_base(first_name) == expected

    @pytest.mark.parametrize("first_name", ["李雷", "!!!", "   ", ""])
    def test_falls_back_when_nothing_usable_is_left(self, first_name):
        assert username_base(first_name) == "user"


class TestGenerateUsername:
    async def test_returns_the_base_with_four_digits(self):
        username = await generate_username(make_conn(False), "Alice")
        assert re.fullmatch(r"alice[0-9]{4}", username)

    async def test_the_result_is_a_valid_username(self):
        for first_name in ("Alice", "José", "李雷", "A" * 50):
            username = await generate_username(make_conn(False), first_name)
            assert clean_username(username) == username

    async def test_looks_the_candidate_up_case_insensitively(self):
        conn = make_conn(False)
        username = await generate_username(conn, "Alice")
        query, params = conn.execute.await_args.args
        assert "lower(username) = lower(%s)" in query
        assert params == (username,)

    async def test_tries_again_when_the_candidate_is_taken(self):
        conn = make_conn(True, True, False)
        username = await generate_username(conn, "Alice")
        assert conn.execute.await_count == 3
        assert re.fullmatch(r"alice[0-9]{4}", username)

    async def test_widens_the_suffix_after_ten_collisions(self):
        conn = make_conn(*([True] * 10))
        username = await generate_username(conn, "Alice")
        assert conn.execute.await_count == 10
        assert re.fullmatch(r"alice[0-9a-f]{8}", username)
        assert clean_username(username) == username


class TestIsUsernameConflict:
    @staticmethod
    def violation(constraint_name):
        return SimpleNamespace(diag=SimpleNamespace(constraint_name=constraint_name))

    def test_username_constraint(self):
        assert is_username_conflict(self.violation("users_username_lower_key")) is True

    def test_email_constraint(self):
        assert is_username_conflict(self.violation("users_email_key")) is False

    def test_unknown_constraint_is_not_a_username_conflict(self):
        assert is_username_conflict(self.violation(None)) is False

    def test_works_on_a_bare_psycopg_error(self):
        assert is_username_conflict(UniqueViolation("duplicate key")) is False
