import pytest
from fastapi import HTTPException

from app.validation import (
    clean_str, clean_email, clean_username, clean_choice, clean_int, clean_float,
    parse_int_param, valid_target_id, GENDERS, MAX_ID, MIN_USERNAME, MAX_USERNAME,
)


def status_of(fn, *args, **kwargs) -> int:
    with pytest.raises(HTTPException) as exc:
        fn(*args, **kwargs)
    return exc.value.status_code


# ── clean_str ─────────────────────────────────────────────────────────────────

class TestCleanStr:
    def test_returns_stripped_value(self):
        assert clean_str("  Alice  ", "name", 50) == "Alice"

    def test_strip_false_keeps_value_exactly(self):
        assert clean_str("  pass word  ", "password", 50, strip=False) == "  pass word  "

    @pytest.mark.parametrize("value", [None, 5, 1.5, True, [], {}, b"bytes"])
    def test_non_string_rejected(self, value):
        assert status_of(clean_str, value, "f", 10) == 400

    @pytest.mark.parametrize("value", ["a\x00b", "\x00", "a\x01b", "a\x1fb", "a\x7fb"])
    def test_control_characters_rejected(self, value):
        assert status_of(clean_str, value, "f", 10) == 400

    @pytest.mark.parametrize("value", ["\ud800", "ok\udfff", "\ud83d"])
    def test_lone_surrogates_rejected(self, value):
        # JSON allows "\ud800"; UTF-8 encoding it (Postgres, itsdangerous, argon2) raises.
        assert status_of(clean_str, value, "f", 10) == 400

    def test_valid_surrogate_pair_is_just_an_emoji(self):
        assert clean_str("héllo 👋", "f", 10) == "héllo 👋"

    def test_newline_rejected_unless_multiline(self):
        assert status_of(clean_str, "a\nb", "f", 10) == 400
        assert status_of(clean_str, "a\tb", "f", 10) == 400
        assert clean_str("a\nb\tc\r", "f", 10, multiline=True) == "a\nb\tc"

    def test_multiline_still_rejects_nul(self):
        assert status_of(clean_str, "a\x00b", "f", 10, multiline=True) == 400

    def test_empty_and_whitespace_only_rejected_by_default(self):
        assert status_of(clean_str, "", "f", 10) == 400
        assert status_of(clean_str, "   ", "f", 10) == 400

    def test_whitespace_only_rejected_even_when_not_stripping(self):
        assert status_of(clean_str, "   ", "password", 10, strip=False) == 400

    def test_min_len_zero_allows_empty(self):
        assert clean_str("", "bio", 10, min_len=0) == ""
        assert clean_str("   ", "bio", 10, min_len=0) == ""

    def test_min_len_above_one(self):
        assert status_of(clean_str, "ab", "f", 10, min_len=3) == 400
        assert clean_str("abc", "f", 10, min_len=3) == "abc"

    def test_max_len_boundary(self):
        assert clean_str("a" * 10, "f", 10) == "a" * 10
        assert status_of(clean_str, "a" * 11, "f", 10) == 400

    def test_max_len_counts_the_stripped_value(self):
        assert clean_str("  " + "a" * 10 + "  ", "f", 10) == "a" * 10

    def test_huge_string_rejected(self):
        assert status_of(clean_str, "a" * 10_000_000, "f", 500) == 400

    def test_nullable_passes_none_through(self):
        assert clean_str(None, "bio", 10, nullable=True) is None

    def test_none_rejected_when_not_nullable(self):
        assert status_of(clean_str, None, "f", 10) == 400

    def test_nullable_still_validates_strings(self):
        assert status_of(clean_str, "a\x00", "bio", 10, nullable=True) == 400

    def test_error_names_the_field(self):
        with pytest.raises(HTTPException) as exc:
            clean_str(5, "first_name", 10)
        assert "first_name" in exc.value.detail


# ── clean_email ───────────────────────────────────────────────────────────────

class TestCleanEmail:
    def test_valid_email_returned_stripped(self):
        assert clean_email("  a@b.co ") == "a@b.co"

    @pytest.mark.parametrize("value", ["plain", "a@b", "@b.co", "a@.co", "a b@c.de", "a@b@c.de", "a@b.co\nx"])
    def test_malformed_rejected(self, value):
        assert status_of(clean_email, value) == 400

    def test_trailing_newline_is_refused(self):
        # A "$"-anchored regex would accept "a@b.co\n"; newlines are refused as control characters.
        assert status_of(clean_email, "a@b.co\n") == 400
        assert status_of(clean_email, "a@b.co\n\n") == 400

    def test_too_long_rejected(self):
        assert status_of(clean_email, "a" * 96 + "@b.co") == 400

    def test_boundary_length_accepted(self):
        email = "a" * 95 + "@b.co"
        assert len(email) == 100
        assert clean_email(email) == email

    @pytest.mark.parametrize("value", [None, 1, ["a@b.co"], "a\x00@b.co", "\ud800@b.co"])
    def test_bad_types_and_characters_rejected(self, value):
        assert status_of(clean_email, value) == 400


