"""Безопасные административные команды приложения."""

import argparse
import asyncio
import getpass
import hmac
from collections.abc import Sequence

from news_reposter.auth.identity import IdentityValidationError
from news_reposter.auth.passwords import PasswordValidationError
from news_reposter.db.session import async_session_factory, close_database
from news_reposter.services.users import (
    SystemRoleNotFoundError,
    UserAlreadyExistsError,
    UserService,
)


class PasswordConfirmationError(ValueError):
    """Два введённых пароля различаются."""


def build_parser() -> argparse.ArgumentParser:
    """Создаёт парсер административных команд."""

    parser = argparse.ArgumentParser(prog="python -m news_reposter.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "create-admin",
        help="интерактивно создать администратора",
    )
    return parser


def prompt_admin_details() -> tuple[str, str, str]:
    """Запрашивает данные, не отображая пароль в терминале."""

    username = input("Логин: ")
    display_name = input("Отображаемое имя: ")
    password = getpass.getpass("Пароль: ")
    confirmation = getpass.getpass("Повторите пароль: ")
    if not hmac.compare_digest(password, confirmation):
        raise PasswordConfirmationError("Введённые пароли не совпадают")
    return username, display_name, password


async def create_admin(username: str, display_name: str, password: str) -> int:
    """Создаёт администратора и возвращает его идентификатор."""

    try:
        async with async_session_factory() as session:
            user = await UserService(session).create_administrator(
                username=username,
                display_name=display_name,
                password=password,
            )
            return user.user_id
    finally:
        await close_database()


def main(argv: Sequence[str] | None = None) -> int:
    """Выполняет выбранную административную команду."""

    args = build_parser().parse_args(argv)
    if args.command == "create-admin":
        try:
            username, display_name, password = prompt_admin_details()
            user_id = asyncio.run(create_admin(username, display_name, password))
        except (
            IdentityValidationError,
            PasswordConfirmationError,
            PasswordValidationError,
            SystemRoleNotFoundError,
            UserAlreadyExistsError,
        ) as exc:
            print(f"Ошибка: {exc}")
            return 1

        print(f"Администратор создан, ID: {user_id}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
