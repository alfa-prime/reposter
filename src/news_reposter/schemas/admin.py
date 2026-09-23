"""HTTP-контракты управления пользователями и просмотра ролей."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class AdminRoleRead(BaseModel):
    """Роль, доступная для назначения пользователю."""

    code: str = Field(description="Стабильный технический код роли.")
    name: str = Field(description="Название роли для интерфейса.")
    description: str | None = Field(description="Назначение роли.")
    is_system: bool = Field(description="Является ли роль системной.")
    permissions: list[str] = Field(description="Коды разрешений роли.")


class AdminUserRead(BaseModel):
    """Учётная запись в административном интерфейсе."""

    user_id: int = Field(description="Идентификатор пользователя.")
    username: str = Field(description="Логин пользователя.")
    display_name: str = Field(description="Отображаемое имя пользователя.")
    avatar_url: str | None = Field(description="URL загруженного аватара пользователя.")
    is_active: bool = Field(description="Разрешён ли пользователю вход.")
    must_change_password: bool = Field(
        description="Нужно ли сменить временный пароль после входа."
    )
    last_login_at: datetime | None = Field(description="Время последнего входа.")
    created_at: datetime = Field(description="Время создания учётной записи.")
    updated_at: datetime = Field(description="Время последнего изменения.")
    roles: list[AdminRoleRead] = Field(description="Назначенные активные роли.")
    target_ids: list[int] = Field(description="Назначенные каналы публикации.")


class AdminUserCreate(BaseModel):
    """Данные новой учётной записи с временным паролем."""

    username: str = Field(min_length=1, max_length=256, description="Логин.")
    display_name: str = Field(
        min_length=1,
        max_length=256,
        description="Имя, отображаемое в интерфейсе.",
    )
    temporary_password: str = Field(
        min_length=1,
        max_length=1024,
        repr=False,
        description="Временный пароль, не менее 15 символов.",
    )
    role_codes: list[str] = Field(
        min_length=1,
        description="Коды ролей, назначаемых пользователю.",
    )
    target_ids: list[int] = Field(
        default_factory=list,
        description="Каналы публикации, доступные пользователю.",
    )

    @field_validator("role_codes")
    @classmethod
    def role_codes_are_unique(cls, value: list[str]) -> list[str]:
        """Не принимает пустые и повторяющиеся коды ролей."""

        prepared = [code.strip() for code in value]
        if any(not code for code in prepared):
            raise ValueError("Код роли не может быть пустым")
        if len(prepared) != len(set(prepared)):
            raise ValueError("Коды ролей не должны повторяться")
        return prepared

    @field_validator("target_ids")
    @classmethod
    def target_ids_are_unique(cls, value: list[int]) -> list[int]:
        if any(target_id <= 0 for target_id in value):
            raise ValueError("Идентификатор канала должен быть положительным")
        if len(value) != len(set(value)):
            raise ValueError("Каналы не должны повторяться")
        return value


class AdminUserUpdate(BaseModel):
    """Изменяемые администратором свойства учётной записи."""

    display_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Новое отображаемое имя.",
    )
    is_active: bool | None = Field(
        default=None,
        description="Новое состояние доступа к приложению.",
    )
    role_codes: list[str] | None = Field(
        default=None,
        min_length=1,
        description="Полный новый набор кодов ролей.",
    )
    target_ids: list[int] | None = Field(
        default=None,
        description="Полный новый набор доступных каналов публикации.",
    )

    @field_validator("target_ids")
    @classmethod
    def target_ids_are_unique(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if any(target_id <= 0 for target_id in value):
            raise ValueError("Идентификатор канала должен быть положительным")
        if len(value) != len(set(value)):
            raise ValueError("Каналы не должны повторяться")
        return value

    @field_validator("role_codes")
    @classmethod
    def role_codes_are_unique(cls, value: list[str] | None) -> list[str] | None:
        """Не принимает пустые и повторяющиеся коды ролей."""

        if value is None:
            return None
        prepared = [code.strip() for code in value]
        if any(not code for code in prepared):
            raise ValueError("Код роли не может быть пустым")
        if len(prepared) != len(set(prepared)):
            raise ValueError("Коды ролей не должны повторяться")
        return prepared


class AdminPasswordReset(BaseModel):
    """Новый временный пароль пользователя."""

    temporary_password: str = Field(
        min_length=1,
        max_length=1024,
        repr=False,
        description="Временный пароль, не менее 15 символов.",
    )


class RevokedSessionsResponse(BaseModel):
    """Результат административного отзыва сессий."""

    revoked_sessions: int = Field(
        ge=0,
        description="Количество отозванных активных сессий.",
    )
