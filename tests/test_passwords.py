import pytest

from news_reposter.auth.passwords import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    PasswordManager,
    PasswordValidationError,
    validate_password,
)


def test_argon2id_hash_does_not_store_plaintext_and_can_be_verified() -> None:
    manager = PasswordManager()
    password = "correct horse battery staple"

    password_hash = manager.hash(password)

    assert password_hash != password
    assert password_hash.startswith("$argon2id$")
    assert manager.verify(password, password_hash) is True
    assert manager.verify("incorrect password", password_hash) is False


def test_hash_uses_a_new_random_salt_each_time() -> None:
    manager = PasswordManager()
    password = "correct horse battery staple"

    assert manager.hash(password) != manager.hash(password)


def test_current_hash_does_not_need_rehashing() -> None:
    manager = PasswordManager()
    password = "correct horse battery staple"
    password_hash = manager.hash(password)

    verified, updated_hash = manager.verify_and_update(password, password_hash)

    assert verified is True
    assert updated_hash is None


@pytest.mark.parametrize(
    "password",
    ["x" * (MIN_PASSWORD_LENGTH - 1), "x" * (MAX_PASSWORD_LENGTH + 1)],
)
def test_password_length_policy(password: str) -> None:
    with pytest.raises(PasswordValidationError):
        validate_password(password)
