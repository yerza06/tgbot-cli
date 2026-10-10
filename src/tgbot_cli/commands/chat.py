"""Named chat identifier management (similar to ``git remote``)."""

from __future__ import annotations

from typing import Annotated

import typer

from .. import db, telegram
from ..config import Settings, get_settings, update_config
from ..console import out
from ..errors import ConfigError, NetworkError, TelegramAPIError, UsageError
from ..resolver import parse_chat_id
from .options import ALLOW_NEG, JsonOpt

app = typer.Typer(help="Manage saved chat aliases (like `git remote`).")

NameArg = Annotated[str, typer.Argument(help="Alias name, e.g. `me` or `team`.")]


def _validate_chat_id(value: str) -> str:
    raw = value.strip()
    if parse_chat_id(raw) is None:
        raise UsageError(
            f"Invalid chat ID '{value}'.",
            hint="Use a numeric ID (e.g. 13342324, -1001234567890) or a @channel username.",
        )
    return raw


def _resolve_username(settings: Settings, value: str) -> tuple[str, str | None]:
    """Resolve ``@username`` via getChat; fall back to storing the value as given."""
    try:
        client = telegram.build_client(settings)
    except ConfigError as exc:
        out.notice(f"{exc.message} Stored '{value}' as is (not resolved).")
        return value, None
    try:
        with client:
            result = client.call("getChat", {"chat_id": value})
    except (TelegramAPIError, NetworkError) as exc:
        out.notice(f"Could not resolve '{value}' ({out.scrub(exc.message)}); stored as is.")
        return value, None
    title = result.get("title") or result.get("first_name") or result.get("username")
    return str(result["id"]), title


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Without a subcommand — show the list of saved chats."""
    if ctx.invoked_subcommand is None:
        _list()


@app.command("add", context_settings=ALLOW_NEG)
def add(
    name: NameArg,
    chat_id: Annotated[str, typer.Argument(help="Numeric chat ID or @channel username.")],
    no_resolve: Annotated[
        bool, typer.Option("--no-resolve", help="Store @username as given, without getChat.")
    ] = False,
    json_output: JsonOpt = False,
) -> None:
    """Save a chat alias. A @public_channel is resolved to its numeric ID."""
    out.use_json(json_output)
    stored_id = _validate_chat_id(chat_id)
    settings = get_settings()

    title: str | None = None
    if stored_id.startswith("@") and not no_resolve:
        stored_id, title = _resolve_username(settings, stored_id)

    with db.open_db(settings.db_path) as conn:
        chat = db.add_chat(conn, name, stored_id, title)
    suffix = f" ({chat.title})" if chat.title else ""
    out.success(
        f"Added '{chat.name}' -> {chat.chat_id}{suffix}", data={"ok": True, **chat.to_dict()}
    )


def _list() -> None:
    settings = get_settings()
    with db.open_db(settings.db_path) as conn:
        chats = db.list_chats(conn)
    if not chats and not out.is_json:
        out.info("No saved chats yet. Add one with `tgbot chat add NAME CHAT_ID`.")
        return
    rows = [
        (c.name, c.chat_id, c.title or "—", c.created_at.strftime("%Y-%m-%d %H:%M")) for c in chats
    ]
    out.table(
        "Saved chats",
        ("Name", "Chat ID", "Title", "Created (UTC)"),
        rows,
        data=[c.to_dict() for c in chats],
    )


@app.command("list")
def list_cmd(json_output: JsonOpt = False) -> None:
    """Show all saved chats."""
    out.use_json(json_output)
    _list()


@app.command("get-id")
def get_id(name: NameArg, json_output: JsonOpt = False) -> None:
    """Print only the chat ID of an alias."""
    out.use_json(json_output)
    with db.open_db(get_settings().db_path) as conn:
        chat = db.get_chat(conn, name)
    out.value(chat.chat_id, data={"name": chat.name, "chat_id": chat.chat_id})


@app.command("default")
def default(name: NameArg, json_output: JsonOpt = False) -> None:
    """Send to this chat when no target is given (written to config.toml)."""
    out.use_json(json_output)
    settings = get_settings()
    with db.open_db(settings.db_path) as conn:
        chat = db.get_chat(conn, name)
    update_config(settings, default_chat=name)
    out.success(
        f"Default chat is now '{name}' ({settings.config_file})",
        data={"ok": True, **chat.to_dict()},
    )


@app.command("replace-id", context_settings=ALLOW_NEG)
def replace_id(
    name: NameArg,
    new_id: Annotated[str, typer.Argument(help="New numeric chat ID or @channel.")],
    json_output: JsonOpt = False,
) -> None:
    """Change the chat ID an alias points to."""
    out.use_json(json_output)
    stored_id = _validate_chat_id(new_id)
    with db.open_db(get_settings().db_path) as conn:
        chat = db.replace_chat_id(conn, name, stored_id)
    out.success(f"'{chat.name}' now points to {chat.chat_id}", data={"ok": True, **chat.to_dict()})


@app.command("rename")
def rename(
    old_name: Annotated[str, typer.Argument(help="Current alias name.")],
    new_name: Annotated[str, typer.Argument(help="New alias name.")],
    json_output: JsonOpt = False,
) -> None:
    """Rename an alias."""
    out.use_json(json_output)
    with db.open_db(get_settings().db_path) as conn:
        chat = db.rename_chat(conn, old_name, new_name)
    out.success(f"Renamed '{old_name}' -> '{chat.name}'", data={"ok": True, **chat.to_dict()})


@app.command("remove")
def remove(name: NameArg, json_output: JsonOpt = False) -> None:
    """Delete an alias."""
    out.use_json(json_output)
    with db.open_db(get_settings().db_path) as conn:
        db.remove_chat(conn, name)
    out.success(f"Removed '{name}'", data={"ok": True, "name": name})
