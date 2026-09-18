import re

from news_reposter.auth.session_tokens import (
    generate_session_tokens,
    hash_token,
    token_matches,
)


def test_session_and_csrf_tokens_are_independent_url_safe_secrets() -> None:
    first = generate_session_tokens()
    second = generate_session_tokens()

    tokens = {
        first.session_token,
        first.csrf_token,
        second.session_token,
        second.csrf_token,
    }
    assert len(tokens) == 4
    assert all(len(token) >= 43 for token in tokens)
    assert all(re.fullmatch(r"[A-Za-z0-9_-]+", token) for token in tokens)
    assert first.session_token not in repr(first)
    assert first.csrf_token not in repr(first)


def test_token_hash_is_fixed_length_and_deterministic() -> None:
    token = "client-only-secret"

    first_hash = hash_token(token)
    second_hash = hash_token(token)

    assert first_hash == second_hash
    assert len(first_hash) == 32
    assert token.encode() not in first_hash
    assert token_matches(token, first_hash) is True
    assert token_matches("another-token", first_hash) is False


def test_empty_or_malformed_token_never_matches() -> None:
    assert token_matches("", bytes(32)) is False
    assert token_matches("token", b"too-short") is False
