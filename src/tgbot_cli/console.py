"""Output facade: styled Rich output, plain text, or JSON.

Commands never print directly; they go through the module-level ``out`` object, whose
mode is chosen once per invocation (``--plain``/``--json``, ``TGBOT_PLAIN``, ``NO_COLOR``
and whether stdout is a terminal).
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
from collections.abc import Iterator, Sequence
from enum import StrEnum
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .errors import TgbotError


class Mode(StrEnum):
    RICH = "rich"
    PLAIN = "plain"
    JSON = "json"


def emit_json(obj: Any, *, err: bool = False) -> None:
    """Write one JSON document (and a newline) to stdout, or stderr with ``err=True``."""
    stream = sys.stderr if err else sys.stdout
    stream.write(json.dumps(obj, ensure_ascii=False) + "\n")
    stream.flush()


def _plain_requested(plain: bool) -> bool:
    if plain or "NO_COLOR" in os.environ:
        return True
    try:
        return not sys.stdout.isatty()
    except (AttributeError, ValueError):
        return True


class Output:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.mode = Mode.RICH
        self._secrets: set[str] = set()
        # ``file=None`` makes Rich resolve sys.stdout/sys.stderr at print time.
        self._console = Console(highlight=False)
        self._err_console = Console(stderr=True, highlight=False)

    def configure(self, *, plain: bool = False, json_output: bool = False) -> None:
        if json_output or self.mode is Mode.JSON:
            self.mode = Mode.JSON
        elif _plain_requested(plain):
            self.mode = Mode.PLAIN
        else:
            self.mode = Mode.RICH

    def use_json(self, enabled: bool) -> None:
        if enabled:
            self.mode = Mode.JSON

    @property
    def is_json(self) -> bool:
        return self.mode is Mode.JSON

    def register_secret(self, secret: str) -> None:
        if secret:
            self._secrets.add(secret)

    def scrub(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, "***")
        return text

    # ------------------------------------------------------------------ results
    def success(self, message: str, data: Any = None) -> None:
        """Report a successful action. In JSON mode only ``data`` is written."""
        if self.mode is Mode.JSON:
            emit_json(data if data is not None else {"ok": True, "message": message})
        elif self.mode is Mode.PLAIN:
            print(message, flush=True)
        else:
            self._console.print(
                Panel(Text(message), title="[bold green]✓ Done", border_style="green")
            )

    def value(self, text: str, data: Any = None) -> None:
        """Print a bare value (e.g. a chat ID) suitable for shell capture."""
        if self.mode is Mode.JSON:
            emit_json(data if data is not None else text)
        else:
            print(text, flush=True)

    def notice(self, message: str) -> None:
        """Informational side note; goes to stderr so stdout stays parseable."""
        if self.mode is Mode.JSON:
            return
        if self.mode is Mode.PLAIN:
            print(message, file=sys.stderr, flush=True)
        else:
            self._err_console.print(Text(message, style="yellow"))

    def info(self, message: str) -> None:
        if self.mode is Mode.JSON:
            return
        if self.mode is Mode.PLAIN:
            print(message, flush=True)
        else:
            self._console.print(Text(message))

    def key_values(self, title: str, rows: Sequence[tuple[str, str]], data: Any) -> None:
        if self.mode is Mode.JSON:
            emit_json(data)
        elif self.mode is Mode.PLAIN:
            for label, val in rows:
                print(f"{label}: {val}", flush=True)
        else:
            grid = Table.grid(padding=(0, 2))
            grid.add_column(style="bold cyan", justify="right")
            grid.add_column()
            for label, val in rows:
                grid.add_row(label, Text(val))
            self._console.print(Panel(grid, title=f"[bold green]{title}", border_style="green"))

    def table(
        self,
        title: str,
        columns: Sequence[str],
        rows: Sequence[Sequence[str]],
        data: Any,
    ) -> None:
        if self.mode is Mode.JSON:
            emit_json(data)
        elif self.mode is Mode.PLAIN:
            for row in rows:
                print("\t".join(row), flush=True)
        else:
            table = Table(title=title, header_style="bold cyan")
            for index, column in enumerate(columns):
                table.add_column(column, style="bold" if index == 0 else None)
            for row in rows:
                table.add_row(*(Text(cell) for cell in row))
            self._console.print(table)

    @contextlib.contextmanager
    def status(self, message: str) -> Iterator[None]:
        if self.mode is Mode.RICH:
            with self._err_console.status(message, spinner="dots"):
                yield
        else:
            yield

    # ------------------------------------------------------------------- errors
    def error(self, exc: TgbotError | str, *, code: int | None = None) -> None:
        if isinstance(exc, TgbotError):
            message, hint, exit_code = exc.message, exc.hint, exc.exit_code
        else:
            message, hint, exit_code = exc, None, 1
        if code is not None:
            exit_code = code
        message = self.scrub(message)
        hint = self.scrub(hint) if hint else None

        if self.mode is Mode.JSON:
            payload: dict[str, Any] = {"ok": False, "error": message, "code": exit_code}
            if hint:
                payload["hint"] = hint
            emit_json(payload, err=True)
        elif self.mode is Mode.PLAIN:
            print(f"Error: {message}", file=sys.stderr, flush=True)
            if hint:
                print(f"Hint: {hint}", file=sys.stderr, flush=True)
        else:
            body = Text(message)
            if hint:
                body.append("\n" + hint, style="dim")
            self._err_console.print(Panel(body, title="[bold red]✗ Error", border_style="red"))


out = Output()
