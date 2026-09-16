from types import SimpleNamespace

from news_reposter.api.v1.queue_media_state import load_state, save_state, uploaded_keys
from news_reposter.services import media_storage


def test_uploaded_photo_uses_canonical_upload_key(
    tmp_path,
    monkeypatch,
) -> None:
    """Загруженное фото получает тот же ключ в редакторе и публикации."""

    monkeypatch.setattr(media_storage, "MEDIA_ROOT", tmp_path)
    directory = media_storage.queue_item_directory(7)
    directory.mkdir(parents=True)
    (directory / "photo.jpg").write_bytes(b"image")
    item = SimpleNamespace(
        queue_item_id=7,
        post=SimpleNamespace(attachments=[]),
    )

    assert uploaded_keys(7) == ["upload:photo.jpg"]

    save_state(7, ["upload:photo.jpg"])

    assert load_state(item) == ["upload:photo.jpg"]


def test_cleanup_queue_item_media_removes_nested_video_and_state(
    tmp_path,
    monkeypatch,
) -> None:
    """Очистка удаляет фото, вложенную папку видео и JSON состояния."""

    monkeypatch.setattr(media_storage, "MEDIA_ROOT", tmp_path)
    directory = media_storage.queue_item_directory(9)
    video_directory = directory / "videos"
    video_directory.mkdir(parents=True)
    (directory / "photo.jpg").write_bytes(b"image")
    (video_directory / "clip.mp4").write_bytes(b"video")
    state = media_storage.media_state_path(9)
    state.parent.mkdir(parents=True)
    state.write_text('["upload:photo.jpg"]', encoding="utf-8")

    media_storage.cleanup_queue_item_media(9)

    assert not directory.exists()
    assert not state.exists()
