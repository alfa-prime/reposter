import os
import shutil
from collections.abc import Iterable
from pathlib import Path

MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "/app/data/media"))


def queue_item_directory(queue_item_id: int) -> Path:
    """Возвращает общую папку фото и видео элемента очереди."""

    return MEDIA_ROOT / str(queue_item_id)


def media_state_path(queue_item_id: int) -> Path:
    """Возвращает путь к сохранённому порядку фотографий."""

    return MEDIA_ROOT / "_state" / f"{queue_item_id}.json"


def cleanup_queue_item_media(queue_item_id: int) -> None:
    """Удаляет фото, вложенную папку видео и состояние элемента очереди."""

    directory = queue_item_directory(queue_item_id)
    if directory.exists():
        shutil.rmtree(directory)
    media_state_path(queue_item_id).unlink(missing_ok=True)


def cleanup_queue_items_media(queue_item_ids: Iterable[int]) -> None:
    """Удаляет файловые данные нескольких элементов после каскадного удаления."""

    for queue_item_id in queue_item_ids:
        cleanup_queue_item_media(queue_item_id)
