"""SQLite storage for named chats (alias -> chat_id, like ``git remote``) and saved bots.

Bot tokens are stored only as ciphertext (see ``crypto``); this module never sees them in
plaintext. The default bot is not stored here but in ``config.toml``.
"""

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
);
CREATE TABLE IF NOT EXISTS bots (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    token_enc BLOB NOT NULL,
    bot_id INTEGER NOT NULL,
    username TEXT,
    created_at TEXT NOT NULL
);
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


class BotExistsError(ConfigError):
    def __init__(self, name: str) -> None:
        super().__init__(
            f"Bot '{name}' already exists.",
            hint="Pick another name, or remove it first with `tgbot bot remove`.",
        )
        self.name = name


class BotNotFoundError(ConfigError):
    def __init__(self, name: str, *, hint: str = "See saved bots with `tgbot bot list`.") -> None:
        super().__init__(f"Bot '{name}' not found.", hint=hint)
        self.name = name


class NoBotsError(ConfigError):
    def __init__(self) -> None:
        super().__init__(
            "No bot configured.",
            hint="Add one with `tgbot bot add NAME` (token from @BotFather).",
        )


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
        conn.executescript(SCHEMA)
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


# --------------------------------------------------------------------------- #
# Bots
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Bot:
    name: str
    bot_id: int
    username: str | None
    created_at: datetime

    def to_dict(self, default_name: str | None = None) -> dict[str, str | int | bool | None]:
        return {
            "name": self.name,
            "bot_id": self.bot_id,
            "username": self.username,
            "is_default": self.name == default_name,
            "created_at": self.created_at.isoformat(),
        }


_BOT_COLUMNS = "name, bot_id, username, created_at"


def _row_to_bot(row: tuple[str, int, str | None, str]) -> Bot:
    name, bot_id, username, created_at = row
    return Bot(name, bot_id, username, datetime.fromisoformat(created_at))


def find_bot(conn: sqlite3.Connection, name: str) -> Bot | None:
    row = conn.execute(f"SELECT {_BOT_COLUMNS} FROM bots WHERE name = ?", (name,)).fetchone()
    return _row_to_bot(row) if row else None


def get_bot(conn: sqlite3.Connection, name: str) -> Bot:
    bot = find_bot(conn, name)
    if bot is None:
        raise BotNotFoundError(name)
    return bot


def list_bots(conn: sqlite3.Connection) -> list[Bot]:
    rows = conn.execute(f"SELECT {_BOT_COLUMNS} FROM bots ORDER BY created_at, id").fetchall()
    return [_row_to_bot(row) for row in rows]


def get_bot_token_enc(conn: sqlite3.Connection, name: str) -> bytes:
    row = conn.execute("SELECT token_enc FROM bots WHERE name = ?", (name,)).fetchone()
    if row is None:
        raise BotNotFoundError(name)
    return bytes(row[0])


def add_bot(
    conn: sqlite3.Connection, name: str, token_enc: bytes, bot_id: int, username: str | None
) -> Bot:
    if find_bot(conn, name) is not None:
        raise BotExistsError(name)
    created = datetime.now(UTC).replace(microsecond=0)
    conn.execute(
        "INSERT INTO bots (name, token_enc, bot_id, username, created_at) VALUES (?, ?, ?, ?, ?)",
        (name, token_enc, bot_id, username, created.isoformat()),
    )
    conn.commit()
    return Bot(name, bot_id, username, created)


def remove_bot(conn: sqlite3.Connection, name: str) -> None:
    cursor = conn.execute("DELETE FROM bots WHERE name = ?", (name,))
    if cursor.rowcount == 0:
        raise BotNotFoundError(name)
    conn.commit()


def rename_bot(conn: sqlite3.Connection, old_name: str, new_name: str) -> Bot:
    bot = get_bot(conn, old_name)
    if old_name != new_name and find_bot(conn, new_name) is not None:
        raise BotExistsError(new_name)
    conn.execute("UPDATE bots SET name = ? WHERE name = ?", (new_name, old_name))
    conn.commit()
    return Bot(new_name, bot.bot_id, bot.username, bot.created_at)
