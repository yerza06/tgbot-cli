"""Shared fixtures: isolated config dir, fake Telegram API and a CLI runner."""

from __future__ import annotations

import io
import json
import sys
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from email.parser import BytesParser
from email.policy import default as default_policy
from pathlib import Path
from typing import Any

import httpx
import pytest

from tgbot_cli import telegram
from tgbot_cli.cli import run

TOKEN = "123456:TEST-SECRET-TOKEN"


@dataclass
class Part:
    value: bytes
    filename: str | None = None


@dataclass
class Call:
    method: str
    params: dict[str, Any]
    files: dict[str, Part] = field(default_factory=dict)


def _parse_multipart(request: httpx.Request) -> tuple[dict[str, Any], dict[str, Part]]:
    header = f"Content-Type: {request.headers['content-type']}\r\n\r\n".encode()
    message = BytesParser(policy=default_policy).parsebytes(header + request.content)
    params: dict[str, Any] = {}
    files: dict[str, Part] = {}
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        payload = part.get_payload(decode=True) or b""
        filename = part.get_filename()
        if filename is not None:
            files[name] = Part(payload, filename)
        else:
            text = payload.decode()
            try:
                params[name] = json.loads(text) if text[:1] in "[{" else text
            except ValueError:
                params[name] = text
    return params, files


class FakeTelegram:
    """Records Bot API calls and answers them with plausible results."""

    def __init__(self) -> None:
        self.calls: list[Call] = []
        self._queued: deque[tuple[str, int, dict[str, Any]]] = deque()
        self._next_id = 100
        self.transport = httpx.MockTransport(self.handler)

    def queue(self, method: str, status: int, payload: dict[str, Any]) -> None:
        """Answer the next call of ``method`` with ``payload`` (one-shot)."""
        self._queued.append((method, status, payload))

    def methods(self) -> list[str]:
        return [call.method for call in self.calls]

    def _message(self) -> dict[str, Any]:
        self._next_id += 1
        return {"message_id": self._next_id}

    def _default(self, call: Call) -> Any:
        if call.method == "getMe":
            return {"id": 42, "is_bot": True, "first_name": "Test Bot", "username": "test_bot"}
        if call.method == "getChat":
            return {"id": -1001234567890, "title": "My Channel", "type": "channel"}
        if call.method == "sendMediaGroup":
            return [self._message() for _ in call.params["media"]]
        return self._message()

    def handler(self, request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        if request.headers.get("content-type", "").startswith("multipart/form-data"):
            params, files = _parse_multipart(request)
        else:
            params, files = (json.loads(request.content) if request.content else {}), {}
        call = Call(method, params, files)
        self.calls.append(call)

        for index, (queued_method, status, payload) in enumerate(self._queued):
            if queued_method == method:
                del self._queued[index]
                return httpx.Response(status, json=payload)
        return httpx.Response(200, json={"ok": True, "result": self._default(call)})


@dataclass
class Result:
    exit_code: int
    stdout: str
    stderr: str

    def json(self) -> Any:
        return json.loads(self.stdout)

    def err_json(self) -> Any:
        return json.loads(self.stderr)


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every test gets its own HOME/config dir and a clean TGBOT_* environment."""
    import os

    for key in list(os.environ):
        if key.startswith("TGBOT_") or key == "NO_COLOR":
            monkeypatch.delenv(key)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    config_dir = tmp_path / "config"
    monkeypatch.setenv("TGBOT_CONFIG_DIR", str(config_dir))
    monkeypatch.setattr(telegram, "TRANSPORT", None)
    return config_dir


@pytest.fixture
def config_dir(isolated_env: Path) -> Path:
    return isolated_env


@pytest.fixture
def token(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("TGBOT_BOT_TOKEN", TOKEN)
    return TOKEN


@pytest.fixture
def fake_tg(monkeypatch: pytest.MonkeyPatch) -> FakeTelegram:
    fake = FakeTelegram()
    monkeypatch.setattr(telegram, "TRANSPORT", fake.transport)
    return fake


@pytest.fixture
def cli(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> Callable[..., Result]:
    """Run ``tgbot`` in-process: ``cli("send", "hi", "me", input="...")``."""

    def invoke(*args: str, input: str | None = None) -> Result:
        capsys.readouterr()
        monkeypatch.setattr(sys, "stdin", io.StringIO(input or ""))
        code = run(list(args))
        captured = capsys.readouterr()
        return Result(code, captured.out, captured.err)

    return invoke
