"""Shell completion of saved chat and bot aliases.

Completers run on every <Tab>, so they must be read-only and silent: they never create the
config dir or the database, never touch the network or the encryption key, and turn every
failure into "no suggestions".
"""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Iterator

import typer

from .config import get_settings

Suggestions = list[tuple[str, str]]


@contextlib.contextmanager
def _read_only_db() -> Iterator[sqlite3.Connection | None]:
    """The saved database opened read-only, or ``None`` when it does not exist."""
    path = get_settings().db_path
    if not path.is_file():
        yield None
        return
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        yield conn
    finally:
        conn.close()


def _query(sql: str) -> list[tuple]:
    try:
        with _read_only_db() as conn:
            return [] if conn is None else conn.execute(sql).fetchall()
    except Exception:  # completion must never print or fail
        return []


def complete_chat(incomplete: str) -> Suggestions:
    """Saved chat aliases starting with ``incomplete``; help is ``chat_id · title``."""
    rows = _query("SELECT name, chat_id, title FROM chats ORDER BY name")
    return [
        (name, f"{chat_id} · {title}" if title else str(chat_id))
        for name, chat_id, title in rows
        if name.startswith(incomplete)
    ]


def complete_bot(incomplete: str) -> Suggestions:
    """Saved bot aliases starting with ``incomplete``; help is ``@username`` (or the bot ID)."""
    rows = _query("SELECT name, bot_id, username FROM bots ORDER BY created_at, id")
    return [
        (name, f"@{username}" if username else str(bot_id))
        for name, bot_id, username in rows
        if name.startswith(incomplete)
    ]


def complete_target_after_media(ctx: typer.Context, incomplete: str) -> Suggestions:
    """Media commands: files first; chat aliases only after a media argument.

    Returning nothing makes the shell fall back to file path completion, so a word that
    matches no alias (e.g. ``./``) still completes as a path.
    """
    if not ctx.params.get("items"):
        return []
    return complete_chat(incomplete)
