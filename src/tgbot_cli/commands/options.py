"""Reusable Typer option declarations."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

import typer

# Telegram group/channel IDs are negative (-100…) and coordinates can be negative.
# Without this, Click treats such tokens as unknown options.
ALLOW_NEG = {"ignore_unknown_options": True}


class ParseMode(StrEnum):
    html = "html"
    markdown = "markdown"

    @property
    def api_value(self) -> str:
        return "HTML" if self is ParseMode.html else "MarkdownV2"


JsonOpt = Annotated[bool, typer.Option("--json", help="Machine-readable JSON output.")]
ToOpt = Annotated[
    str | None,
    typer.Option("--to", help="Target: saved chat name, numeric chat ID or @channel."),
]
CaptionOpt = Annotated[str | None, typer.Option("--caption", help="Caption (max 1024 chars).")]
SilentOpt = Annotated[bool, typer.Option("--silent", help="Deliver without a notification sound.")]
ParseModeOpt = Annotated[
    ParseMode | None,
    typer.Option("--parse-mode", help="Format text as html or markdown (default: plain)."),
]
