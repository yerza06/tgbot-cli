from .conftest import TOKEN


def test_version_shows_paths_and_hides_token(cli, token, config_dir):
    result = cli("version")
    assert result.exit_code == 0
    assert f"Config dir: {config_dir}" in result.stdout
    assert f"Database: {config_dir / 'tgbot.db'}" in result.stdout
    assert "Token: configured" in result.stdout
    assert TOKEN not in result.stdout


def test_version_without_token(cli):
    assert "Token: not configured" in cli("version").stdout


def test_version_json(cli, token):
    payload = cli("version", "--json").json()
    assert payload["token_configured"] is True
    assert TOKEN not in str(payload)
