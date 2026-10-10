import stat

import pytest

from tgbot_cli.config import get_settings

from .conftest import TOKEN


def test_token_set_saves_valid_token(cli, fake_tg, config_dir):
    result = cli("token", "set", TOKEN)
    assert result.exit_code == 0, result.stderr
    assert "@test_bot" in result.stdout
    assert TOKEN not in result.stdout
    env = config_dir / ".env"
    assert f"TGBOT_BOT_TOKEN={TOKEN}" in env.read_text()
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    assert fake_tg.methods() == ["getMe"]


@pytest.mark.filterwarnings("ignore::getpass.GetPassWarning")  # no TTY under pytest
def test_token_set_prompts_when_omitted(cli, fake_tg):
    result = cli("token", "set", input=f"{TOKEN}\n")
    assert result.exit_code == 0, result.stderr
    assert TOKEN not in result.stdout
    assert get_settings().require_token() == TOKEN


def test_invalid_token_is_not_saved(cli, fake_tg, config_dir):
    fake_tg.queue("getMe", 401, {"ok": False, "error_code": 401, "description": "Unauthorized"})
    result = cli("token", "set", "bad:token")
    assert result.exit_code == 1
    assert "Unauthorized" in result.stderr
    assert not (config_dir / ".env").exists()


def test_token_set_json(cli, fake_tg):
    result = cli("token", "set", TOKEN, "--json")
    assert result.json() == {"ok": True, "id": 42, "username": "test_bot"}


def test_whoami(cli, fake_tg, token):
    result = cli("whoami")
    assert result.exit_code == 0
    assert "ID: 42" in result.stdout
    assert "Username: @test_bot" in result.stdout
    assert "Name: Test Bot" in result.stdout


def test_whoami_json(cli, fake_tg, token):
    assert cli("whoami", "--json").json()["username"] == "test_bot"


def test_missing_token_makes_no_request(cli, fake_tg):
    result = cli("send", "hi", "123")
    assert result.exit_code == 3
    assert "tgbot token set" in result.stderr
    assert "TGBOT_BOT_TOKEN" in result.stderr
    assert fake_tg.calls == []


def test_whoami_without_token(cli, fake_tg):
    assert cli("whoami").exit_code == 3
    assert fake_tg.calls == []
