import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.exc import IntegrityError

from news_reposter.db.models import Role, User
from news_reposter.services.users import (
    RolesNotFoundError,
    SelfManagementError,
    SystemRoleNotFoundError,
    UserAlreadyExistsError,
    UserService,
)


class MemoryUserRepository:
    def __init__(self, existing: User | None = None) -> None:
        self.existing = existing
        self.lookup: str | None = None
        self.added: User | None = None

    async def get_by_normalized_username(self, username: str) -> User | None:
        self.lookup = username
        return self.existing

    def add(self, user: User) -> None:
        self.added = user


class MemoryRoleRepository:
    def __init__(self, role: Role | None) -> None:
        self.role = role
        self.lookup: str | None = None

    async def get_by_code(self, code: str) -> Role | None:
        self.lookup = code
        return self.role


def test_create_administrator_normalizes_identity_and_assigns_role() -> None:
    async def scenario() -> None:
        session = AsyncMock()
        users = MemoryUserRepository()
        administrator = Role(
            role_id=1,
            code="administrator",
            name="Администратор",
            is_system=True,
            is_active=True,
        )
        roles = MemoryRoleRepository(administrator)
        passwords = Mock()
        passwords.hash.return_value = "$argon2id$test"
        service = UserService(
            session,
            password_manager=passwords,
            user_repository=users,
            role_repository=roles,
        )

        user = await service.create_administrator(
            username="  Admin.User ",
            display_name="  Александр  ",
            password="a sufficiently long password",
        )

        assert user is users.added
        assert users.lookup == "admin.user"
        assert roles.lookup == "administrator"
        assert user.username == "Admin.User"
        assert user.username_normalized == "admin.user"
        assert user.display_name == "Александр"
        assert user.password_hash == "$argon2id$test"
        assert user.is_active is True
        assert user.must_change_password is False
        assert user.roles == [administrator]
        passwords.hash.assert_called_once_with("a sufficiently long password")
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once_with(user)
        session.rollback.assert_not_awaited()

    asyncio.run(scenario())


def test_create_administrator_rejects_duplicate_before_hashing() -> None:
    async def scenario() -> None:
        session = AsyncMock()
        users = MemoryUserRepository(existing=User())
        roles = MemoryRoleRepository(None)
        passwords = Mock()
        service = UserService(
            session,
            password_manager=passwords,
            user_repository=users,
            role_repository=roles,
        )

        with pytest.raises(UserAlreadyExistsError):
            await service.create_administrator(
                username="ADMIN",
                display_name="Administrator",
                password="a sufficiently long password",
            )

        passwords.hash.assert_not_called()
        session.commit.assert_not_awaited()

    asyncio.run(scenario())


def test_create_administrator_requires_seeded_active_role() -> None:
    async def scenario() -> None:
        session = AsyncMock()
        users = MemoryUserRepository()
        roles = MemoryRoleRepository(None)
        passwords = Mock()
        service = UserService(
            session,
            password_manager=passwords,
            user_repository=users,
            role_repository=roles,
        )

        with pytest.raises(SystemRoleNotFoundError):
            await service.create_administrator(
                username="admin",
                display_name="Administrator",
                password="a sufficiently long password",
            )

        passwords.hash.assert_not_called()
        session.commit.assert_not_awaited()

    asyncio.run(scenario())


def test_create_administrator_rolls_back_concurrent_duplicate() -> None:
    async def scenario() -> None:
        session = AsyncMock()
        users = MemoryUserRepository()

        async def fail_with_duplicate() -> None:
            users.existing = User()
            raise IntegrityError(
                "INSERT INTO users",
                {},
                RuntimeError("duplicate"),
            )

        session.commit.side_effect = fail_with_duplicate
        roles = MemoryRoleRepository(
            Role(
                role_id=1,
                code="administrator",
                name="Администратор",
                is_active=True,
            )
        )
        passwords = Mock()
        passwords.hash.return_value = "$argon2id$test"
        service = UserService(
            session,
            password_manager=passwords,
            user_repository=users,
            role_repository=roles,
        )

        with pytest.raises(UserAlreadyExistsError):
            await service.create_administrator(
                username="admin",
                display_name="Administrator",
                password="a sufficiently long password",
            )

        session.rollback.assert_awaited_once()
        session.refresh.assert_not_awaited()

    asyncio.run(scenario())


def test_create_administrator_preserves_unrelated_integrity_error() -> None:
    async def scenario() -> None:
        session = AsyncMock()
        database_error = IntegrityError(
            "INSERT INTO users",
            {},
            RuntimeError("foreign key violation"),
        )
        session.commit.side_effect = database_error
        users = MemoryUserRepository()
        roles = MemoryRoleRepository(
            Role(
                role_id=1,
                code="administrator",
                name="Администратор",
                is_active=True,
            )
        )
        passwords = Mock()
        passwords.hash.return_value = "$argon2id$test"
        service = UserService(
            session,
            password_manager=passwords,
            user_repository=users,
            role_repository=roles,
        )

        with pytest.raises(IntegrityError) as caught:
            await service.create_administrator(
                username="admin",
                display_name="Administrator",
                password="a sufficiently long password",
            )

        assert caught.value is database_error
        session.rollback.assert_awaited_once()

    asyncio.run(scenario())


