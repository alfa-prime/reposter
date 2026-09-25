from __future__ import annotations

import asyncio
import os
import shutil
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import unquote
from uuid import uuid4

from fastapi import HTTPException, Request, status

from news_reposter.config import get_settings
from news_reposter.services.media_validation import MediaValidationError

_upload_semaphore: asyncio.Semaphore | None = None
_upload_semaphore_limit: int | None = None
_item_locks: dict[int, asyncio.Lock] = {}


def _semaphore() -> asyncio.Semaphore:
    global _upload_semaphore, _upload_semaphore_limit
    limit = get_settings().media_max_concurrent_uploads
    if _upload_semaphore is None or _upload_semaphore_limit != limit:
        _upload_semaphore = asyncio.Semaphore(limit)
        _upload_semaphore_limit = limit
    return _upload_semaphore


@asynccontextmanager
async def upload_slot(queue_item_id: int):
    semaphore = _semaphore()
    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=0.05)
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Сейчас выполняется слишком много загрузок. Повторите через несколько секунд.",
            headers={"Retry-After": "3"},
        ) from exc
    try:
        item_lock = _item_locks.setdefault(queue_item_id, asyncio.Lock())
        async with item_lock:
            yield
    finally:
        semaphore.release()


def directory_size(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())


def local_attachment_count(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(
        1
        for path in directory.rglob("*")
        if path.is_file() and not path.name.endswith(".part")
    )


def ensure_disk_space(directory: Path, incoming_bytes: int = 0) -> None:
    settings = get_settings()
    probe = directory if directory.exists() else directory.parent
    probe.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(probe)
    reserve = max(
        settings.media_min_free_bytes,
        int(usage.total * settings.media_min_free_percent / 100),
    )
    if usage.free - incoming_bytes < reserve:
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail="На сервере недостаточно свободного места для загрузки",
        )


def upload_metadata(request: Request) -> tuple[str, str]:
    filename = unquote(request.headers.get("X-Filename", "")).strip()
    content_type = request.headers.get("Content-Type", "").split(";", 1)[0].lower()
    if not filename or len(filename) > 255:
        raise HTTPException(status_code=400, detail="Не передано корректное имя файла")
    return Path(filename).name, content_type


async def stream_file_to_disk(
    request: Request,
    *,
    directory: Path,
    item_directory: Path | None = None,
    filename_prefix: str,
    extension: str,
    max_bytes: int,
    validate: Callable[[bytes, str], str],
    content_type: str,
) -> tuple[Path, int]:
    """Пишет тело запроса блоками во временный файл и атомарно завершает загрузку."""

    settings = get_settings()
    content_length = request.headers.get("Content-Length")
    if content_length:
        try:
            announced_size = int(content_length)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="Некорректный размер файла"
            ) from exc
        if announced_size > max_bytes:
            raise HTTPException(
                status_code=413, detail="Файл превышает допустимый размер"
            )
    else:
        announced_size = 0

    await asyncio.to_thread(ensure_disk_space, directory, announced_size)
    total_directory = item_directory or directory
    current_size = await asyncio.to_thread(directory_size, total_directory)
    if current_size + announced_size > settings.media_item_max_bytes:
        raise HTTPException(
            status_code=413, detail="Превышен общий лимит медиа материала"
        )

    await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True)
    temporary = directory / f".upload-{uuid4().hex}.part"
    final = directory / f"{filename_prefix}{uuid4().hex}{extension}"
    size = 0
    handle = await asyncio.to_thread(temporary.open, "xb")
    try:
        async for chunk in request.stream():
            if not chunk:
                continue
            size += len(chunk)
            if size > max_bytes or current_size + size > settings.media_item_max_bytes:
                raise HTTPException(
                    status_code=413, detail="Превышен допустимый размер медиа"
                )
            await asyncio.to_thread(handle.write, chunk)
        await asyncio.to_thread(handle.flush)
        await asyncio.to_thread(os.fsync, handle.fileno())
        if size == 0:
            raise HTTPException(status_code=400, detail="Пустой файл")
        header = await asyncio.to_thread(_read_header, temporary)
        try:
            validate(header, content_type)
        except MediaValidationError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc
        await asyncio.to_thread(ensure_disk_space, directory)
        await asyncio.to_thread(temporary.replace, final)
        return final, size
    finally:
        await asyncio.to_thread(handle.close)
        if temporary.exists():
            await asyncio.to_thread(temporary.unlink, missing_ok=True)


def _read_header(path: Path) -> bytes:
    with path.open("rb") as source:
        return source.read(4096)
