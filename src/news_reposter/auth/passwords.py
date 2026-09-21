"""Хеширование паролей и единая политика их проверки."""

from pwdlib import PasswordHash

MIN_PASSWORD_LENGTH = 15
MAX_PASSWORD_LENGTH = 1024
DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$liG2joXKEv1ltp8OiH2D8w$"
    "DgBNIc2kDhd8y2MhNuGaUQ7Rp0xh7CfbGuv64D8zbQE"
)


class PasswordValidationError(ValueError):
    """Пароль не соответствует требованиям безопасности."""


class PasswordManager:
    """Создаёт и проверяет самодокументируемые Argon2id-хеши."""

    def __init__(self, password_hash: PasswordHash | None = None) -> None:
        self._password_hash = password_hash or PasswordHash.recommended()

    def hash(self, password: str) -> str:
        """Проверяет пароль и возвращает стойкий хеш со случайной солью."""

        validate_password(password)
        return self._password_hash.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        """Безопасно сравнивает пароль с сохранённым хешем."""

        return self._password_hash.verify(password, password_hash)

    def verify_and_update(
        self,
        password: str,
        password_hash: str,
    ) -> tuple[bool, str | None]:
        """Проверяет пароль и при необходимости возвращает обновлённый хеш."""

        return self._password_hash.verify_and_update(password, password_hash)

    def verify_dummy(self, password: str) -> None:
        """Выполняет Argon2id для неизвестной учётной записи."""

        self._password_hash.verify(password, DUMMY_PASSWORD_HASH)


def validate_password(password: str) -> None:
    """Проверяет длину без навязывания небезопасных правил состава."""

    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordValidationError(
            f"Пароль должен содержать не менее {MIN_PASSWORD_LENGTH} символов"
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        raise PasswordValidationError(
            f"Пароль должен содержать не более {MAX_PASSWORD_LENGTH} символов"
        )
