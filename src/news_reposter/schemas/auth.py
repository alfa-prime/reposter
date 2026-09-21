"""HTTP-контракт входа и текущего пользователя."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Учётные данные для создания серверной сессии."""

    username: str = Field(
        min_length=1,
        max_length=256,
        description="Логин пользователя.",
    )
    password: str = Field(
        min_length=1,
        max_length=1024,
        repr=False,
        description="Пароль пользователя.",
    )


class PasswordChangeRequest(BaseModel):
    """Текущий и новый пароли для безопасной замены."""

    current_password: str = Field(
        min_length=1,
        max_length=1024,
        repr=False,
        description="Текущий пароль пользователя.",
    )
    new_password: str = Field(
        min_length=1,
        max_length=1024,
        repr=False,
        description="Новый пароль пользователя, не менее 15 символов.",
    )


class CurrentUserRole(BaseModel):
    """Активная роль текущего пользователя."""

    code: str = Field(description="Стабильный технический код роли.")
    name: str = Field(description="Название роли для интерфейса.")


class CurrentUserResponse(BaseModel):
    """Безопасные данные текущего пользователя и его актуальные права."""

    user_id: int = Field(description="Идентификатор пользователя.")
    username: str = Field(description="Логин пользователя.")
    display_name: str = Field(description="Имя, отображаемое в интерфейсе.")
    avatar_url: str | None = Field(
        default=None,
        description="URL аватара; отсутствует, пока изображение не загружено.",
    )
    must_change_password: bool = Field(
        description="Нужно ли пользователю сменить временный пароль.",
    )
    roles: list[CurrentUserRole] = Field(
        description="Активные роли пользователя.",
    )
    permissions: list[str] = Field(
        description="Актуальные коды разрешённых действий.",
    )
