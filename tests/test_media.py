import os

import pytest

from tgbot_cli.errors import UsageError
from tgbot_cli.media import (
    MAX_PHOTO_BYTES,
    MAX_UPLOAD_BYTES,
    Upload,
    check_caption,
    chunk_text,
    looks_like_path,
    resolve_input,
)


def _sparse_file(path, size):
    with open(path, "wb") as fh:
        fh.truncate(size)
    return path


def test_existing_file_is_upload(tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(b"png")
    result = resolve_input(str(path), kind="photo")
    assert isinstance(result, Upload)
    assert result.filename == "a.png"
    assert result.mime_type == "image/png"


def test_url_passthrough():
    assert resolve_input("https://example.com/a.png", kind="photo") == "https://example.com/a.png"


def test_file_id_passthrough():
    assert resolve_input("CAACAgIAAxkBAAEB_x-y", kind="sticker") == "CAACAgIAAxkBAAEB_x-y"


@pytest.mark.parametrize("value", ["nope.pdf", "dir/file", "~/x"])
def test_missing_path_named_in_error(value):
    with pytest.raises(UsageError, match="File not found"):
        resolve_input(value, kind="document")


def test_directory_rejected(tmp_path):
    with pytest.raises(UsageError, match="not a regular file"):
        resolve_input(str(tmp_path), kind="document")


def test_upload_limit(tmp_path):
    path = _sparse_file(tmp_path / "big.bin", MAX_UPLOAD_BYTES + 1)
    with pytest.raises(UsageError, match="50 MB"):
        resolve_input(str(path), kind="document")
    os.remove(path)


def test_photo_limit(tmp_path):
    path = _sparse_file(tmp_path / "big.jpg", MAX_PHOTO_BYTES + 1)
    with pytest.raises(UsageError, match="10 MB"):
        resolve_input(str(path), kind="photo")
    assert isinstance(resolve_input(str(path), kind="document"), Upload)


def test_caption_limit():
    check_caption("x" * 1024)
    check_caption(None)
    with pytest.raises(UsageError, match="1024"):
        check_caption("x" * 1025)


def test_looks_like_path():
    assert looks_like_path("report.pdf")
    assert not looks_like_path("CAACAgIAAxkBAAEB")
    assert not looks_like_path("me")


def test_chunk_short_text():
    assert chunk_text("hello") == ["hello"]
    assert chunk_text("") == []


def test_chunk_9000_chars_prefers_newlines():
    lines = [f"line {i:04d} " + "x" * 80 for i in range(100)]
    text = "\n".join(lines)
    assert len(text) > 9000
    parts = chunk_text(text)
    assert len(parts) == 3
    assert all(len(part) <= 4096 for part in parts)
    assert "\n".join(parts) == text


def test_chunk_without_newlines_is_hard_cut():
    text = "a" * 9000
    parts = chunk_text(text)
    assert [len(p) for p in parts] == [4096, 4096, 808]
    assert "".join(parts) == text
