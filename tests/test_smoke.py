from tgbot_cli.config import get_settings


def test_help_runs(cli):
    result = cli("--help")
    assert result.exit_code == 0
    assert "Send Telegram messages as a bot" in result.stdout


def test_config_dir_is_isolated(config_dir):
    assert get_settings().config_dir == config_dir


def test_fake_telegram_records_calls(fake_tg, token):
    from tgbot_cli.telegram import BotClient

    with BotClient(token, transport=fake_tg.transport) as client:
        assert client.call("getMe")["username"] == "test_bot"
    assert fake_tg.methods() == ["getMe"]
