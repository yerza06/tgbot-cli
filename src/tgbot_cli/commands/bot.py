"""Saved bots (alias -> encrypted token), similar to ``tgbot chat``; plus ``tgbot whoami``.

The default bot lives in ``config.toml`` as ``default_bot``; these commands keep it in
sync when bots are added, renamed or removed.
"""

from __future__ import annotations

from typing import Annotated, Any

import typer

from .. import crypto, db, telegram
from ..completion import complete_bot
from ..config import Settings, config_file_value, get_settings, update_config
from ..console import out
from ..errors import TelegramAPIError, UsageError
from .options import BotOpt, JsonOpt

app = typer.Typer(help="Manage saved bots (token aliases, like `tgbot chat`).")
top_level = typer.Typer()

NameArg = Annotated[str, typer.Argument(help="Bot alias, e.g. `news` or `alerts`.")]
ExistingNameArg = Annotated[
    str, typer.Argument(help="Saved bot alias, e.g. `main`.", autocompletion=complete_bot)
]


def _bot_label(username: str | None, bot_id: Any) -> str:
    return f"@{username} ({bot_id})" if username else str(bot_id)


def _file_default(settings: Settings) -> str | None:
    value = config_file_value(settings, "default_bot")
    return value if isinstance(value, str) and value.strip() else None


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Without a subcommand — show the list of saved bots."""
    if ctx.invoked_subcommand is None:
        _list()


@app.command("add")
def add(
    name: NameArg,
    token: Annotated[
        str | None,
        typer.Argument(help="Bot token from @BotFather. Prompted (hidden) when omitted."),
    ] = None,
    json_output: JsonOpt = False,
) -> None:
    """Validate a bot token with Telegram and save it (encrypted) under NAME."""
    out.use_json(json_output)
    settings = get_settings()
    fernet = crypto.load_key(settings)  # before touching any file
    with db.open_db(settings.db_path) as conn:
        if db.find_bot(conn, name) is not None:
            raise db.BotExistsError(name)

    if token is None:
        token = typer.prompt("Bot token", hide_input=True)
    token = token.strip()
    if not token:
        raise UsageError("The bot token is empty.")

    with telegram.client_for_token(settings, token) as client, out.status("Checking token..."):
        try:
            me = client.call("getMe")
        except TelegramAPIError as exc:
            raise TelegramAPIError(
                f"token rejected ({exc.description})",
                error_code=exc.error_code,
                hint="Copy the token again from @BotFather.",
            ) from None

    with db.open_db(settings.db_path) as conn:
        bot = db.add_bot(conn, name, crypto.encrypt(fernet, token), me["id"], me.get("username"))
    default = _file_default(settings)
    if default is None:
        update_config(settings, default_bot=name)
        default = name

    suffix = " (default)" if default == name else ""
    out.success(
        f"Saved bot '{name}': {_bot_label(bot.username, bot.bot_id)}{suffix}",
        data={"ok": True, **bot.to_dict(default)},
    )


def _list() -> None:
    settings = get_settings()
    with db.open_db(settings.db_path) as conn:
        bots = db.list_bots(conn)
    if not bots and not out.is_json:
        out.info("No saved bots yet. Add one with `tgbot bot add NAME`.")
        return
    default = settings.default_bot
    rows = [
        (
            b.name,
            f"@{b.username}" if b.username else "—",
            str(b.bot_id),
            "yes" if b.name == default else "",
            b.created_at.strftime("%Y-%m-%d %H:%M"),
        )
        for b in bots
    ]
    out.table(
        "Saved bots",
        ("Name", "Username", "Bot ID", "Default", "Added (UTC)"),
        rows,
        data=[b.to_dict(default) for b in bots],
    )


@app.command("list")
def list_cmd(json_output: JsonOpt = False) -> None:
    """Show all saved bots (tokens are never shown)."""
    out.use_json(json_output)
    _list()


@app.command("default")
def default(name: ExistingNameArg, json_output: JsonOpt = False) -> None:
    """Make NAME the default bot (written to config.toml)."""
    out.use_json(json_output)
    settings = get_settings()
    with db.open_db(settings.db_path) as conn:
        bot = db.get_bot(conn, name)
    update_config(settings, default_bot=name)
    out.success(
        f"Default bot is now '{name}' ({settings.config_file})",
        data={"ok": True, **bot.to_dict(name)},
    )


@app.command("rename")
def rename(
    old_name: Annotated[
        str, typer.Argument(help="Current bot alias.", autocompletion=complete_bot)
    ],
    new_name: Annotated[str, typer.Argument(help="New bot alias.")],
    json_output: JsonOpt = False,
) -> None:
    """Rename a bot alias (keeps the token; updates default_bot if needed)."""
    out.use_json(json_output)
    settings = get_settings()
    with db.open_db(settings.db_path) as conn:
        bot = db.rename_bot(conn, old_name, new_name)
    default = _file_default(settings)
    if default == old_name:
        update_config(settings, default_bot=new_name)
        default = new_name
    out.success(f"Renamed '{old_name}' -> '{new_name}'", data={"ok": True, **bot.to_dict(default)})


@app.command("remove")
def remove(name: ExistingNameArg, json_output: JsonOpt = False) -> None:
    """Delete a saved bot and its token."""
    out.use_json(json_output)
    settings = get_settings()
    with db.open_db(settings.db_path) as conn:
        db.remove_bot(conn, name)
        remaining = db.list_bots(conn)

    new_default: str | None = None
    if _file_default(settings) == name:
        new_default = remaining[0].name if remaining else None
        update_config(settings, default_bot=new_default)
        if new_default:
            out.notice(f"Default bot is now '{new_default}'.")
    out.success(f"Removed '{name}'", data={"ok": True, "name": name, "default_bot": new_default})


@top_level.command("whoami")
def whoami(bot: BotOpt = None, json_output: JsonOpt = False) -> None:
    """Show the saved bot that would send (or the one given with --bot)."""
    out.use_json(json_output)
    settings = get_settings()
    name, token = telegram.resolve_bot_token(settings, bot)
    with telegram.client_for_token(settings, token) as client, out.status("Asking Telegram..."):
        me = client.call("getMe")

    username = me.get("username")
    rows = [
        ("Alias", name),
        ("ID", str(me.get("id"))),
        ("Username", f"@{username}" if username else "—"),
        ("Name", me.get("first_name") or "—"),
    ]
    out.key_values(
        "Bot",
        rows,
        data={
            "ok": True,
            "name": name,
            "id": me.get("id"),
            "username": username,
            "first_name": me.get("first_name"),
        },
    )
