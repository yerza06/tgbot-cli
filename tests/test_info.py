from .conftest import SECRET_KEY, TOKEN


def test_version_shows_paths_and_bots(cli, add_bot, write_config, config_dir):
    add_bot("news", TOKEN)
    add_bot("alerts", "2:ALERTS")
    write_config(default_bot="news", default_chat="me")
    result = cli("version")
    assert result.exit_code == 0
    assert f"Config dir: {config_dir}" in result.stdout
    assert f"Config file: {config_dir / 'config.toml'}" in result.stdout
    assert f"Database: {config_dir / 'tgbot.db'}" in result.stdout
    assert "Saved bots: 2" in result.stdout
    assert "Default bot: news" in result.stdout
    assert "Default chat: me" in result.stdout
    assert TOKEN not in result.stdout
    assert SECRET_KEY not in result.stdout


def test_version_without_bots(cli, config_dir):
    result = cli("version")
    assert "Saved bots: 0" in result.stdout
    assert "Default bot: —" in result.stdout
    assert not (config_dir / ".env").exists()


def test_version_json(cli, token):
    result = cli("version", "--json")
    payload = result.json()
    assert payload["bots"] == 1
    assert payload["default_bot"] == "test"
    assert TOKEN not in result.stdout
    assert SECRET_KEY not in result.stdout
