"""Encryption key management: ``tgbot key init``."""

from __future__ import annotations

import os
from typing import Annotated

import typer

from .. import crypto, db
from ..config import SECRET_KEY, _write_env, get_settings
from ..console import out
from ..errors import ConfigError
from .options import JsonOpt

app = typer.Typer(help="Manage the key that encrypts saved bot tokens.", no_args_is_help=True)


@app.command("init")
def init(
    force: Annotated[
        bool,
        typer.Option("--force", help="Replace an existing key (saved bots must be re-added)."),
    ] = False,
    json_output: JsonOpt = False,
) -> None:
    """Generate a new key and save it as TGBOT_SECRET_KEY in <config_dir>/.env."""
    out.use_json(json_output)
    settings = get_settings()
    if settings.secret_key is not None and not force:
        raise ConfigError(
            f"{SECRET_KEY} is already configured.",
            hint="Use `tgbot key init --force` to replace it; saved bots then must be re-added.",
        )

    warnings: list[str] = []
    if settings.secret_key is not None:
        with db.open_db(settings.db_path) as conn:
            saved = len(db.list_bots(conn))
        if saved:
            noun = "bot" if saved == 1 else "bots"
            warnings.append(
                f"{saved} saved {noun} can no longer be decrypted; "
                "re-add them with `tgbot bot add`."
            )
        if os.environ.get(SECRET_KEY, "").strip():
            warnings.append(
                f"{SECRET_KEY} is also set in the environment and still takes precedence."
            )

    _write_env(settings, {SECRET_KEY: crypto.generate_key()})
    for warning in warnings:
        out.notice(warning)
    out.success(
        f"Encryption key saved to {settings.env_file}",
        data={"ok": True, "path": str(settings.env_file), "warnings": warnings},
    )
