import pytest


@pytest.fixture
def me(cli):
    assert cli("chat", "add", "me", "13342324").exit_code == 0
    return 13342324


def test_positional_text(cli, token, fake_tg, me):
    result = cli("send", "Build failed", "me")
    assert result.exit_code == 0, result.stderr
    assert fake_tg.calls[0].method == "sendMessage"
    assert fake_tg.calls[0].params == {"chat_id": me, "text": "Build failed"}
    assert "Sent 1 message to me (13342324)" in result.stdout


def test_flag_target(cli, token, fake_tg, me):
    assert cli("send", "hi", "--to", "me").exit_code == 0
    assert fake_tg.calls[0].params["chat_id"] == me


def test_numeric_and_negative_targets(cli, token, fake_tg):
    assert cli("send", "hi", "-1001234567890").exit_code == 0
    assert fake_tg.calls[0].params["chat_id"] == -1001234567890


def test_plain_text_by_default(cli, token, fake_tg, me):
    text = "*bold?* _x_ 1.2 - (a)"
    cli("send", text, "me")
    assert fake_tg.calls[0].params == {"chat_id": me, "text": text}


@pytest.mark.parametrize(("mode", "api"), [("html", "HTML"), ("markdown", "MarkdownV2")])
def test_parse_mode(cli, token, fake_tg, me, mode, api):
    cli("send", "<b>x</b>", "me", "--parse-mode", mode)
    assert fake_tg.calls[0].params["parse_mode"] == api


def test_silent(cli, token, fake_tg, me):
    cli("send", "nightly ok", "me", "--silent")
    assert fake_tg.calls[0].params["disable_notification"] is True


def test_stdin(cli, token, fake_tg, me):
    result = cli("send", "-", "me", input="deploy done\n")
    assert result.exit_code == 0
    assert fake_tg.calls[0].params["text"] == "deploy done"


def test_empty_stdin(cli, token, fake_tg, me):
    result = cli("send", "-", "me", input="")
    assert result.exit_code == 2
    assert fake_tg.calls == []


def test_long_text_split_in_order(cli, token, fake_tg, me):
    text = "\n".join(f"{i:05d}" + "y" * 90 for i in range(94))  # ~9000 chars
    result = cli("send", "-", "me", "--json", input=text)
    assert result.exit_code == 0
    texts = [call.params["text"] for call in fake_tg.calls]
    assert len(texts) == 3
    assert "\n".join(texts) == text
    assert len(result.json()["message_ids"]) == 3


def test_json_success_shape(cli, token, fake_tg, me):
    result = cli("send", "hi", "me", "--json")
    assert result.stdout == '{"ok": true, "chat_id": 13342324, "message_ids": [101]}\n'
    assert result.stderr == ""


def test_global_json_flag(cli, token, fake_tg, me):
    assert cli("--json", "send", "hi", "me").json()["ok"] is True


def test_unknown_alias_json(cli, token, fake_tg):
    result = cli("send", "hi", "boss", "--json")
    assert result.exit_code == 3
    assert result.stdout == ""
    payload = result.err_json()
    assert payload["ok"] is False
    assert payload["code"] == 3
    assert "boss" in payload["error"]
    assert fake_tg.calls == []


def test_unknown_alias_plain(cli, token, fake_tg):
    result = cli("send", "hi", "boss")
    assert result.exit_code == 3
    assert "tgbot chat add" in result.stderr


def test_no_target(cli, token, fake_tg):
    assert cli("send", "hi").exit_code == 2


def test_recipient_never_started_bot(cli, token, fake_tg, me):
    fake_tg.queue(
        "sendMessage",
        403,
        {
            "ok": False,
            "error_code": 403,
            "description": "Forbidden: bot can't initiate conversation with a user",
        },
    )
    result = cli("send", "hi", "me")
    assert result.exit_code == 1
    assert "/start" in result.stderr


def test_telegram_rejection_exit_1(cli, token, fake_tg, me):
    fake_tg.queue("sendMessage", 400, {"ok": False, "error_code": 400, "description": "Bad"})
    assert cli("send", "hi", "me").exit_code == 1


def test_plain_flag_output(cli, token, fake_tg, me):
    result = cli("--plain", "send", "hi", "me")
    assert result.stdout == "Sent 1 message to me (13342324)\n"


# --------------------------------------------------------------------------- choosing the bot
@pytest.fixture
def two_bots(add_bot, write_config):
    add_bot("news", "1:NEWS")
    add_bot("alerts", "2:ALERTS")
    write_config(default_bot="news")


def test_default_bot_from_config(cli, two_bots, fake_tg):
    assert cli("send", "hi", "1").exit_code == 0
    assert fake_tg.calls[0].token == "1:NEWS"


def test_bot_flag(cli, two_bots, fake_tg):
    assert cli("send", "hi", "1", "--bot", "alerts").exit_code == 0
    assert fake_tg.calls[0].token == "2:ALERTS"


def test_bot_from_environment(cli, two_bots, fake_tg, monkeypatch):
    monkeypatch.setenv("TGBOT_DEFAULT_BOT", "alerts")
    assert cli("send", "hi", "1").exit_code == 0
    assert fake_tg.calls[0].token == "2:ALERTS"


def test_unknown_bot_flag(cli, two_bots, fake_tg):
    result = cli("send", "hi", "1", "--bot", "missing")
    assert result.exit_code == 3
    assert "missing" in result.stderr
    assert "tgbot bot list" in result.stderr
    assert fake_tg.calls == []


def test_no_bots_saved(cli, fake_tg):
    result = cli("send", "hi", "123")
    assert result.exit_code == 3
    assert "tgbot bot add" in result.stderr
    assert fake_tg.calls == []


def test_legacy_token_variable_is_ignored(cli, fake_tg, monkeypatch):
    monkeypatch.setenv("TGBOT_BOT_TOKEN", "123:LEGACY")
    result = cli("send", "hi", "123")
    assert result.exit_code == 3
    assert "tgbot bot add" in result.stderr
    assert fake_tg.calls == []


def test_removed_key_fails_without_request(cli, two_bots, fake_tg, monkeypatch, config_dir):
    monkeypatch.delenv("TGBOT_SECRET_KEY")
    result = cli("send", "hi", "1")
    assert result.exit_code == 3
    assert "key" in result.stderr.lower()
    assert fake_tg.calls == []
    assert not (config_dir / ".env").exists()


def test_wrong_key_fails_without_request(cli, two_bots, fake_tg, monkeypatch):
    from tgbot_cli.crypto import generate_key

    monkeypatch.setenv("TGBOT_SECRET_KEY", generate_key())
    result = cli("send", "hi", "1")
    assert result.exit_code == 3
    assert "decrypt" in result.stderr
    assert "1:NEWS" not in result.stderr
    assert fake_tg.calls == []
