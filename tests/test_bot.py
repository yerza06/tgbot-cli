import pytest

from tgbot_cli.config import get_settings

from .conftest import TOKEN


def config_text(config_dir) -> str:
    path = config_dir / "config.toml"
    return path.read_text() if path.exists() else ""


# --------------------------------------------------------------------------- add
def test_add_saves_bot_and_becomes_default(cli, fake_tg, secret_key, config_dir):
    result = cli("bot", "add", "news", TOKEN)
    assert result.exit_code == 0, result.stderr
    assert "news" in result.stdout
    assert "@test_bot" in result.stdout
    assert TOKEN not in result.stdout + result.stderr
    assert fake_tg.methods() == ["getMe"]
    assert 'default_bot = "news"' in config_text(config_dir)


@pytest.mark.filterwarnings("ignore::getpass.GetPassWarning")  # no TTY under pytest
def test_add_prompts_when_token_omitted(cli, fake_tg, secret_key):
    result = cli("bot", "add", "news", input=f"{TOKEN}\n")
    assert result.exit_code == 0, result.stderr
    assert TOKEN not in result.stdout
    assert fake_tg.calls[0].token == TOKEN


def test_add_json_has_no_token(cli, fake_tg, secret_key):
    result = cli("bot", "add", "news", TOKEN, "--json")
    assert TOKEN not in result.stdout + result.stderr
    data = result.json()
    assert data["ok"] is True
    assert data["name"] == "news"
    assert data["bot_id"] == 42
    assert data["username"] == "test_bot"
    assert data["is_default"] is True


def test_database_contains_no_plaintext_token(cli, fake_tg, secret_key, config_dir):
    assert cli("bot", "add", "news", TOKEN).exit_code == 0
    assert cli("bot", "add", "copy", TOKEN).exit_code == 0
    raw = (config_dir / "tgbot.db").read_bytes()
    assert TOKEN.encode() not in raw


def test_invalid_token_is_not_saved(cli, fake_tg, secret_key, config_dir):
    fake_tg.queue("getMe", 401, {"ok": False, "error_code": 401, "description": "Unauthorized"})
    result = cli("bot", "add", "news", "bad:token")
    assert result.exit_code == 1
    assert "Unauthorized" in result.stderr
    assert cli("bot", "list", "--json").json() == []
    assert config_text(config_dir) == ""


def test_empty_token_is_usage_error(cli, fake_tg, secret_key):
    result = cli("bot", "add", "news", "   ")
    assert result.exit_code == 2
    assert fake_tg.calls == []


def test_add_without_key_hints_key_init(cli, fake_tg, config_dir):
    result = cli("bot", "add", "news", TOKEN)
    assert result.exit_code == 3
    assert "tgbot key init" in result.stderr
    assert fake_tg.calls == []
    assert not config_dir.exists()


def test_duplicate_alias_makes_no_request(cli, fake_tg, add_bot):
    add_bot("news", "1:A")
    result = cli("bot", "add", "news", TOKEN)
    assert result.exit_code == 3
    assert fake_tg.calls == []


def test_second_bot_keeps_default(cli, fake_tg, secret_key, config_dir):
    assert cli("bot", "add", "news", "1:A").exit_code == 0
    assert cli("bot", "add", "alerts", "2:B").exit_code == 0
    assert 'default_bot = "news"' in config_text(config_dir)


# --------------------------------------------------------------------------- default
def test_default_writes_config_and_keeps_comments(cli, add_bot, write_config, config_dir):
    add_bot("news", "1:A")
    add_bot("alerts", "2:B")
    write_config('# my settings\ntimeout = 5\ndefault_bot = "news"\n')
    result = cli("bot", "default", "alerts")
    assert result.exit_code == 0, result.stderr
    text = config_text(config_dir)
    assert 'default_bot = "alerts"' in text
    assert "# my settings" in text
    assert "timeout = 5" in text
    assert get_settings().default_bot == "alerts"


