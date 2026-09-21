import pytest
from pydantic import ValidationError

from news_reposter.config import Settings


def test_session_policy_has_safe_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.auth_session_idle_minutes == 60
    assert settings.auth_session_absolute_hours == 12
    assert settings.auth_session_touch_interval_minutes == 5
    assert settings.auth_max_sessions_per_user == 5
    assert settings.auth_login_attempt_window_minutes == 15
    assert settings.auth_login_block_minutes == 15
    assert settings.auth_login_max_attempts_per_username == 5
    assert settings.auth_login_max_attempts_per_ip == 20


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {
                "auth_session_idle_minutes": 5,
                "auth_session_touch_interval_minutes": 5,
            },
            "AUTH_SESSION_TOUCH_INTERVAL_MINUTES",
        ),
        (
            {
                "auth_session_idle_minutes": 60,
                "auth_session_absolute_hours": 1,
            },
            "AUTH_SESSION_IDLE_MINUTES",
        ),
    ],
)
def test_session_policy_rejects_inconsistent_lifetimes(
    overrides: dict[str, int],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        Settings(_env_file=None, **overrides)
