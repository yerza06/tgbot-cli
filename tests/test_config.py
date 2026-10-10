import stat

import pytest

from tgbot_cli.config import SECRET_KEY, _write_env, get_settings
from tgbot_cli.errors import ConfigError


def test_defaults(config_dir):
    settings = get_settings()
    assert settings.config_dir == config_dir
    assert settings.db_path == config_dir / "tgbot.db"
    assert settings.env_file == config_dir / ".env"
    assert settings.config_file == config_dir / "config.toml"
    assert settings.secret_key is None
    assert settings.default_bot is None
    assert settings.api_url == "https://api.telegram.org"
    assert not hasattr(settings, "bot_token")


def test_default_config_dir_is_under_home(monkeypatch, tmp_path):
    monkeypatch.delenv("TGBOT_CONFIG_DIR")
    assert get_settings().config_dir == tmp_path / "home" / ".config" / "tgbot"


def test_secret_key_from_env_file(config_dir):
    config_dir.mkdir(parents=True)
    (config_dir / ".env").write_text(f"{SECRET_KEY}=file-key\n")
    assert get_settings().secret_key.get_secret_value() == "file-key"


def test_environment_overrides_file(config_dir, monkeypatch):
    config_dir.mkdir(parents=True)
    (config_dir / ".env").write_text(f"{SECRET_KEY}=key-a\nTGBOT_DEFAULT_BOT=news\n")
    monkeypatch.setenv(SECRET_KEY, "key-b")
    monkeypatch.setenv("TGBOT_DEFAULT_BOT", "alerts")
    settings = get_settings()
    assert settings.secret_key.get_secret_value() == "key-b"
    assert settings.default_bot == "alerts"


def test_custom_config_dir(tmp_path, monkeypatch):
    other = tmp_path / "elsewhere"
    monkeypatch.setenv("TGBOT_CONFIG_DIR", str(other))
    settings = get_settings()
    _write_env(settings, {SECRET_KEY: "abc"})
    assert (other / ".env").exists()
    assert get_settings().db_path == other / "tgbot.db"


def test_write_env_merges_and_restricts_permissions(config_dir):
    config_dir.mkdir(parents=True)
    env = config_dir / ".env"
    env.write_text(f"TGBOT_TIMEOUT=10\n# comment\n{SECRET_KEY}=old\n")
    _write_env(get_settings(), {SECRET_KEY: "new-key"})

    content = env.read_text()
    assert "TGBOT_TIMEOUT=10" in content
    assert f"{SECRET_KEY}=new-key" in content
    assert "old" not in content
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    assert get_settings().timeout == 10


def test_blank_values_count_as_missing(monkeypatch):
    monkeypatch.setenv(SECRET_KEY, "   ")
    monkeypatch.setenv("TGBOT_DEFAULT_BOT", " ")
    settings = get_settings()
    assert settings.secret_key is None
    assert settings.default_bot is None


def test_legacy_token_variable_is_ignored(monkeypatch):
    monkeypatch.setenv("TGBOT_BOT_TOKEN", "123:LEGACY")
    assert "123:LEGACY" not in repr(get_settings().model_dump())


def test_invalid_setting_is_config_error(monkeypatch):
    monkeypatch.setenv("TGBOT_TIMEOUT", "soon")
    with pytest.raises(ConfigError, match="TGBOT_TIMEOUT"):
        get_settings()
