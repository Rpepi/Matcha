import pytest
from app.security.passwords import hash_password, verify_password, is_password_valid


class TestHashPassword:
    async def test_returns_argon2_hash(self):
        h = await hash_password("MyS3cur3P@ss!")
        assert h.startswith("$argon2")

    async def test_same_password_produces_different_hashes(self):
        h1 = await hash_password("MyS3cur3P@ss!")
        h2 = await hash_password("MyS3cur3P@ss!")
        assert h1 != h2  # Argon2 uses random salt


class TestVerifyPassword:
    async def test_correct_password_returns_true(self):
        h = await hash_password("MyS3cur3P@ss!")
        assert await verify_password(h, "MyS3cur3P@ss!") is True

    async def test_wrong_password_returns_false(self):
        h = await hash_password("MyS3cur3P@ss!")
        assert await verify_password(h, "WrongPassword1!") is False

    async def test_invalid_hash_returns_false(self):
        assert await verify_password("not_a_valid_hash", "anything") is False

    async def test_empty_password_returns_false(self):
        h = await hash_password("MyS3cur3P@ss!")
        assert await verify_password(h, "") is False


class TestIsPasswordValid:
    def test_all_digits_rejected(self):
        assert is_password_valid("123456789") is False

    def test_all_alpha_rejected(self):
        assert is_password_valid("abcdefghij") is False

    def test_common_word_rejected(self):
        # "password" is in the 10k most common list
        assert is_password_valid("password") is False

    def test_common_word_case_insensitive(self):
        assert is_password_valid("PASSWORD") is False
        assert is_password_valid("Password") is False

    def test_valid_password_accepted(self):
        assert is_password_valid("Tr0ub4dor&3") is True

    def test_valid_mixed_password_accepted(self):
        assert is_password_valid("hello123!") is True

    def test_short_common_word_rejected(self):
        assert is_password_valid("abc123") is False

    def test_short_password_rejected(self):
        assert is_password_valid("a2") is False

    def test_long_password_rejected(self):
        assert is_password_valid("fjpkdssjnvosjr4323jcnsken8766Rkuidcjuie9876543456fjenbrjHUIOIHGFDSERTY789876545678") is False
    
