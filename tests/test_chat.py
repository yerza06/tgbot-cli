def test_add_user_alias(cli):
    result = cli("chat", "add", "me", "13342324")
    assert result.exit_code == 0, result.stderr
    assert "Added 'me' -> 13342324" in result.stdout
    assert cli("chat", "get-id", "me").stdout == "13342324\n"


def test_add_negative_group_id(cli):
    result = cli("chat", "add", "team", "-1001234567890")
    assert result.exit_code == 0, result.stderr
    assert cli("chat", "get-id", "team").stdout == "-1001234567890\n"


def test_add_duplicate(cli):
    cli("chat", "add", "me", "13342324")
    result = cli("chat", "add", "me", "999")
    assert result.exit_code == 3
    assert "already exists" in result.stderr
    assert cli("chat", "get-id", "me").stdout == "13342324\n"


def test_add_invalid_id(cli):
    result = cli("chat", "add", "me", "not-an-id")
    assert result.exit_code == 2
    assert "Invalid chat ID" in result.stderr


def test_add_resolves_public_channel(cli, token, fake_tg):
    result = cli("chat", "add", "news", "@mychannel")
    assert result.exit_code == 0, result.stderr
    assert fake_tg.calls[0].method == "getChat"
    assert fake_tg.calls[0].params == {"chat_id": "@mychannel"}
    assert cli("chat", "get-id", "news").stdout == "-1001234567890\n"
    assert "My Channel" in cli("chat", "list").stdout


def test_add_without_token_stores_as_given(cli, fake_tg):
    result = cli("chat", "add", "news", "@mychannel")
    assert result.exit_code == 0
    assert "not resolved" in result.stderr
    assert fake_tg.calls == []
    assert cli("chat", "get-id", "news").stdout == "@mychannel\n"


def test_add_no_resolve(cli, token, fake_tg):
    cli("chat", "add", "news", "@mychannel", "--no-resolve")
    assert fake_tg.calls == []
    assert cli("chat", "get-id", "news").stdout == "@mychannel\n"


def test_add_resolution_failure_falls_back(cli, token, fake_tg):
    fake_tg.queue(
        "getChat",
        400,
        {"ok": False, "error_code": 400, "description": "Bad Request: chat not found"},
    )
    result = cli("chat", "add", "news", "@mychannel")
    assert result.exit_code == 0
    assert "chat not found" in result.stderr
    assert cli("chat", "get-id", "news").stdout == "@mychannel\n"


def test_list_sorted(cli):
    cli("chat", "add", "team", "-100")
    cli("chat", "add", "me", "1")
    result = cli("chat")
    assert result.exit_code == 0
    lines = result.stdout.splitlines()
    assert [line.split("\t")[:2] for line in lines] == [["me", "1"], ["team", "-100"]]


def test_list_empty(cli):
    result = cli("chat", "list")
    assert result.exit_code == 0
    assert "No saved chats" in result.stdout


def test_list_json(cli):
    cli("chat", "add", "me", "1")
    payload = cli("chat", "list", "--json").json()
    assert len(payload) == 1
    assert set(payload[0]) == {"name", "chat_id", "title", "created_at"}
    assert cli("chat", "list", "--json").json() == payload


def test_list_json_empty(cli):
    assert cli("chat", "list", "--json").json() == []


def test_replace_id(cli):
    cli("chat", "add", "me", "1")
    result = cli("chat", "replace-id", "me", "-42")
    assert result.exit_code == 0
    assert cli("chat", "get-id", "me").stdout == "-42\n"


def test_rename_onto_existing(cli):
    cli("chat", "add", "a", "1")
    cli("chat", "add", "b", "2")
    result = cli("chat", "rename", "a", "b")
    assert result.exit_code == 3
    assert "'b' already exists" in result.stderr
    assert cli("chat", "get-id", "a").stdout == "1\n"


def test_rename(cli):
    cli("chat", "add", "a", "1")
    assert cli("chat", "rename", "a", "c").exit_code == 0
    assert cli("chat", "get-id", "c").stdout == "1\n"


def test_remove_missing(cli):
    result = cli("chat", "remove", "ghost")
    assert result.exit_code == 3
    assert "not found" in result.stderr


def test_remove(cli):
    cli("chat", "add", "me", "1")
    assert cli("chat", "remove", "me").exit_code == 0
    assert cli("chat", "get-id", "me").exit_code == 3


def test_get_id_json(cli):
    cli("chat", "add", "me", "1")
    assert cli("chat", "get-id", "me", "--json").json() == {"name": "me", "chat_id": "1"}


def test_add_resolves_with_default_bot_token(cli, add_bot, write_config, fake_tg):
    add_bot("news", "1:NEWS")
    write_config(default_bot="news")
    assert cli("chat", "add", "chan", "@mychannel").exit_code == 0
    assert fake_tg.calls[0].token == "1:NEWS"


# --------------------------------------------------------------------------- chat default
def test_default_writes_config(cli, config_dir, write_config):
    write_config("# prefs\ncolor = false\n")
    assert cli("chat", "add", "me", "13342324").exit_code == 0
    result = cli("chat", "default", "me")
    assert result.exit_code == 0, result.stderr
    text = (config_dir / "config.toml").read_text()
    assert 'default_chat = "me"' in text
    assert "# prefs" in text
    assert "color = false" in text


def test_default_creates_config_file(cli, config_dir):
    assert cli("chat", "add", "me", "1").exit_code == 0
    assert cli("chat", "default", "me", "--json").json()["name"] == "me"
    assert 'default_chat = "me"' in (config_dir / "config.toml").read_text()


def test_default_unknown_chat(cli, config_dir):
    assert cli("chat", "default", "ghost").exit_code == 3
    assert not (config_dir / "config.toml").exists()
