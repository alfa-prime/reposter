import asyncio
import os
import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from news_reposter.services import media_upload
from news_reposter.services.media_cleanup import cleanup_orphaned_media
from news_reposter.services.media_validation import validate_image_content

PNG = b"\x89PNG\r\n\x1a\n" + b"payload"


def streaming_request(content: bytes, content_type: str = "image/png") -> Request:
    chunks = [content[:5], content[5:]]

    async def receive():
        if chunks:
            return {
                "type": "http.request",
                "body": chunks.pop(0),
                "more_body": bool(chunks),
            }
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/upload",
            "headers": [
                (b"content-type", content_type.encode()),
                (b"content-length", str(len(content)).encode()),
                (b"x-filename", b"photo.png"),
            ],
        },
        receive,
    )


def test_stream_upload_writes_atomically_and_removes_temporary_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(media_upload, "ensure_disk_space", lambda *_args: None)

    async def scenario() -> None:
        path, size = await media_upload.stream_file_to_disk(
            streaming_request(PNG),
            directory=tmp_path,
            filename_prefix="",
            extension=".png",
            max_bytes=1024,
            validate=validate_image_content,
            content_type="image/png",
        )
        assert size == len(PNG)
        assert path.read_bytes() == PNG
        assert not list(tmp_path.glob("*.part"))

    asyncio.run(scenario())


def test_stream_upload_stops_when_limit_is_exceeded(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(media_upload, "ensure_disk_space", lambda *_args: None)

    async def scenario() -> None:
        with pytest.raises(HTTPException) as error:
            await media_upload.stream_file_to_disk(
                streaming_request(PNG),
                directory=tmp_path,
                filename_prefix="",
                extension=".png",
                max_bytes=4,
                validate=validate_image_content,
                content_type="image/png",
            )
        assert error.value.status_code == 413
        assert not list(tmp_path.iterdir())

    asyncio.run(scenario())


def test_stream_upload_rejects_fake_image_and_removes_temporary_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(media_upload, "ensure_disk_space", lambda *_args: None)

    async def scenario() -> None:
        with pytest.raises(HTTPException) as error:
            await media_upload.stream_file_to_disk(
                streaming_request(b"not-an-image"),
                directory=tmp_path,
                filename_prefix="",
                extension=".png",
                max_bytes=1024,
                validate=validate_image_content,
                content_type="image/png",
            )
        assert error.value.status_code == 415
        assert not list(tmp_path.iterdir())

    asyncio.run(scenario())


def test_disk_reserve_blocks_upload_before_writing(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        media_upload,
        "get_settings",
        lambda: SimpleNamespace(
            media_min_free_bytes=200,
            media_min_free_percent=10,
        ),
    )
    monkeypatch.setattr(
        media_upload.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=1000, used=850, free=150),
    )

    with pytest.raises(HTTPException) as error:
        media_upload.ensure_disk_space(tmp_path, 1)

    assert error.value.status_code == 507


def test_cleanup_removes_only_old_temporary_and_orphaned_media(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = time.time()
    active = tmp_path / "1"
    orphan = tmp_path / "2"
    active.mkdir()
    orphan.mkdir()
    old_temp = active / ".upload-old.part"
    recent_temp = active / ".upload-recent.part"
    old_temp.write_bytes(b"old")
    recent_temp.write_bytes(b"recent")
    (orphan / "photo.jpg").write_bytes(b"orphan")
    old_time = now - 10 * 86400
    old_temp.touch()
    for path in (old_temp, orphan / "photo.jpg", orphan):
        path.touch()
        path.chmod(0o644 if path.is_file() else 0o755)
        os.utime(path, (old_time, old_time))

    removed_temp, removed_orphans = cleanup_orphaned_media(tmp_path, {1}, now=now)

    assert (removed_temp, removed_orphans) == (1, 1)
    assert not old_temp.exists()
    assert recent_temp.exists()
    assert not orphan.exists()