def test_create_user_assigns_roles_and_requires_password_change() -> None:
    async def scenario() -> None:
        session = AsyncMock()
        users = MemoryUserRepository()
        editor = Role(role_id=2, code="editor", name="Редактор", is_active=True)
        roles = MemoryRoleRepository(editor)
        roles.get_active_by_codes = AsyncMock(return_value=[editor])
        passwords = Mock()
        passwords.hash.return_value = "$argon2id$temporary"
        service = UserService(
            session,
            password_manager=passwords,
            user_repository=users,
            role_repository=roles,
        )

        user = await service.create_user(
            username=" Editor.One ",
            display_name=" Редактор ",
            temporary_password="temporary password 123",
            role_codes=["editor"],
        )

        assert user is users.added
        assert user.username_normalized == "editor.one"
        assert user.display_name == "Редактор"
        assert user.must_change_password is True
        assert user.roles == [editor]
        roles.get_active_by_codes.assert_awaited_once_with({"editor"})
        session.commit.assert_awaited_once()

    asyncio.run(scenario())


def test_deactivate_user_revokes_sessions_in_same_transaction() -> None:
    async def scenario() -> None:
        session = AsyncMock()
        managed = User(
            user_id=8,
            username="editor",
            username_normalized="editor",
            display_name="Редактор",
            password_hash="hash",
            is_active=True,
            must_change_password=False,
            roles=[],
        )
        users = MemoryUserRepository()
        users.get_by_id_for_update = AsyncMock(return_value=managed)
        sessions = AsyncMock()
        service = UserService(
            session,
            user_repository=users,
            role_repository=MemoryRoleRepository(None),
            session_repository=sessions,
        )

        result = await service.update_user(
            8,
            actor_user_id=1,
            is_active=False,
        )

        assert result.is_active is False
        sessions.revoke_all_for_user.assert_awaited_once()
        assert (
            sessions.revoke_all_for_user.await_args.kwargs["reason"] == "admin_revoked"
        )
        session.commit.assert_awaited_once()
        session.refresh.assert_awaited_once_with(
            managed,
            attribute_names=[
                "user_id",
                "created_at",
                "updated_at",
                "last_login_at",
            ],
        )

    asyncio.run(scenario())


def test_administrator_cannot_remove_own_access() -> None:
    async def scenario() -> None:
        session = AsyncMock()
        managed = User(user_id=1, is_active=True, roles=[])
        users = MemoryUserRepository()
        users.get_by_id_for_update = AsyncMock(return_value=managed)
        service = UserService(
            session,
            user_repository=users,
            role_repository=MemoryRoleRepository(None),
        )

        with pytest.raises(SelfManagementError):
            await service.update_user(1, actor_user_id=1, role_codes=["viewer"])

        session.commit.assert_not_awaited()

    asyncio.run(scenario())


def test_reset_password_marks_temporary_and_revokes_sessions() -> None:
    async def scenario() -> None:
        session = AsyncMock()
        managed = User(
            user_id=9,
            username="publisher",
            username_normalized="publisher",
            display_name="Выпускающий",
            password_hash="old-hash",
            is_active=True,
            must_change_password=False,
            roles=[],
        )
        users = MemoryUserRepository()
        users.get_by_id_for_update = AsyncMock(return_value=managed)
        sessions = AsyncMock()
        passwords = Mock()
        passwords.hash.return_value = "new-hash"
        service = UserService(
            session,
            password_manager=passwords,
            user_repository=users,
            role_repository=MemoryRoleRepository(None),
            session_repository=sessions,
        )

        result = await service.reset_password(
            9,
            actor_user_id=1,
            temporary_password="new temporary password",
        )

        assert result.password_hash == "new-hash"
        assert result.must_change_password is True
        passwords.hash.assert_called_once_with("new temporary password")
        sessions.revoke_all_for_user.assert_awaited_once()
        session.commit.assert_awaited_once()

    asyncio.run(scenario())


def test_create_user_rejects_unknown_role_before_hashing() -> None:
    async def scenario() -> None:
        session = AsyncMock()
        users = MemoryUserRepository()
        roles = MemoryRoleRepository(None)
        roles.get_active_by_codes = AsyncMock(return_value=[])
        passwords = Mock()
        service = UserService(
            session,
            password_manager=passwords,
            user_repository=users,
            role_repository=roles,
        )

        with pytest.raises(RolesNotFoundError, match="missing-role"):
            await service.create_user(
                username="editor",
                display_name="Редактор",
                temporary_password="temporary password 123",
                role_codes=["missing-role"],
            )

        passwords.hash.assert_not_called()
        session.commit.assert_not_awaited()

    asyncio.run(scenario())
