import pytest

from tgbot_cli import db
from tgbot_cli.errors import ConfigError


@pytest.fixture
def conn(tmp_path):
    with db.open_db(tmp_path / "nested" / "tgbot.db") as connection:
        yield connection


def test_add_and_find(conn):
    chat = db.add_chat(conn, "me", "13342324")
    assert chat.name == "me"
    assert db.find_chat(conn, "me") == chat
    assert db.find_chat(conn, "ghost") is None


def test_names_are_unique(conn):
    db.add_chat(conn, "me", "1")
    with pytest.raises(db.ChatExistsError) as excinfo:
        db.add_chat(conn, "me", "2")
    assert isinstance(excinfo.value, ConfigError)
    assert db.get_chat(conn, "me").chat_id == "1"


def test_list_sorted_by_name(conn):
    db.add_chat(conn, "team", "-100")
    db.add_chat(conn, "me", "1", "Me")
    assert [c.name for c in db.list_chats(conn)] == ["me", "team"]


def test_get_missing(conn):
    with pytest.raises(db.ChatNotFoundError):
        db.get_chat(conn, "ghost")


def test_rename(conn):
    db.add_chat(conn, "a", "1")
    assert db.rename_chat(conn, "a", "b").name == "b"
    assert db.find_chat(conn, "a") is None


def test_rename_clash(conn):
    db.add_chat(conn, "a", "1")
    db.add_chat(conn, "b", "2")
    with pytest.raises(db.ChatExistsError):
        db.rename_chat(conn, "a", "b")
    assert db.get_chat(conn, "a").chat_id == "1"


def test_rename_missing(conn):
    with pytest.raises(db.ChatNotFoundError):
        db.rename_chat(conn, "ghost", "x")


def test_replace_id(conn):
    db.add_chat(conn, "me", "1", "Old title")
    chat = db.replace_chat_id(conn, "me", "2")
    assert chat.chat_id == "2"
    assert db.get_chat(conn, "me").title is None


def test_remove(conn):
    db.add_chat(conn, "me", "1")
    db.remove_chat(conn, "me")
    assert db.list_chats(conn) == []
    with pytest.raises(db.ChatNotFoundError):
        db.remove_chat(conn, "me")


def test_persisted_between_connections(tmp_path):
    path = tmp_path / "tgbot.db"
    with db.open_db(path) as conn:
        db.add_chat(conn, "me", "1")
    with db.open_db(path) as conn:
        assert db.get_chat(conn, "me").chat_id == "1"


# --------------------------------------------------------------------------- bots
def test_bot_crud(conn):
    bot = db.add_bot(conn, "news", b"cipher", 42, "news_bot")
    assert db.find_bot(conn, "news") == bot
    assert db.get_bot_token_enc(conn, "news") == b"cipher"
    assert db.find_bot(conn, "ghost") is None

    db.remove_bot(conn, "news")
    assert db.list_bots(conn) == []


def test_bot_to_dict_has_no_token_and_computed_default(conn):
    bot = db.add_bot(conn, "news", b"cipher", 42, "news_bot")
    data = bot.to_dict("news")
    assert data["is_default"] is True
    assert set(data) == {"name", "bot_id", "username", "is_default", "created_at"}
    assert bot.to_dict("other")["is_default"] is False


def test_bot_names_are_unique(conn):
    db.add_bot(conn, "news", b"a", 1, None)
    with pytest.raises(db.BotExistsError) as excinfo:
        db.add_bot(conn, "news", b"b", 2, None)
    assert isinstance(excinfo.value, ConfigError)
    assert db.get_bot_token_enc(conn, "news") == b"a"


def test_bots_listed_in_creation_order(conn):
    db.add_bot(conn, "zeta", b"a", 1, None)
    db.add_bot(conn, "alpha", b"b", 2, None)
    assert [b.name for b in db.list_bots(conn)] == ["zeta", "alpha"]


def test_bot_rename_and_clash(conn):
    db.add_bot(conn, "news", b"a", 1, "n")
    db.add_bot(conn, "alerts", b"b", 2, "a")
    with pytest.raises(db.BotExistsError):
        db.rename_bot(conn, "news", "alerts")
    renamed = db.rename_bot(conn, "news", "daily")
    assert renamed.name == "daily"
    assert db.get_bot_token_enc(conn, "daily") == b"a"
    assert db.find_bot(conn, "news") is None


def test_bot_not_found(conn):
    with pytest.raises(db.BotNotFoundError):
        db.get_bot(conn, "ghost")
    with pytest.raises(db.BotNotFoundError):
        db.get_bot_token_enc(conn, "ghost")
    with pytest.raises(db.BotNotFoundError):
        db.remove_bot(conn, "ghost")
    with pytest.raises(db.BotNotFoundError):
        db.rename_bot(conn, "ghost", "x")


def test_existing_chats_db_gains_bots_table(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.execute(
        "CREATE TABLE chats (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, "
        "chat_id TEXT NOT NULL, title TEXT, created_at TEXT NOT NULL)"
    )
    old.execute("INSERT INTO chats VALUES (1, 'me', '1', NULL, '2026-01-01T00:00:00+00:00')")
    old.commit()
    old.close()

    with db.open_db(path) as conn:
        assert db.get_chat(conn, "me").chat_id == "1"
        assert db.list_bots(conn) == []
