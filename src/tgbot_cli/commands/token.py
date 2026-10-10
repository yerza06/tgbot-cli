"""Bot token configuration: ``tgbot token set`` and ``tgbot whoami``."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from .. import telegram
from ..config import get_settings, save_token
from ..console import out
from ..errors import TelegramAPIError, UsageError
from .options import JsonOpt

app = typer.Typer(help="Configure the Telegram bot token.", no_args_is_help=True)
top_level = typer.Typer()


def _bot_label(me: dict[str, Any]) -> str:
    username = me.get("username")
    return f"@{username} ({me.get('id')})" if username else str(me.get("id"))


@app.command("set")
def set_token(
    token: Annotated[
        str | None,
        typer.Argument(help="Bot token from @BotFather. Prompted (hidden) when omitted."),
    ] = None,
    json_output: JsonOpt = False,
) -> None:
    """Validate a bot token with Telegram and save it to the config directory."""
    out.use_json(json_output)
    if token is None:
        token = typer.prompt("Bot token", hide_input=True)
    token = token.strip()
    if not token:
        raise UsageError("The bot token is empty.")

    settings = get_settings()
    out.register_secret(token)
    client = telegram.BotClient(
        token, api_url=settings.api_url, timeout=settings.timeout, transport=telegram.TRANSPORT
    )
    with client, out.status("Checking token..."):
        try:
            me = client.call("getMe")
        except TelegramAPIError as exc:
            raise TelegramAPIError(
                f"token rejected ({exc.description})",
                error_code=exc.error_code,
                hint="Copy the token again from @BotFather.",
            ) from None

    save_token(settings, token)
    out.success(
        f"Token saved to {settings.env_file}. Bot: {_bot_label(me)}",
        data={"ok": True, "id": me.get("id"), "username": me.get("username")},
    )


@top_level.command("whoami")
def whoami(json_output: JsonOpt = False) -> None:
    """Show the bot the configured token belongs to."""
    out.use_json(json_output)
    settings = get_settings()
    with telegram.build_client(settings) as client, out.status("Asking Telegram..."):
        me = client.call("getMe")

    username = me.get("username")
    rows = [
        ("ID", str(me.get("id"))),
        ("Username", f"@{username}" if username else "—"),
        ("Name", me.get("first_name") or "—"),
    ]
    out.key_values(
        "Bot",
        rows,
        data={
            "ok": True,
            "id": me.get("id"),
            "username": username,
            "first_name": me.get("first_name"),
        },
    )
