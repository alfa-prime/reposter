from sqlalchemy import (
    Boolean,
    DateTime,
    LargeBinary,
    String,
    inspect,
)
from sqlalchemy.dialects.postgresql import INET

from news_reposter.db.models import LoginAttempt, User, UserSession


def constraint_names(model: type[object]) -> set[str | None]:
    return {constraint.name for constraint in model.__table__.constraints}


def index_names(model: type[object]) -> set[str | None]:
    return {index.name for index in model.__table__.indexes}


def test_user_session_stores_only_fixed_length_token_hashes() -> None:
    table = UserSession.__table__

    assert table.name == "user_sessions"
    assert table.c.session_id.primary_key is True
    assert isinstance(table.c.token_hash.type, LargeBinary)
    assert table.c.token_hash.type.length == 32
    assert table.c.token_hash.nullable is False
    assert isinstance(table.c.csrf_token_hash.type, LargeBinary)
    assert table.c.csrf_token_hash.type.length == 32
    assert table.c.csrf_token_hash.nullable is False
    assert "uq_user_sessions_token_hash" in constraint_names(UserSession)
    assert "token" not in table.c


def test_user_session_has_server_enforced_lifetime_and_revocation_fields() -> None:
    table = UserSession.__table__

    assert isinstance(table.c.created_at.type, DateTime)
    assert table.c.created_at.type.timezone is True
    assert table.c.created_at.nullable is False
    assert table.c.last_seen_at.type.timezone is True
    assert table.c.absolute_expires_at.type.timezone is True
    assert table.c.revoked_at.type.timezone is True
    assert table.c.revoked_at.nullable is True
    assert isinstance(table.c.revoked_reason.type, String)
    assert table.c.revoked_reason.type.length == 64

    assert {
        "ck_user_sessions_token_hash_length",
        "ck_user_sessions_csrf_token_hash_length",
        "ck_user_sessions_expires_after_created",
        "ck_user_sessions_revoked_after_created",
    } <= constraint_names(UserSession)


def test_user_session_tracks_client_metadata_without_binding_identity_to_it() -> None:
    table = UserSession.__table__

    assert isinstance(table.c.ip_address.type, INET)
    assert table.c.ip_address.nullable is True
    assert isinstance(table.c.user_agent.type, String)
    assert table.c.user_agent.type.length == 512
    assert table.c.user_agent.nullable is True


def test_user_session_indexes_support_lookup_cleanup_and_active_session_limit() -> None:
    assert {
        "uq_user_sessions_token_hash",
        "ix_user_sessions_absolute_expires_at",
        "ix_user_sessions_user_active",
    } <= constraint_names(UserSession) | index_names(UserSession)

    active_index = next(
        index
        for index in UserSession.__table__.indexes
        if index.name == "ix_user_sessions_user_active"
    )
    assert [column.name for column in active_index.columns] == [
        "user_id",
        "revoked_at",
        "absolute_expires_at",
    ]


def test_user_session_is_deleted_with_its_user() -> None:
    foreign_key = next(iter(UserSession.__table__.c.user_id.foreign_keys))

    assert foreign_key.target_fullname == "users.user_id"
    assert foreign_key.ondelete == "CASCADE"


def test_login_attempt_uses_fingerprint_instead_of_raw_username() -> None:
    table = LoginAttempt.__table__

    assert table.name == "login_attempts"
    assert table.c.login_attempt_id.primary_key is True
    assert "username" not in table.c
    assert isinstance(table.c.username_fingerprint.type, LargeBinary)
    assert table.c.username_fingerprint.type.length == 32
    assert table.c.username_fingerprint.nullable is False
    assert "ck_login_attempts_username_fingerprint_length" in constraint_names(
        LoginAttempt
    )


def test_login_attempt_contains_throttling_and_correlation_fields() -> None:
    table = LoginAttempt.__table__

    assert isinstance(table.c.ip_address.type, INET)
    assert isinstance(table.c.was_successful.type, Boolean)
    assert table.c.was_successful.nullable is False
    assert table.c.attempted_at.type.timezone is True
    assert table.c.attempted_at.nullable is False
    assert table.c.request_id.type.length == 64
    assert table.c.request_id.nullable is True

    assert {
        "ix_login_attempts_attempted_at",
        "ix_login_attempts_ip_at",
        "ix_login_attempts_user_id",
        "ix_login_attempts_username_at",
    } <= index_names(LoginAttempt)

    for index_name in (
        "ix_login_attempts_ip_at",
        "ix_login_attempts_username_at",
    ):
        index = next(item for item in table.indexes if item.name == index_name)
        where = index.dialect_options["postgresql"]["where"]
        assert str(where) == "was_successful = false"


def test_login_attempt_survives_user_deletion_for_security_history() -> None:
    foreign_key = next(iter(LoginAttempt.__table__.c.user_id.foreign_keys))

    assert LoginAttempt.__table__.c.user_id.nullable is True
    assert foreign_key.target_fullname == "users.user_id"
    assert foreign_key.ondelete == "SET NULL"


def test_auth_session_relationships_are_bidirectional() -> None:
    user_relationships = inspect(User).relationships
    session_relationships = inspect(UserSession).relationships
    attempt_relationships = inspect(LoginAttempt).relationships

    assert user_relationships.sessions.mapper.class_ is UserSession
    assert user_relationships.login_attempts.mapper.class_ is LoginAttempt
    assert session_relationships.user.mapper.class_ is User
    assert attempt_relationships.user.mapper.class_ is User
