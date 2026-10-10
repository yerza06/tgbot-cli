"""Root tgbot CLI application and console-script entry point."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Annotated

import typer

from .commands import bot, chat, info, key, send
from .config import get_settings
from .console import out
from .errors import TgbotError, UsageError

app = typer.Typer(
    name="tgbot",
    help="Send Telegram messages as a bot. Write-only: tgbot never reads messages.",
    no_args_is_help=True,
    add_completion=True,
    rich_markup_mode=None,
)

# Saved bots: tgbot bot add/list/… and tgbot whoami.
app.add_typer(bot.app, name="bot")
app.registered_commands.extend(bot.top_level.registered_commands)

# Encryption key for saved bot tokens (tgbot key init).
app.add_typer(key.app, name="key")

# Chat alias management (tgbot chat …).
app.add_typer(chat.app, name="chat")

# Sending commands at the top level (tgbot send / sendphoto / …).
app.registered_commands.extend(send.app.registered_commands)

# Meta commands (tgbot version).
app.registered_commands.extend(info.app.registered_commands)


def _version_callback(value: bool) -> None:
    if value:
        print(info.version_line())
        raise typer.Exit()


@app.callback()
def _main(
    plain: Annotated[
        bool, typer.Option("--plain", help="Plain text output without colors or boxes.")
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Machine-readable JSON output.")
    ] = False,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=_version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """tgbot — send Telegram messages as a bot."""
    settings = get_settings()
    out.configure(plain=plain or settings.plain or not settings.color, json_output=json_output)


def run(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the process exit code (no tracebacks, stable codes)."""
    args = list(sys.argv[1:] if argv is None else argv)
    out.reset()
    out.configure(json_output="--json" in args)
    try:
        result = app(args=args, prog_name="tgbot", standalone_mode=False)
    except TgbotError as exc:
        out.error(exc)
        return exc.exit_code
    except typer.Abort:
        return 130
    except typer.TyperException as exc:  # usage errors raised by the argument parser
        if out.is_json:
            out.error(UsageError(exc.format_message()), code=exc.exit_code)
        elif hasattr(exc, "show"):
            exc.show()
        else:
            out.error(UsageError(exc.format_message()), code=exc.exit_code)
        return exc.exit_code
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # top-level safety net: no raw tracebacks
        out.error(f"Unexpected error: {type(exc).__name__}: {exc}")
        return 1
    return result if isinstance(result, int) else 0


def main() -> None:
    """Console-script entry point."""
    sys.exit(run())
