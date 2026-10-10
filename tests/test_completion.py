"""Shell completion: saved chat/bot aliases, options after `-`, read-only behaviour."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest

from tgbot_cli import db
from tgbot_cli.cli import run
from tgbot_cli.commands.send import DICE_EMOJI
from tgbot_cli.completion import complete_bot, complete_chat
from tgbot_cli.config import get_settings

MEDIA_COMMANDS = [
    "sendphoto",
    "sendfile",
    "sendvideo",
    "sendaudio",
    "sendvoice",
    "sendanimation",
    "sendvideonote",
    "sendsticker",
]


@pytest.fixture
def chats(config_dir: Path) -> None:
    with db.open_db(get_settings().db_path) as conn:
        db.add_chat(conn, "me", "13342324")
        db.add_chat(conn, "team", "-1001234567890", "Dev team")


@pytest.fixture
def bots(add_bot: Callable[..., None]) -> None:
    add_bot("main", "1:A", bot_id=1, username="main_bot")
    add_bot("alerts", "2:B", bot_id=2)


@pytest.fixture
def complete(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> Callable[[str], str]:
    """Run zsh completion for a command line, as the generated script does."""

    def invoke(line: str) -> str:
        monkeypatch.setenv("_TGBOT_COMPLETE", "complete_zsh")
        monkeypatch.setenv("_TYPER_COMPLETE_ARGS", line)
        capsys.readouterr()
        with pytest.raises(SystemExit) as exc:
            run([])
        captured = capsys.readouterr()
        assert exc.value.code == 0
        assert captured.err == ""
        return captured.out

    return invoke


def values(output: str) -> list[str]:
    """Suggested values from Typer's zsh `_arguments` output (`[]` for `_files`)."""
    return re.findall(r'^\(?\(?"([^"]+)"', output.split("((", 1)[-1], flags=re.M)


# --------------------------------------------------------------------------- #
# Completer functions
# --------------------------------------------------------------------------- #
def test_chats_with_descriptions(chats):
    assert complete_chat("") == [("me", "13342324"), ("team", "-1001234567890 · Dev team")]
    assert complete_chat("t") == [("team", "-1001234567890 · Dev team")]


def test_bots_with_descriptions(bots):
    assert complete_bot("") == [("main", "@main_bot"), ("alerts", "2")]
    assert complete_bot("a") == [("alerts", "2")]


def test_missing_config_dir_creates_nothing(config_dir):
    assert complete_chat("") == []
    assert complete_bot("") == []
    assert not config_dir.exists()


def test_broken_config_gives_no_suggestions(chats, write_config):
    write_config("not = [valid toml")
    assert complete_chat("") == []


def test_bots_without_secret_key(bots, monkeypatch):
    monkeypatch.delenv("TGBOT_SECRET_KEY")
    assert [name for name, _ in complete_bot("")] == ["main", "alerts"]


def test_database_is_not_modified(chats, bots):
    path = get_settings().db_path
    before = path.stat()
    complete_chat("")
    complete_bot("")
    after = path.stat()
    assert (after.st_mtime_ns, after.st_size) == (before.st_mtime_ns, before.st_size)


# --------------------------------------------------------------------------- #
# End-to-end through the zsh completion protocol
# --------------------------------------------------------------------------- #
def test_send_target(chats, complete):
    assert values(complete('tgbot send "hi" ')) == ["me", "team"]


def test_to_option_filters_by_prefix(chats, complete):
    assert values(complete('tgbot send "hi" --to t')) == ["team"]


def test_senddice_target(chats, complete):
    assert values(complete("tgbot senddice ")) == ["me", "team"]


@pytest.mark.parametrize("line", ['tgbot send "hi" me --bot ', "tgbot whoami --bot "])
def test_bot_option(bots, complete, line):
    output = complete(line)
    assert values(output) == ["main", "alerts"]
    assert "@main_bot" in output


@pytest.mark.parametrize("command", MEDIA_COMMANDS)
def test_media_first_argument_is_a_file(chats, complete, command):
    assert complete(f"tgbot {command} ").strip() == "_files"


@pytest.mark.parametrize("command", MEDIA_COMMANDS)
def test_media_target_after_file(chats, complete, command):
    assert values(complete(f"tgbot {command} shot.png m")) == ["me"]


def test_media_path_prefix_falls_back_to_files(chats, complete):
    assert complete("tgbot sendphoto shot.png ./").strip() == "_files"


def test_chat_management_names(chats, complete):
    assert values(complete("tgbot chat remove ")) == ["me", "team"]
    assert values(complete("tgbot chat rename t")) == ["team"]


def test_bot_management_names(bots, complete):
    assert values(complete("tgbot bot default a")) == ["alerts"]


@pytest.mark.parametrize("line", ["tgbot chat add ", "tgbot chat rename team "])
def test_new_names_are_not_completed(chats, complete, line):
    assert values(complete(line)) == []


def test_no_suggestions_without_database(config_dir, complete):
    assert complete('tgbot send "hi" ').strip() == "_files"
    assert not config_dir.exists()


# --------------------------------------------------------------------------- #
# Commands, options and fixed values
# --------------------------------------------------------------------------- #
def test_command_prefix(complete):
    output = complete("tgbot cha")
    assert values(output) == ["chat"]
    assert "Manage saved chat aliases" in output


def test_chat_subcommands(complete):
    assert set(values(complete("tgbot chat "))) >= {
        "add",
        "list",
        "get-id",
        "default",
        "replace-id",
        "rename",
        "remove",
    }


def test_global_options(complete):
    output = complete("tgbot -")
    assert {"--plain", "--json", "--version", "--help"} <= set(values(output))
    assert "Machine-readable JSON output." in output


def test_options_win_over_aliases(chats, complete):
    suggested = values(complete('tgbot send "hi" -'))
    assert {"--to", "--bot", "--parse-mode", "--silent", "--json"} <= set(suggested)
    assert "me" not in suggested


def test_options_after_media_file(chats, complete):
    suggested = values(complete("tgbot sendphoto shot.png -"))
    assert {"--caption", "--to"} <= set(suggested)


def test_chat_add_options(complete):
    assert "--no-resolve" in values(complete("tgbot chat add -"))


def test_parse_mode_values(complete):
    assert values(complete('tgbot send "hi" me --parse-mode ')) == ["html", "markdown"]


def test_dice_emoji_values(complete):
    output = complete("tgbot senddice --emoji ")
    assert values(output) == list(DICE_EMOJI)
    assert "_files" not in output


def test_show_completion_zsh(capsys):
    with pytest.raises(SystemExit) as exc:
        run(["--show-completion", "zsh"])
    script = capsys.readouterr().out
    assert exc.value.code == 0
    assert "compdef" in script
    assert "_TGBOT_COMPLETE" in script
