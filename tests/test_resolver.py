import pytest

from tgbot_cli import db
from tgbot_cli.errors import ConfigError
from tgbot_cli.resolver import parse_chat_id, resolve_target


@pytest.fixture
def conn(tmp_path):
    with db.open_db(tmp_path / "tgbot.db") as connection:
        yield connection


def test_alias_wins(conn):
    db.add_chat(conn, "me", "13342324")
    assert resolve_target(conn, "me") == 13342324


def test_alias_shadowing_a_number(conn):
    db.add_chat(conn, "42", "-1001")
    assert resolve_target(conn, "42") == -1001


def test_alias_with_username(conn):
    db.add_chat(conn, "news", "@mychannel")
    assert resolve_target(conn, "news") == "@mychannel"


def test_numeric_ids(conn):
    assert resolve_target(conn, "123") == 123
    assert resolve_target(conn, "-1001234567890") == -1001234567890


def test_username_passthrough(conn):
    assert resolve_target(conn, "@mychannel") == "@mychannel"


def test_unknown_alias(conn):
    with pytest.raises(ConfigError) as excinfo:
        resolve_target(conn, "boss")
    assert excinfo.value.exit_code == 3
    assert "tgbot chat add" in excinfo.value.hint


@pytest.mark.parametrize(
    ("value", "expected"),
    [("12", 12), (" -5 ", -5), ("@good_name", "@good_name"), ("@x", None), ("me", None)],
)
def test_parse_chat_id(value, expected):
    assert parse_chat_id(value) == expected
