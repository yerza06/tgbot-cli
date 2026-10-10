"""Meta commands: ``tgbot version``."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

import typer

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
    """Show the version, config locations and whether a token is configured."""
    out.use_json(json_output)
    settings = get_settings()
    token_state = "configured" if settings.has_token else "not configured"
    out.key_values(
        version_line(),
        [
            ("Version", package_version()),
            ("Config dir", str(settings.config_dir)),
            ("Database", str(settings.db_path)),
            ("Token", token_state),
        ],
        data={
            "version": package_version(),
            "config_dir": str(settings.config_dir),
            "database": str(settings.db_path),
            "token_configured": settings.has_token,
        },
    )