def test_default_unknown_bot(cli, add_bot, write_config, config_dir):
    add_bot("news", "1:A")
    write_config(default_bot="news")
    assert cli("bot", "default", "missing").exit_code == 3
    assert 'default_bot = "news"' in config_text(config_dir)


# --------------------------------------------------------------------------- list
def test_list_marks_default_and_hides_tokens(cli, add_bot, write_config):
    add_bot("news", "1:NEWS-TOKEN", bot_id=1, username="news_bot")
    add_bot("alerts", "2:ALERTS-TOKEN", bot_id=2, username="alerts_bot")
    write_config(default_bot="news")
    result = cli("bot", "list")
    assert result.exit_code == 0
    assert "news" in result.stdout
    assert "@alerts_bot" in result.stdout
    assert "NEWS-TOKEN" not in result.stdout
    assert "ALERTS-TOKEN" not in result.stdout


def test_list_json_shape(cli, add_bot, write_config):
    add_bot("news", "1:NEWS-TOKEN", bot_id=1, username="news_bot")
    add_bot("alerts", "2:ALERTS-TOKEN", bot_id=2)
    write_config(default_bot="news")
    result = cli("bot", "list", "--json")
    data = result.json()
    assert [b["name"] for b in data] == ["news", "alerts"]
    assert [b["is_default"] for b in data] == [True, False]
    for item in data:
        assert set(item) == {"name", "bot_id", "username", "is_default", "created_at"}
    assert "TOKEN" not in result.stdout


def test_bare_bot_lists_and_explains_when_empty(cli):
    result = cli("bot")
    assert result.exit_code == 0
    assert "tgbot bot add" in result.stdout


# --------------------------------------------------------------------------- rename / remove
def test_rename_updates_default(cli, add_bot, write_config, config_dir, fake_tg):
    add_bot("news", "1:A")
    write_config(default_bot="news")
    assert cli("bot", "rename", "news", "daily").exit_code == 0
    assert 'default_bot = "daily"' in config_text(config_dir)
    assert cli("send", "hi", "1").exit_code == 0
    assert fake_tg.calls[0].token == "1:A"


def test_rename_onto_existing(cli, add_bot):
    add_bot("news", "1:A")
    add_bot("alerts", "2:B")
    assert cli("bot", "rename", "news", "alerts").exit_code == 3


def test_remove_non_default(cli, add_bot, write_config, config_dir):
    add_bot("news", "1:A")
    add_bot("alerts", "2:B")
    write_config(default_bot="news")
    assert cli("bot", "remove", "alerts").exit_code == 0
    assert [b["name"] for b in cli("bot", "list", "--json").json()] == ["news"]
    assert 'default_bot = "news"' in config_text(config_dir)


def test_remove_default_reassigns(cli, add_bot, write_config, config_dir):
    add_bot("news", "1:A")
    add_bot("alerts", "2:B")
    write_config(default_bot="news")
    assert cli("bot", "remove", "news").exit_code == 0
    assert 'default_bot = "alerts"' in config_text(config_dir)


def test_remove_last_bot_drops_default(cli, add_bot, write_config, config_dir):
    add_bot("news", "1:A")
    write_config(default_bot="news")
    assert cli("bot", "remove", "news").exit_code == 0
    assert "default_bot" not in config_text(config_dir)


def test_remove_unknown(cli, secret_key):
    assert cli("bot", "remove", "missing").exit_code == 3


# --------------------------------------------------------------------------- whoami / legacy
def test_whoami_default(cli, fake_tg, token):
    result = cli("whoami")
    assert result.exit_code == 0
    assert "Alias: test" in result.stdout
    assert "ID: 42" in result.stdout
    assert "Username: @test_bot" in result.stdout
    assert "Name: Test Bot" in result.stdout


def test_whoami_bot_flag(cli, fake_tg, token, add_bot):
    add_bot("alerts", "2:B")
    data = cli("whoami", "--bot", "alerts", "--json").json()
    assert data["name"] == "alerts"
    assert fake_tg.calls[0].token == "2:B"


def test_token_set_is_gone(cli):
    assert cli("token", "set", TOKEN).exit_code == 2
