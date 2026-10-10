import pytest

from tgbot_cli.commands.send import pick_target, split_media_args
from tgbot_cli.errors import UsageError


@pytest.fixture
def files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ("a.pdf", "b.pdf", "a.png"):
        (tmp_path / name).write_bytes(b"x")
    return tmp_path


def test_positional_files_target_caption(files):
    assert split_media_args(["a.pdf", "b.pdf", "team", "Reports"], None, None) == (
        ["a.pdf", "b.pdf"],
        "team",
        "Reports",
    )


def test_flags(files):
    assert split_media_args(["a.png"], "me", None) == (["a.png"], "me", None)
    assert split_media_args(["a.png"], "me", "cap") == (["a.png"], "me", "cap")


def test_positional_caption_with_to_flag(files):
    assert split_media_args(["a.png", "cap"], "me", None) == (["a.png"], "me", "cap")


def test_url_is_content(files):
    url = "https://example.com/x.png"
    assert split_media_args([url, "me"], None, None) == ([url], "me", None)


def test_negative_target(files):
    assert split_media_args(["a.png", "-1001234"], None, None)[1] == "-1001234"


def test_extra_tokens(files):
    with pytest.raises(UsageError, match="extra"):
        split_media_args(["a.png", "me", "cap", "extra"], None, None)


def test_file_id_needs_flags(files):
    assert split_media_args(["CAACAgIAAxkB"], "me", None, has_caption=False) == (
        ["CAACAgIAAxkB"],
        "me",
        None,
    )
    assert split_media_args(["AgACAgIAAxkB", "BQACAgIAAxkB"], "me", "cap") == (
        ["AgACAgIAAxkB", "BQACAgIAAxkB"],
        "me",
        "cap",
    )


def test_missing_file_named(files):
    with pytest.raises(UsageError, match=r"File not found: nope\.pdf"):
        split_media_args(["nope.pdf"], "me", None)
    with pytest.raises(UsageError, match=r"File not found: nope\.pdf"):
        split_media_args(["a.pdf", "nope.pdf", "me"], None, None)


def test_no_content(files):
    with pytest.raises(UsageError, match="No media"):
        split_media_args(["me"], None, None)


def test_no_target(files):
    with pytest.raises(UsageError, match="No target"):
        split_media_args(["a.png"], None, None)


def test_sticker_has_no_caption(files):
    with pytest.raises(UsageError, match="extra"):
        split_media_args(["a.png", "me", "cap"], None, None, has_caption=False)


def test_pick_target():
    assert pick_target(["me"], None) == "me"
    assert pick_target([], "me") == "me"
    with pytest.raises(UsageError, match="No target"):
        pick_target([], None)
    with pytest.raises(UsageError, match="extra"):
        pick_target(["me", "x"], None)
    with pytest.raises(UsageError, match="extra"):
        pick_target(["x"], "me")
