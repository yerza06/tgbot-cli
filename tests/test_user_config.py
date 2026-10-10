"""config.toml: preference keys, precedence against env/.env, errors and updates."""

import pytest

from tgbot_cli.config import get_settings, update_config
from tgbot_cli.errors import ConfigError


def write(config_dir, name, text):
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / name).write_text(text)


def test_values_from_config_file(config_dir):
    write(config_dir, "config.toml", 'timeout = 5\napi_url = "http://localhost:8081"\n')
    settings = get_settings()
    assert settings.timeout == 5
    assert settings.api_url == "http://localhost:8081"
    assert settings.config_file == config_dir / "config.toml"


def test_missing_file_uses_defaults_and_creates_nothing(config_dir):
    settings = get_settings()
    assert settings.default_bot is None
    assert settings.default_chat is None
    assert settings.color is True
    assert not settings.config_file.exists()


def test_env_and_dotenv_override_file(config_dir, monkeypatch):
    write(config_dir, "config.toml", 'default_chat = "me"\ndefault_bot = "news"\ntimeout = 5\n')
    write(config_dir, ".env", "TGBOT_DEFAULT_BOT=alerts\n")
    monkeypatch.setenv("TGBOT_DEFAULT_CHAT", "team")
    settings = get_settings()
    assert settings.default_chat == "team"
    assert settings.default_bot == "alerts"
    assert settings.timeout == 5


def test_custom_config_dir_moves_the_file(tmp_path, monkeypatch):
    other = tmp_path / "elsewhere"
    write(other, "config.toml", 'default_chat = "me"\n')
    monkeypatch.setenv("TGBOT_CONFIG_DIR", str(other))
    assert get_settings().default_chat == "me"


def test_broken_toml_names_the_file(config_dir):
    write(config_dir, "config.toml", "default_bot = \n")
    with pytest.raises(ConfigError) as excinfo:
        get_settings()
    assert str(config_dir / "config.toml") in excinfo.value.message
    assert excinfo.value.exit_code == 3


def test_wrong_value_type_names_the_key(config_dir):
    write(config_dir, "config.toml", 'timeout = "soon"\n')
    with pytest.raises(ConfigError, match="timeout"):
        get_settings()


def test_secret_key_and_unknown_keys_in_toml_are_ignored(config_dir):
    write(config_dir, "config.toml", 'secret_key = "abc"\nwhatever = 1\nplain = true\n')
    settings = get_settings()
    assert settings.secret_key is None
    assert settings.plain is False


def test_update_creates_file(config_dir):
    settings = get_settings()
    update_config(settings, default_bot="news")
    assert 'default_bot = "news"' in settings.config_file.read_text()
    assert settings.default_bot == "news"
    assert get_settings().default_bot == "news"


def test_update_keeps_comments_and_other_keys(config_dir):
    write(config_dir, "config.toml", '# my settings\ntimeout = 5\ndefault_bot = "news"\n')
    update_config(get_settings(), default_bot="alerts")
    text = (config_dir / "config.toml").read_text()
    assert "# my settings" in text
    assert "timeout = 5" in text
    assert 'default_bot = "alerts"' in text
    assert "news" not in text


def test_update_removes_key(config_dir):
    write(config_dir, "config.toml", 'default_bot = "news"\ncolor = false\n')
    update_config(get_settings(), default_bot=None)
    text = (config_dir / "config.toml").read_text()
    assert "default_bot" not in text
    assert "color = false" in text
