"""Meta commands: ``tgbot version``."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

import typer

from .. import db
from ..config import get_settings
from ..console import out
from .options import JsonOpt

app = typer.Typer()


def package_version() -> str:
    try:
        return version("tgbot-cli")
    except PackageNotFoundError:  # pragma: no cover - running from a source tree
        return "0.0.0"


def version_line() -> str:
    return f"tgbot {package_version()}"


@app.command("version")
def version_cmd(json_output: JsonOpt = False) -> None:
    """Show the version, config locations, saved bots and defaults (never tokens)."""
    out.use_json(json_output)
    settings = get_settings()
    with db.open_db(settings.db_path) as conn:
        bots = len(db.list_bots(conn))
    out.key_values(
        version_line(),
        [
            ("Version", package_version()),
            ("Config dir", str(settings.config_dir)),
            ("Config file", str(settings.config_file)),
            ("Database", str(settings.db_path)),
            ("Saved bots", str(bots)),
            ("Default bot", settings.default_bot or "—"),
            ("Default chat", settings.default_chat or "—"),
        ],
        data={
            "version": package_version(),
            "config_dir": str(settings.config_dir),
            "config_file": str(settings.config_file),
            "database": str(settings.db_path),
            "bots": bots,
            "default_bot": settings.default_bot,
            "default_chat": settings.default_chat,
        },
    )
