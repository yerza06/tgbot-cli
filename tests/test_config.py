import stat

import pytest

from tgbot_cli.config import TOKEN_KEY, get_settings, save_token
from tgbot_cli.errors import ConfigError


def test_defaults(config_dir):
    settings = get_settings()
    assert settings.config_dir == config_dir
    assert settings.db_path == config_dir / "tgbot.db"
    assert settings.env_file == config_dir / ".env"
    assert settings.bot_token is None
    assert settings.api_url == "https://api.telegram.org"


def test_default_config_dir_is_under_home(monkeypatch, tmp_path):
    monkeypatch.delenv("TGBOT_CONFIG_DIR")
    assert get_settings().config_dir == tmp_path / "home" / ".config" / "tgbot"


def test_token_from_env_file(config_dir):
    config_dir.mkdir(parents=True)
    (config_dir / ".env").write_text(f"{TOKEN_KEY}=file-token\n")
    assert get_settings().require_token() == "file-token"


def test_environment_overrides_file(config_dir, monkeypatch):
    config_dir.mkdir(parents=True)
    (config_dir / ".env").write_text(f"{TOKEN_KEY}=token-a\n")
    monkeypatch.setenv(TOKEN_KEY, "token-b")
    assert get_settings().require_token() == "token-b"


def test_custom_config_dir(tmp_path, monkeypatch):
    other = tmp_path / "elsewhere"
    monkeypatch.setenv("TGBOT_CONFIG_DIR", str(other))
    settings = get_settings()
    save_token(settings, "abc")
    assert (other / ".env").exists()
    assert get_settings().db_path == other / "tgbot.db"


def test_save_token_merges_and_restricts_permissions(config_dir):
    config_dir.mkdir(parents=True)
    env = config_dir / ".env"
    env.write_text("TGBOT_TIMEOUT=10\n# comment\nTGBOT_BOT_TOKEN=old\n")
    settings = get_settings()
    save_token(settings, "new-token")

    content = env.read_text()
    assert "TGBOT_TIMEOUT=10" in content
    assert "TGBOT_BOT_TOKEN=new-token" in content
    assert "old" not in content
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    assert settings.require_token() == "new-token"
    assert get_settings().timeout == 10


def test_missing_token_error_explains_how_to_fix():
    with pytest.raises(ConfigError) as excinfo:
        get_settings().require_token()
    assert "tgbot token set" in excinfo.value.hint
    assert TOKEN_KEY in excinfo.value.hint


def test_blank_token_counts_as_missing(monkeypatch):
    monkeypatch.setenv(TOKEN_KEY, "   ")
    assert not get_settings().has_token


def test_invalid_setting_is_config_error(monkeypatch):
    monkeypatch.setenv("TGBOT_TIMEOUT", "soon")
    with pytest.raises(ConfigError, match="TGBOT_TIMEOUT"):
        get_settings()
