"""Стабильные коды возможностей и начальные системные роли.

Коды разрешений являются контрактом между API и базой данных. Наборы прав
ролей хранятся в PostgreSQL и позднее смогут редактироваться через интерфейс.
"""

from dataclasses import dataclass
from enum import StrEnum


class PermissionCode(StrEnum):
    """Действия, для которых backend выполняет проверку доступа."""

    OVERVIEW_READ = "overview.read"
    QUEUE_READ = "queue.read"
    QUEUE_EDIT = "queue.edit"
    QUEUE_REWRITE = "queue.rewrite"
    QUEUE_SUBMIT = "queue.submit"
    QUEUE_MODERATE = "queue.moderate"
    QUEUE_SCHEDULE = "queue.schedule"
    QUEUE_PUBLISH = "queue.publish"
    COLLECTION_RUN = "collection.run"
    SCHEDULER_READ = "scheduler.read"
    SCHEDULER_MANAGE = "scheduler.manage"
    SOURCES_READ = "sources.read"
    SOURCES_MANAGE = "sources.manage"
    TARGETS_READ = "targets.read"
    TARGETS_MANAGE = "targets.manage"
    USERS_READ = "users.read"
    USERS_MANAGE = "users.manage"
    ROLES_READ = "roles.read"
    ROLES_MANAGE = "roles.manage"
    AUDIT_READ = "audit.read"


class SystemRoleCode(StrEnum):
    """Неудаляемые роли, создаваемые первой RBAC-миграцией."""

    ADMINISTRATOR = "administrator"
    EDITOR = "editor"
    PUBLISHER = "publisher"
    VIEWER = "viewer"


@dataclass(frozen=True, slots=True)
class PermissionDefinition:
    """Человекочитаемое описание известного backend разрешения."""

    name: str
    description: str


@dataclass(frozen=True, slots=True)
class SystemRoleDefinition:
    """Начальное содержимое системной роли."""

    name: str
    description: str
    permissions: frozenset[PermissionCode]


PERMISSIONS: dict[PermissionCode, PermissionDefinition] = {
    PermissionCode.OVERVIEW_READ: PermissionDefinition(
        name="Просмотр обзора",
        description="Просмотр общей статистики и состояния приложения.",
    ),
    PermissionCode.QUEUE_READ: PermissionDefinition(
        name="Просмотр очереди",
        description="Просмотр материалов редакционной очереди.",
    ),
    PermissionCode.QUEUE_EDIT: PermissionDefinition(
        name="Редактирование материалов",
        description="Изменение текста и параметров материала.",
    ),
    PermissionCode.QUEUE_REWRITE: PermissionDefinition(
        name="Запуск рерайта",
        description="Создание новой версии текста через LLM.",
    ),
    PermissionCode.QUEUE_SUBMIT: PermissionDefinition(
        name="Отправка на модерацию",
        description="Передача подготовленного материала выпускающему редактору.",
    ),
    PermissionCode.QUEUE_MODERATE: PermissionDefinition(
        name="Модерация материалов",
        description="Одобрение и отклонение подготовленных материалов.",
    ),
    PermissionCode.QUEUE_SCHEDULE: PermissionDefinition(
        name="Планирование публикаций",
        description="Назначение и изменение времени публикации.",
    ),
    PermissionCode.QUEUE_PUBLISH: PermissionDefinition(
        name="Публикация материалов",
        description="Немедленная публикация одобренных материалов.",
    ),
    PermissionCode.COLLECTION_RUN: PermissionDefinition(
        name="Ручной сбор",
        description="Запуск внеочередного сбора публикаций из источников.",
    ),
    PermissionCode.SCHEDULER_READ: PermissionDefinition(
        name="Просмотр планировщика",
        description="Просмотр расписания и истории автоматического сбора.",
    ),
    PermissionCode.SCHEDULER_MANAGE: PermissionDefinition(
        name="Настройка планировщика",
        description="Изменение расписания автоматического сбора.",
    ),
    PermissionCode.SOURCES_READ: PermissionDefinition(
        name="Просмотр источников",
        description="Просмотр подключённых источников публикаций.",
    ),
    PermissionCode.SOURCES_MANAGE: PermissionDefinition(
        name="Управление источниками",
        description="Создание, изменение и отключение источников.",
    ),
    PermissionCode.TARGETS_READ: PermissionDefinition(
        name="Просмотр каналов",
        description="Просмотр целевых каналов публикации.",
    ),
    PermissionCode.TARGETS_MANAGE: PermissionDefinition(
        name="Управление каналами",
        description="Создание, изменение и отключение целевых каналов.",
    ),
    PermissionCode.USERS_READ: PermissionDefinition(
        name="Просмотр пользователей",
        description="Просмотр учётных записей пользователей.",
    ),
    PermissionCode.USERS_MANAGE: PermissionDefinition(
        name="Управление пользователями",
        description="Создание, изменение и блокировка пользователей.",
    ),
    PermissionCode.ROLES_READ: PermissionDefinition(
        name="Просмотр ролей",
        description="Просмотр ролей и назначенных им разрешений.",
    ),
    PermissionCode.ROLES_MANAGE: PermissionDefinition(
        name="Управление ролями",
        description="Создание ролей и изменение назначенных им разрешений.",
    ),
    PermissionCode.AUDIT_READ: PermissionDefinition(
        name="Просмотр аудита",
        description="Просмотр журнала действий пользователей и системы.",
    ),
}


READ_ONLY_PERMISSIONS = frozenset(
    {
        PermissionCode.OVERVIEW_READ,
        PermissionCode.QUEUE_READ,
        PermissionCode.SCHEDULER_READ,
        PermissionCode.SOURCES_READ,
        PermissionCode.TARGETS_READ,
    }
)

EDITOR_PERMISSIONS = READ_ONLY_PERMISSIONS | {
    PermissionCode.QUEUE_EDIT,
    PermissionCode.QUEUE_REWRITE,
    PermissionCode.QUEUE_SUBMIT,
    PermissionCode.COLLECTION_RUN,
}

PUBLISHER_PERMISSIONS = EDITOR_PERMISSIONS | {
    PermissionCode.QUEUE_MODERATE,
    PermissionCode.QUEUE_SCHEDULE,
    PermissionCode.QUEUE_PUBLISH,
}

SYSTEM_ROLES: dict[SystemRoleCode, SystemRoleDefinition] = {
    SystemRoleCode.ADMINISTRATOR: SystemRoleDefinition(
        name="Администратор",
        description="Полное управление приложением, пользователями и настройками.",
        permissions=frozenset(PermissionCode),
    ),
    SystemRoleCode.EDITOR: SystemRoleDefinition(
        name="Редактор",
        description="Подготовка материалов и отправка их на модерацию.",
        permissions=frozenset(EDITOR_PERMISSIONS),
    ),
    SystemRoleCode.PUBLISHER: SystemRoleDefinition(
        name="Выпускающий редактор",
        description="Модерация, планирование и публикация материалов.",
        permissions=frozenset(PUBLISHER_PERMISSIONS),
    ),
    SystemRoleCode.VIEWER: SystemRoleDefinition(
        name="Наблюдатель",
        description="Просмотр очереди, справочников и состояния планировщика.",
        permissions=READ_ONLY_PERMISSIONS,
    ),
}
