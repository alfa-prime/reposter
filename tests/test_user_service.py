import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.exc import IntegrityError

from news_reposter.db.models import Role, User
from news_reposter.services.users import (
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
