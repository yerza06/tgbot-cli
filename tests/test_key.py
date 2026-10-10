import stat

from cryptography.fernet import Fernet

from tgbot_cli import crypto, db
from tgbot_cli.config import get_settings


def _env_key(config_dir) -> str:
    for line in (config_dir / ".env").read_text().splitlines():
        if line.startswith("TGBOT_SECRET_KEY="):
            return line.partition("=")[2]
    raise AssertionError("no key in .env")


def test_init_creates_key_in_env_file(cli, config_dir):
    result = cli("key", "init")
    assert result.exit_code == 0, result.stderr
    env = config_dir / ".env"
    key = _env_key(config_dir)
    Fernet(key)  # a valid key
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    assert str(env) in result.stdout
    assert key not in result.stdout + result.stderr
    assert get_settings().secret_key.get_secret_value() == key


def test_init_preserves_other_lines(cli, config_dir):
    config_dir.mkdir(parents=True)
    (config_dir / ".env").write_text("TGBOT_TIMEOUT=10\nTGBOT_PLAIN=true\n")
    assert cli("key", "init").exit_code == 0
    content = (config_dir / ".env").read_text()
    assert "TGBOT_TIMEOUT=10" in content
    assert "TGBOT_PLAIN=true" in content


def test_init_json_does_not_print_key(cli, config_dir):
    result = cli("key", "init", "--json")
    data = result.json()
    assert data["ok"] is True
    assert data["path"] == str(config_dir / ".env")
    assert _env_key(config_dir) not in result.stdout


def test_init_refuses_when_key_in_env_file(cli, config_dir):
    assert cli("key", "init").exit_code == 0
    before = (config_dir / ".env").read_text()
    result = cli("key", "init")
    assert result.exit_code == 3
    assert "--force" in result.stderr
    assert (config_dir / ".env").read_text() == before


def test_init_refuses_when_key_in_environment(cli, config_dir, monkeypatch):
    monkeypatch.setenv("TGBOT_SECRET_KEY", crypto.generate_key())
    result = cli("key", "init")
    assert result.exit_code == 3
    assert not (config_dir / ".env").exists()


def test_force_replaces_key_and_warns_about_saved_bots(cli, config_dir):
    assert cli("key", "init").exit_code == 0
    old = _env_key(config_dir)
    settings = get_settings()
    fernet = crypto.load_key(settings)
    with db.open_db(settings.db_path) as conn:
        db.add_bot(conn, "news", crypto.encrypt(fernet, "1:A"), 1, None)
        db.add_bot(conn, "alerts", crypto.encrypt(fernet, "2:B"), 2, None)

    result = cli("key", "init", "--force")
    assert result.exit_code == 0
    assert _env_key(config_dir) != old
    assert "2 saved bots" in result.stderr

    data = cli("key", "init", "--force", "--json").json()
    assert any("2 saved bots" in w for w in data["warnings"])
