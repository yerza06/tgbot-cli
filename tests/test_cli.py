import json

import typer

from tgbot_cli import cli as cli_module
from tgbot_cli.errors import ConfigError


def _add_command(monkeypatch, func):
    app = typer.Typer()
    app.callback()(lambda: None)
    app.command("boom")(func)
    monkeypatch.setattr(cli_module, "app", app)


def test_version_flag(cli):
    result = cli("--version")
    assert result.exit_code == 0
    assert result.stdout.startswith("tgbot ")


def test_config_error_exit_code(cli, monkeypatch):
    def boom() -> None:
        raise ConfigError("nope")

    _add_command(monkeypatch, boom)
    result = cli("boom")
    assert result.exit_code == 3
    assert "Error: nope" in result.stderr


def test_unexpected_error_is_one_line_without_traceback(cli, monkeypatch):
    def boom() -> None:
        raise RuntimeError("kaput")

    _add_command(monkeypatch, boom)
    result = cli("boom")
    assert result.exit_code == 1
    assert "Traceback" not in result.stderr
    assert result.stderr.strip() == "Error: Unexpected error: RuntimeError: kaput"


def test_keyboard_interrupt_exits_130(cli, monkeypatch):
    def boom() -> None:
        raise KeyboardInterrupt

    _add_command(monkeypatch, boom)
    assert cli("boom").exit_code == 130


def test_usage_error_exit_code(cli):
    result = cli("send")
    assert result.exit_code == 2
    assert "Missing argument" in result.stderr


def test_usage_error_as_json(cli):
    result = cli("send", "--json")
    assert result.exit_code == 2
    payload = json.loads(result.stderr)
    assert payload["ok"] is False
    assert payload["code"] == 2
    assert result.stdout == ""


def test_help_is_english(cli):
    result = cli("--help")
    assert "Send a text message." in result.stdout
    assert "Manage saved chat aliases" in result.stdout
