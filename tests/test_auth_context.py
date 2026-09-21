from datetime import UTC, datetime, timedelta

from news_reposter.auth.context import AuthContext
from news_reposter.db.models import Permission, Role, User, UserSession


def test_auth_context_uses_only_active_roles_and_deduplicates_permissions() -> None:
    shared = Permission(code="queue.read", name="Просмотр очереди")
    edit = Permission(code="queue.edit", name="Редактирование очереди")
    active = Role(
        code="editor",
        name="Редактор",
        is_active=True,
        permissions=[shared, edit],
    )
    duplicate = Role(
        code="publisher",
        name="Выпускающий редактор",
        is_active=True,
        permissions=[shared],
    )
    inactive = Role(
        code="disabled",
        name="Отключённая роль",
        is_active=False,
        permissions=[Permission(code="users.manage", name="Пользователи")],
    )
    user = User(
        user_id=7,
        username="editor",
        username_normalized="editor",
        display_name="Редактор",
        password_hash="hash",
        roles=[active, duplicate, inactive],
    )
    now = datetime.now(UTC)
    session = UserSession(
        session_id=3,
        user_id=user.user_id,
        token_hash=b"a" * 32,
        csrf_token_hash=b"b" * 32,
        created_at=now,
        last_seen_at=now,
        absolute_expires_at=now + timedelta(hours=12),
        user=user,
    )

    context = AuthContext.from_session(session)

    assert context.user is user
    assert context.role_codes == frozenset({"editor", "publisher"})
    assert context.permission_codes == frozenset({"queue.read", "queue.edit"})
