import io
import json
import re

import pytest

from tgbot_cli.console import Mode, Output, emit_json
from tgbot_cli.errors import ConfigError

ANSI_OR_BOX = re.compile(r"\x1b\[|[─│╭╮╰╯━┃]")


@pytest.fixture
def output() -> Output:
    return Output()


def test_non_tty_selects_plain(output):
    output.configure()  # pytest captures stdout, so it is not a terminal
    assert output.mode is Mode.PLAIN


def test_plain_flag(output, monkeypatch):
    monkeypatch.setattr("sys.stdout.isatty", lambda: True, raising=False)
    output.configure(plain=True)
    assert output.mode is Mode.PLAIN


def test_no_color_selects_plain(output, monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    output.configure()
    assert output.mode is Mode.PLAIN


def test_json_wins_and_sticks(output):
    output.configure(json_output=True)
    output.configure(plain=True)
    assert output.is_json


def test_plain_success_has_no_ansi_or_boxes(output, capsys):
    output.configure(plain=True)
    output.success("Sent 1 message to me")
    printed = capsys.readouterr().out
    assert printed == "Sent 1 message to me\n"
    assert not ANSI_OR_BOX.search(printed)


def test_rich_success_uses_panel(output, monkeypatch):
    buffer = io.StringIO()
    monkeypatch.setattr("sys.stdout", buffer)
    output.mode = Mode.RICH
    output.success("hello")
    assert "hello" in buffer.getvalue()
    assert "Done" in buffer.getvalue()


def test_json_success_writes_data_only(output, capsys):
    output.use_json(True)
    output.success("ignored", data={"ok": True, "message_ids": [1]})
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"ok": True, "message_ids": [1]}
    assert captured.err == ""


def test_json_error_goes_to_stderr(output, capsys):
    output.use_json(True)
    output.error(ConfigError("Unknown chat 'boss'.", hint="add it"))
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "ok": False,
        "error": "Unknown chat 'boss'.",
        "code": 3,
        "hint": "add it",
    }


def test_plain_error_and_hint_on_stderr(output, capsys):
    output.configure(plain=True)
    output.error(ConfigError("No bot configured.", hint="Run `tgbot bot add NAME`."))
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Error: No bot configured." in captured.err
    assert "Hint: Run `tgbot bot add NAME`." in captured.err


def test_secrets_are_scrubbed(output, capsys):
    output.configure(plain=True)
    output.register_secret("SECRET")
    output.error("boom at /botSECRET/sendMessage")
    assert "SECRET" not in capsys.readouterr().err


def test_notice_never_pollutes_stdout(output, capsys):
    output.configure(plain=True)
    output.notice("note")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "note" in captured.err


def test_emit_json_keeps_unicode(capsys):
    emit_json({"text": "Привет"})
    assert capsys.readouterr().out == '{"text": "Привет"}\n'


def _pretend_tty(monkeypatch):
    """Call inside the test body: capsys installs its stdout only for the call phase."""
    monkeypatch.setattr("sys.stdout.isatty", lambda: True, raising=False)


def _write_config(config_dir, text):
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.toml").write_text(text)


def test_color_false_in_config_selects_plain(cli, config_dir, monkeypatch):
    from tgbot_cli.console import out

    _pretend_tty(monkeypatch)

    _write_config(config_dir, "color = false\n")
    result = cli("chat", "list")
    assert result.exit_code == 0
    assert out.mode is Mode.PLAIN
    assert not ANSI_OR_BOX.search(result.stdout)


def test_color_default_keeps_rich_on_a_tty(cli, config_dir, monkeypatch):
    from tgbot_cli.console import out

    _pretend_tty(monkeypatch)

    assert cli("chat", "list").exit_code == 0
    assert out.mode is Mode.RICH


def test_color_false_does_not_affect_json(cli, config_dir, monkeypatch):
    from tgbot_cli.console import out

    _pretend_tty(monkeypatch)

    _write_config(config_dir, "color = false\n")
    result = cli("chat", "list", "--json")
    assert out.is_json
    assert result.json() == []
