"""Media inputs (local file / URL / file_id), Telegram limits and text chunking."""

from __future__ import annotations

import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path

from .errors import UsageError

MB = 1024 * 1024
MAX_UPLOAD_BYTES = 50 * MB
MAX_PHOTO_BYTES = 10 * MB
MAX_CAPTION = 1024
MAX_TEXT = 4096

_FILE_EXT_RE = re.compile(r"\.[A-Za-z0-9]{1,5}$")


@dataclass(frozen=True)
class Upload:
    """A local file to upload as multipart form data."""

    path: Path

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def mime_type(self) -> str | None:
        return mimetypes.guess_type(self.path.name)[0]


InputValue = Upload | str


def is_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def is_existing_file(value: str) -> bool:
    return Path(value).expanduser().is_file()


def is_content_token(value: str) -> bool:
    """Tokens recognised as media content in the positional syntax."""
    return is_url(value) or is_existing_file(value)


def looks_like_path(value: str) -> bool:
    """Heuristic: Telegram file_ids never contain dots, slashes or a leading ``~``."""
    return (
        "/" in value or "\\" in value or value.startswith("~") or bool(_FILE_EXT_RE.search(value))
    )


def resolve_input(value: str, *, kind: str) -> InputValue:
    """Classify a media argument: existing file -> Upload, URL -> str, else file_id."""
    if is_url(value):
        return value
    path = Path(value).expanduser()
    if path.is_file():
        size = path.stat().st_size
        limit = MAX_PHOTO_BYTES if kind == "photo" else MAX_UPLOAD_BYTES
        if size > limit:
            raise UsageError(
                f"File '{value}' is {size / MB:.1f} MB; Telegram bots can upload "
                f"{kind}s of at most {limit // MB} MB."
            )
        return Upload(path)
    if path.exists():
        raise UsageError(f"'{value}' is not a regular file.")
    if looks_like_path(value):
        raise UsageError(f"File not found: {value}")
    return value  # Telegram file_id


def check_caption(caption: str | None) -> None:
    if caption is not None and len(caption) > MAX_CAPTION:
        raise UsageError(
            f"Caption is {len(caption)} characters long; Telegram allows at most {MAX_CAPTION}."
        )


def chunk_text(text: str, limit: int = MAX_TEXT) -> list[str]:
    """Split ``text`` into parts of at most ``limit`` characters, preferring line breaks.

    The newline a part is broken at is dropped; nothing else is lost or reordered.
    """
    parts: list[str] = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit + 1)
        if cut > 0:
            parts.append(text[:cut])
            text = text[cut + 1 :]
        else:
            parts.append(text[:limit])
            text = text[limit:]
    if text:
        parts.append(text)
    return parts