# ── clean_choice ──────────────────────────────────────────────────────────────

class TestCleanUsername:
    @pytest.mark.parametrize("value", [
        "abc", "Alice", "alice.smith", "alice-s_2", "9lives", "a" * MAX_USERNAME, "  alice  ",
    ])
    def test_accepts_letters_digits_and_separators(self, value):
        assert clean_username(value) == value.strip()

    def test_keeps_the_case(self):
        assert clean_username("AlIcE") == "AlIcE"

    @pytest.mark.parametrize("value", [
        "a" * (MIN_USERNAME - 1), "a" * (MAX_USERNAME + 1), "", "   ",
        "has space", "ali@ce", "ali/ce", "alice!", "alicé", "ali\tce", "ali\nce",
        "-alice", ".alice", "_alice", "<b>alice</b>", "alice'; DROP TABLE users;--",
    ])
    def test_refuses_what_is_not_a_username(self, value):
        assert status_of(clean_username, value) == 400

    @pytest.mark.parametrize("value", [None, 5, True, ["alice"], {"a": 1}, "ali\x00ce", "\ud800alice"])
    def test_refuses_non_strings_and_unsafe_strings(self, value):
        assert status_of(clean_username, value) == 400

    def test_a_username_never_contains_an_at_sign(self):
        # Login tells a username from an email by that character.
        assert status_of(clean_username, "alice@x.co") == 400

    def test_error_names_the_field(self):
        with pytest.raises(HTTPException) as exc:
            clean_username("a!", "login")
        assert exc.value.detail.startswith("login")


class TestCleanChoice:
    def test_accepts_allowed(self):
        for g in GENDERS:
            assert clean_choice(g, "gender", GENDERS) == g

    @pytest.mark.parametrize("value", ["Male", "MALE", " male", "robot", "", None, 1, ["male"], "male\x00"])
    def test_rejects_everything_else(self, value):
        assert status_of(clean_choice, value, "gender", GENDERS) == 400


# ── clean_int ─────────────────────────────────────────────────────────────────

class TestCleanInt:
    def test_accepts_in_range(self):
        assert clean_int(3, "to", 1, 5) == 3
        assert clean_int(1, "to", 1, 5) == 1
        assert clean_int(5, "to", 1, 5) == 5

    @pytest.mark.parametrize("value", [0, 6, -1, 10**30])
    def test_out_of_range_rejected(self, value):
        assert status_of(clean_int, value, "to", 1, 5) == 400

    @pytest.mark.parametrize("value", [True, False, 2.0, 2.5, "2", None, [2], float("inf"), float("nan")])
    def test_non_integers_rejected(self, value):
        assert status_of(clean_int, value, "to", 1, 5) == 400


# ── clean_float ───────────────────────────────────────────────────────────────

class TestCleanFloat:
    def test_accepts_ints_and_floats(self):
        assert clean_float(48, "lat", -90, 90) == 48.0
        assert clean_float(48.85, "lat", -90, 90) == 48.85
        assert clean_float(-90, "lat", -90, 90) == -90.0

    @pytest.mark.parametrize("value", [90.0001, -91, 1e999, 1e308])
    def test_out_of_range_rejected(self, value):
        assert status_of(clean_float, value, "lat", -90, 90) == 400

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_rejected(self, value):
        assert status_of(clean_float, value, "lat", -90, 90) == 400

    @pytest.mark.parametrize("value", [True, False, "48.8", None, [1]])
    def test_non_numbers_rejected(self, value):
        assert status_of(clean_float, value, "lat", -90, 90) == 400


# ── parse_int_param ───────────────────────────────────────────────────────────

class TestParseIntParam:
    def test_absent_is_none(self):
        assert parse_int_param(None, "page", 0, 10) is None

    def test_parses_in_range(self):
        assert parse_int_param("7", "page", 0, 10) == 7
        assert parse_int_param("-3", "x", -5, 5) == -3

    @pytest.mark.parametrize("value", ["", "abc", "1.5", "1e3", " 5", "5 ", "+5", "1_0", "٣", "--1", "0x10", "5\x00"])
    def test_non_plain_integers_rejected(self, value):
        assert status_of(parse_int_param, value, "page", 0, 10) == 400

    def test_out_of_range_rejected(self):
        assert status_of(parse_int_param, "11", "page", 0, 10) == 400
        assert status_of(parse_int_param, "-1", "page", 0, 10) == 400

    def test_huge_number_rejected_without_being_converted(self):
        assert status_of(parse_int_param, "9" * 5000, "page", 0, 10) == 400
        assert status_of(parse_int_param, "99999999999", "page", 0, 10) == 400


# ── valid_target_id ───────────────────────────────────────────────────────────

class TestValidTargetId:
    @pytest.mark.parametrize("value", [1, 42, MAX_ID])
    def test_valid_ids_returned(self, value):
        assert valid_target_id(value) == value

    @pytest.mark.parametrize("value", [0, -1, MAX_ID + 1, 10**30])
    def test_impossible_ids_are_404(self, value):
        assert status_of(valid_target_id, value) == 404
