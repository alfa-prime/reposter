from typing import Annotated

from fastapi import Depends

from news_reposter.api.dependencies import require_permission
from news_reposter.auth.context import AuthContext
from news_reposter.auth.rbac import PermissionCode

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
