"""Resolve a send target: saved alias -> numeric chat ID -> ``@username``."""

from __future__ import annotations

import re
import sqlite3

from .db import find_chat
from .errors import ConfigError

_USERNAME_RE = re.compile(r"^@[A-Za-z][A-Za-z0-9_]{3,}$")


def parse_chat_id(value: str) -> int | str | None:
    """Return an int for numeric IDs, the string for ``@username``, otherwise ``None``."""
    raw = value.strip()
    try:
        return int(raw)
    except ValueError:
        pass
    if _USERNAME_RE.match(raw):
        return raw
    return None


def resolve_target(conn: sqlite3.Connection, value: str) -> int | str:
    """Turn a target given on the command line into a Bot API ``chat_id``."""
    chat = find_chat(conn, value)
    if chat is not None:
        parsed = parse_chat_id(chat.chat_id)
        return parsed if parsed is not None else chat.chat_id

    parsed = parse_chat_id(value)
    if parsed is None:
        raise ConfigError(
            f"Unknown chat '{value}'.",
            hint=(
                "Save it with `tgbot chat add NAME CHAT_ID`, or pass a numeric chat ID or @channel."
            ),
        )
    return parsed
