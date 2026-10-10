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
