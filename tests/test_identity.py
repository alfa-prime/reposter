import pytest

from news_reposter.auth.identity import (
    IdentityValidationError,
    prepare_display_name,
    prepare_username,
)


def test_username_is_unicode_normalized_and_case_insensitive() -> None:
    prepared = prepare_username("  Ａdmin.User  ")

    assert prepared.value == "Admin.User"
    assert prepared.normalized == "admin.user"


@pytest.mark.parametrize(
    "username",
    [
        "ab",
        "a" * 65,
        "-admin",
        "admin_",
        "admin user",
        "аdmin",
        "admin@example.com",
    ],
)
def test_username_rejects_ambiguous_or_unsupported_values(username: str) -> None:
    with pytest.raises(IdentityValidationError):
        prepare_username(username)


def test_display_name_supports_cyrillic_and_trims_whitespace() -> None:
    assert prepare_display_name("  Александр Углин  ") == "Александр Углин"


@pytest.mark.parametrize("display_name", ["", "   ", "x" * 201])
def test_display_name_enforces_database_limits(display_name: str) -> None:
    with pytest.raises(IdentityValidationError):
        prepare_display_name(display_name)
