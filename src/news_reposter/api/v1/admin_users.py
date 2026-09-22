"""Административное управление пользователями и просмотр ролей."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from news_reposter.api.dependencies import (
    PERMISSION_AUTH_RESPONSES,
    PERMISSION_CSRF_AUTH_RESPONSES,
    CsrfAuthContextDep,
    SameOriginDep,
    UserServiceDep,
    require_permission,
)
from news_reposter.auth.context import AuthContext
from news_reposter.auth.identity import IdentityValidationError
from news_reposter.auth.passwords import PasswordValidationError
from news_reposter.auth.rbac import PermissionCode
from news_reposter.db.models import Role, User
from news_reposter.schemas import (
    AdminPasswordReset,
    AdminRoleRead,
    AdminUserCreate,
    AdminUserRead,
    AdminUserUpdate,
    RevokedSessionsResponse,
)
from news_reposter.services.users import (
    RolesNotFoundError,
    SelfManagementError,
    UserAlreadyExistsError,
    UserNotFoundError,
)

router = APIRouter(prefix="/admin", tags=["Администрирование"])
UsersReadDep = Annotated[
    AuthContext,
    Depends(require_permission(PermissionCode.USERS_READ)),
]
UsersManageDep = Annotated[
    AuthContext,
    Depends(require_permission(PermissionCode.USERS_MANAGE)),
]
RolesReadDep = Annotated[
    AuthContext,
    Depends(require_permission(PermissionCode.ROLES_READ)),
]
UserId = Annotated[
    int,
    Path(gt=0, description="Идентификатор управляемого пользователя"),
]


@router.get(
    "/users",
    response_model=list[AdminUserRead],
    summary="Получить список пользователей",
    description=(
        "Возвращает учётные записи, их состояние, назначенные роли и время "
        "последнего входа для административного интерфейса."
    ),
    responses=PERMISSION_AUTH_RESPONSES,
)
async def list_users(
    service: UserServiceDep,
    _auth: UsersReadDep,
) -> list[AdminUserRead]:
    return [_user_response(user) for user in await service.list_users()]


@router.get(
    "/roles",
    response_model=list[AdminRoleRead],
    summary="Получить список ролей",
    description=(
        "Возвращает активные роли и входящие в них разрешения, чтобы администратор "
        "мог назначать роли пользователям."
    ),
    responses=PERMISSION_AUTH_RESPONSES,
)
async def list_roles(
    service: UserServiceDep,
    _auth: RolesReadDep,
) -> list[AdminRoleRead]:
    return [_role_response(role) for role in await service.list_roles()]


@router.post(
    "/users",
    response_model=AdminUserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать пользователя",
    description=(
        "Создаёт активную учётную запись с временным паролем. При первом входе "
        "пользователь обязан заменить пароль."
    ),
    responses={
        **PERMISSION_CSRF_AUTH_RESPONSES,
        409: {"description": "Пользователь с таким логином уже существует"},
        422: {"description": "Некорректные данные, пароль или роли"},
    },
)
async def create_user(
    payload: AdminUserCreate,
    service: UserServiceDep,
    _auth: UsersManageDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> AdminUserRead:
    try:
        user = await service.create_user(
            username=payload.username,
            display_name=payload.display_name,
            temporary_password=payload.temporary_password,
            role_codes=payload.role_codes,
        )
    except UserAlreadyExistsError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (
        IdentityValidationError,
        PasswordValidationError,
        RolesNotFoundError,
    ) as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return _user_response(user)


@router.patch(
    "/users/{user_id}",
    response_model=AdminUserRead,
    summary="Изменить пользователя",
    description=(
        "Меняет отображаемое имя, состояние доступа или полный набор ролей. "
        "Отключение учётной записи сразу завершает её активные сессии."
    ),
    responses={
        **PERMISSION_CSRF_AUTH_RESPONSES,
        400: {"description": "Нельзя лишить доступа текущего администратора"},
        404: {"description": "Пользователь не найден"},
        422: {"description": "Нет изменений либо данные или роли некорректны"},
    },
)
async def update_user(
    user_id: UserId,
    payload: AdminUserUpdate,
    service: UserServiceDep,
    auth: UsersManageDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> AdminUserRead:
    if not payload.model_fields_set:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Не указано ни одного изменения",
        )
    try:
        user = await service.update_user(
            user_id,
            actor_user_id=auth.user.user_id,
            **payload.model_dump(exclude_unset=True),
        )
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SelfManagementError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except (IdentityValidationError, RolesNotFoundError) as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return _user_response(user)


@router.post(
    "/users/{user_id}/reset-password",
    response_model=AdminUserRead,
    summary="Сбросить пароль пользователя",
    description=(
        "Устанавливает новый временный пароль, требует его смену при следующем "
        "входе и завершает все активные сессии пользователя."
    ),
    responses={
        **PERMISSION_CSRF_AUTH_RESPONSES,
        400: {"description": "Для текущего администратора используется смена пароля"},
        404: {"description": "Пользователь не найден"},
        422: {"description": "Временный пароль не соответствует политике"},
    },
)
async def reset_user_password(
    user_id: UserId,
    payload: AdminPasswordReset,
    service: UserServiceDep,
    auth: UsersManageDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> AdminUserRead:
    try:
        user = await service.reset_password(
            user_id,
            actor_user_id=auth.user.user_id,
            temporary_password=payload.temporary_password,
        )
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SelfManagementError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PasswordValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return _user_response(user)


@router.post(
    "/users/{user_id}/revoke-sessions",
    response_model=RevokedSessionsResponse,
    summary="Завершить сессии пользователя",
    description="Немедленно отзывает все активные сессии выбранного пользователя.",
    responses={
        **PERMISSION_CSRF_AUTH_RESPONSES,
        400: {"description": "Текущая сессия завершается через меню пользователя"},
        404: {"description": "Пользователь не найден"},
    },
)
async def revoke_user_sessions(
    user_id: UserId,
    service: UserServiceDep,
    auth: UsersManageDep,
    _csrf_auth: CsrfAuthContextDep,
    _same_origin: SameOriginDep,
) -> RevokedSessionsResponse:
    try:
        count = await service.revoke_sessions(
            user_id,
            actor_user_id=auth.user.user_id,
        )
    except UserNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SelfManagementError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RevokedSessionsResponse(revoked_sessions=count)


def _role_response(role: Role) -> AdminRoleRead:
    return AdminRoleRead(
        code=role.code,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=sorted(permission.code for permission in role.permissions),
    )


def _user_response(user: User) -> AdminUserRead:
    return AdminUserRead(
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=sorted(
            (_role_response(role) for role in user.roles),
            key=lambda role: (role.name, role.code),
        ),
    )
