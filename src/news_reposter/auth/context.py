"""Актуальный пользовательский контекст для одного HTTP-запроса."""

from dataclasses import dataclass

from news_reposter.db.models import User, UserSession


@dataclass(frozen=True, slots=True)
class AuthContext:
    """Проверенная сессия и вычисленные из активных ролей права."""

    session: UserSession
    user: User
    role_codes: frozenset[str]
    permission_codes: frozenset[str]

    @classmethod
    def from_session(cls, user_session: UserSession) -> "AuthContext":
        """Создаёт контекст только из активных на данный момент ролей."""

        active_roles = [role for role in user_session.user.roles if role.is_active]
        return cls(
            session=user_session,
            user=user_session.user,
            role_codes=frozenset(role.code for role in active_roles),
            permission_codes=frozenset(
                permission.code
                for role in active_roles
                for permission in role.permissions
            ),
        )
