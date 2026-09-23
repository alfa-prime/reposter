from typing import Annotated

from fastapi import Depends

from news_reposter.api.dependencies import require_permission
from news_reposter.auth.context import AuthContext
from news_reposter.auth.rbac import PermissionCode
from news_reposter.repositories.queue_item import QueueItemRepository


def target_scope(auth: AuthContext) -> dict[str, frozenset[int]]:
    """Возвращает аргумент репозитория только для ограниченного пользователя."""

    target_ids = getattr(auth, "target_ids", None)
    return {} if target_ids is None else {"allowed_target_ids": target_ids}


def can_access_target(auth: AuthContext, target_id: int) -> bool:
    target_ids = getattr(auth, "target_ids", None)
    return target_ids is None or target_id in target_ids


async def get_accessible_queue_item(
    repository: QueueItemRepository,
    queue_item_id: int,
    auth: AuthContext,
):
    return await repository.get(queue_item_id, **target_scope(auth))


QueueReadDep = Annotated[
    AuthContext,
    Depends(require_permission(PermissionCode.QUEUE_READ)),
]
QueueEditDep = Annotated[
    AuthContext,
    Depends(require_permission(PermissionCode.QUEUE_EDIT)),
]
QueueRewriteDep = Annotated[
    AuthContext,
    Depends(require_permission(PermissionCode.QUEUE_REWRITE)),
]
QueueSubmitDep = Annotated[
    AuthContext,
    Depends(require_permission(PermissionCode.QUEUE_SUBMIT)),
]
QueueModerateDep = Annotated[
    AuthContext,
    Depends(require_permission(PermissionCode.QUEUE_MODERATE)),
]
QueueScheduleDep = Annotated[
    AuthContext,
    Depends(require_permission(PermissionCode.QUEUE_SCHEDULE)),
]
QueuePublishDep = Annotated[
    AuthContext,
    Depends(require_permission(PermissionCode.QUEUE_PUBLISH)),
]
