"""SQLite storage for named chats (alias -> chat_id), similar to ``git remote``."""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .errors import ConfigError

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    chat_id TEXT NOT NULL,
    title TEXT,
    created_at TEXT NOT NULL
)
"""


class ChatExistsError(ConfigError):
    def __init__(self, name: str) -> None:
        super().__init__(
            f"Chat '{name}' already exists.",
            hint="Use `tgbot chat replace-id` to change its ID or pick another name.",
        )
        self.name = name


class ChatNotFoundError(ConfigError):
    def __init__(self, name: str) -> None:
        super().__init__(
            f"Chat '{name}' not found.",
            hint="See saved chats with `tgbot chat list`.",
        )
        self.name = name


@dataclass(frozen=True)
class Chat:
    name: str
    chat_id: str
    title: str | None
    created_at: datetime

    def to_dict(self) -> dict[str, str | None]:
        return {
            "name": self.name,
            "chat_id": self.chat_id,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
        }


@contextlib.contextmanager
def open_db(path: Path) -> Iterator[sqlite3.Connection]:
    """Open (and create if needed) the chat database; commit on success, always close."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _row_to_chat(row: tuple[str, str, str | None, str]) -> Chat:
    name, chat_id, title, created_at = row
    return Chat(name, chat_id, title, datetime.fromisoformat(created_at))


_COLUMNS = "name, chat_id, title, created_at"


def find_chat(conn: sqlite3.Connection, name: str) -> Chat | None:
    row = conn.execute(f"SELECT {_COLUMNS} FROM chats WHERE name = ?", (name,)).fetchone()
    return _row_to_chat(row) if row else None


def get_chat(conn: sqlite3.Connection, name: str) -> Chat:
    chat = find_chat(conn, name)
    if chat is None:
        raise ChatNotFoundError(name)
    return chat


def list_chats(conn: sqlite3.Connection) -> list[Chat]:
    rows = conn.execute(f"SELECT {_COLUMNS} FROM chats ORDER BY name").fetchall()
    return [_row_to_chat(row) for row in rows]


def add_chat(conn: sqlite3.Connection, name: str, chat_id: str, title: str | None = None) -> Chat:
    if find_chat(conn, name) is not None:
        raise ChatExistsError(name)
    created = datetime.now(UTC).replace(microsecond=0)
    conn.execute(
        "INSERT INTO chats (name, chat_id, title, created_at) VALUES (?, ?, ?, ?)",
        (name, chat_id, title, created.isoformat()),
    )
    conn.commit()
    return Chat(name, chat_id, title, created)


def remove_chat(conn: sqlite3.Connection, name: str) -> None:
    cursor = conn.execute("DELETE FROM chats WHERE name = ?", (name,))
    if cursor.rowcount == 0:
        raise ChatNotFoundError(name)
    conn.commit()


def rename_chat(conn: sqlite3.Connection, old_name: str, new_name: str) -> Chat:
    chat = get_chat(conn, old_name)
    if old_name != new_name and find_chat(conn, new_name) is not None:
        raise ChatExistsError(new_name)
    conn.execute("UPDATE chats SET name = ? WHERE name = ?", (new_name, old_name))
    conn.commit()
    return Chat(new_name, chat.chat_id, chat.title, chat.created_at)


def replace_chat_id(
    conn: sqlite3.Connection, name: str, new_id: str, title: str | None = None
) -> Chat:
    chat = get_chat(conn, name)
    conn.execute("UPDATE chats SET chat_id = ?, title = ? WHERE name = ?", (new_id, title, name))
    conn.commit()
    return Chat(name, new_id, title, chat.created_at)
