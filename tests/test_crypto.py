import pytest
from cryptography.fernet import Fernet

from tgbot_cli import crypto
from tgbot_cli.config import get_settings
from tgbot_cli.errors import ConfigError

TOKEN = "123456:SECRET-TOKEN"


def test_round_trip(monkeypatch):
    monkeypatch.setenv("TGBOT_SECRET_KEY", crypto.generate_key())
    fernet = crypto.load_key(get_settings())
    blob = crypto.encrypt(fernet, TOKEN)
    assert TOKEN.encode() not in blob
    assert crypto.decrypt(fernet, blob, bot="news") == TOKEN


def test_same_token_encrypts_differently():
    fernet = Fernet(crypto.generate_key())
    assert crypto.encrypt(fernet, TOKEN) != crypto.encrypt(fernet, TOKEN)


def test_env_key_beats_dotenv_key(config_dir, monkeypatch):
    env_key, file_key = crypto.generate_key(), crypto.generate_key()
    config_dir.mkdir(parents=True)
    (config_dir / ".env").write_text(f"TGBOT_SECRET_KEY={file_key}\n")
    assert crypto.load_key(get_settings())  # from .env

    monkeypatch.setenv("TGBOT_SECRET_KEY", env_key)
    blob = Fernet(env_key).encrypt(b"x")
    assert crypto.decrypt(crypto.load_key(get_settings()), blob, bot="b") == "x"


def test_missing_key_hints_key_init_and_creates_nothing(config_dir):
    with pytest.raises(ConfigError) as excinfo:
        crypto.load_key(get_settings())
    assert excinfo.value.exit_code == 3
    assert "tgbot key init" in excinfo.value.hint
    assert not config_dir.exists()


def test_malformed_key_is_not_echoed(monkeypatch):
    monkeypatch.setenv("TGBOT_SECRET_KEY", "not-a-real-key")
    with pytest.raises(ConfigError) as excinfo:
        crypto.load_key(get_settings())
    assert "not-a-real-key" not in excinfo.value.message
    assert "not-a-real-key" not in (excinfo.value.hint or "")


def test_wrong_key_cannot_decrypt(monkeypatch):
    key_a, key_b = crypto.generate_key(), crypto.generate_key()
    blob = crypto.encrypt(Fernet(key_a), TOKEN)
    monkeypatch.setenv("TGBOT_SECRET_KEY", key_b)
    with pytest.raises(ConfigError) as excinfo:
        crypto.decrypt(crypto.load_key(get_settings()), blob, bot="news")
    text = excinfo.value.message + (excinfo.value.hint or "")
    assert "news" in excinfo.value.message
    assert TOKEN not in text
    assert key_a not in text
    assert key_b not in text
