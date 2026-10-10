import pytest

from tgbot_cli.commands.send import pick_target, split_media_args
from tgbot_cli.errors import UsageError


@pytest.fixture
def files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ("a.pdf", "b.pdf", "a.png"):
        (tmp_path / name).write_bytes(b"x")
    return tmp_path


def test_positional_files_target_caption(files):
    assert split_media_args(["a.pdf", "b.pdf", "team", "Reports"], None, None) == (
        ["a.pdf", "b.pdf"],
        "team",
        "Reports",
    )


def test_flags(files):
    assert split_media_args(["a.png"], "me", None) == (["a.png"], "me", None)
    assert split_media_args(["a.png"], "me", "cap") == (["a.png"], "me", "cap")


def test_positional_caption_with_to_flag(files):
    assert split_media_args(["a.png", "cap"], "me", None) == (["a.png"], "me", "cap")


def test_url_is_content(files):
    url = "https://example.com/x.png"
    assert split_media_args([url, "me"], None, None) == ([url], "me", None)


def test_negative_target(files):
    assert split_media_args(["a.png", "-1001234"], None, None)[1] == "-1001234"


def test_extra_tokens(files):
    with pytest.raises(UsageError, match="extra"):
        split_media_args(["a.png", "me", "cap", "extra"], None, None)


def test_file_id_needs_flags(files):
    assert split_media_args(["CAACAgIAAxkB"], "me", None, has_caption=False) == (
        ["CAACAgIAAxkB"],
        "me",
        None,
    )
    assert split_media_args(["AgACAgIAAxkB", "BQACAgIAAxkB"], "me", "cap") == (
        ["AgACAgIAAxkB", "BQACAgIAAxkB"],
        "me",
        "cap",
    )


def test_missing_file_named(files):
    with pytest.raises(UsageError, match=r"File not found: nope\.pdf"):
        split_media_args(["nope.pdf"], "me", None)
    with pytest.raises(UsageError, match=r"File not found: nope\.pdf"):
        split_media_args(["a.pdf", "nope.pdf", "me"], None, None)


def test_no_content(files):
    with pytest.raises(UsageError, match="No media"):
        split_media_args(["me"], None, None)


def test_no_target_is_left_to_the_default_chat(files):
    assert split_media_args(["a.png"], None, None) == (["a.png"], None, None)
    assert split_media_args(["a.png"], None, "cap") == (["a.png"], None, "cap")


def test_sticker_has_no_caption(files):
    with pytest.raises(UsageError, match="extra"):
        split_media_args(["a.png", "me", "cap"], None, None, has_caption=False)


def test_pick_target():
    assert pick_target(["me"], None) == "me"
    assert pick_target([], "me") == "me"
    assert pick_target([], None) is None
    with pytest.raises(UsageError, match="extra"):
        pick_target(["me", "x"], None)
    with pytest.raises(UsageError, match="extra"):
        pick_target(["x"], "me")


# --------------------------------------------------------------------------- default chat
def test_send_without_target_uses_default_chat(cli, token, fake_tg, write_config):
    write_config(default_chat="12345")
    result = cli("send", "hi", "--json")
    assert result.exit_code == 0, result.stderr
    assert fake_tg.calls[0].params["chat_id"] == 12345


def test_media_without_target_uses_default_chat(cli, token, fake_tg, write_config, files):
    write_config(default_chat="@mychannel")
    result = cli("sendphoto", "a.png", "--caption", "cap")
    assert result.exit_code == 0, result.stderr
    call = fake_tg.calls[0]
    assert call.method == "sendPhoto"
    assert call.params["chat_id"] == "@mychannel"
    assert call.params["caption"] == "cap"


def test_default_chat_can_be_a_saved_alias(cli, token, fake_tg, write_config):
    assert cli("chat", "add", "me", "777").exit_code == 0
    write_config(default_chat="me")
    assert cli("senddice").exit_code == 0
    assert fake_tg.calls[0].params["chat_id"] == 777


def test_explicit_target_wins_over_default(cli, token, fake_tg, write_config):
    write_config(default_chat="12345")
    assert cli("send", "hi", "999").exit_code == 0
    assert fake_tg.calls[0].params["chat_id"] == 999


def test_env_default_chat_beats_file(cli, token, fake_tg, write_config, monkeypatch):
    write_config(default_chat="12345")
    monkeypatch.setenv("TGBOT_DEFAULT_CHAT", "555")
    assert cli("send", "hi").exit_code == 0
    assert fake_tg.calls[0].params["chat_id"] == 555


def test_no_target_and_no_default_is_usage_error(cli, token, fake_tg):
    result = cli("send", "hi")
    assert result.exit_code == 2
    assert "tgbot chat default" in result.stderr
    assert fake_tg.calls == []
