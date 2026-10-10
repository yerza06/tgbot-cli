import pytest

from tgbot_cli.media import MAX_UPLOAD_BYTES


@pytest.fixture
def workdir(tmp_path, monkeypatch, cli):
    monkeypatch.chdir(tmp_path)
    for name in (
        "shot.png",
        "a.pdf",
        "b.pdf",
        "clip.mp4",
        "track.mp3",
        "voice.ogg",
        "anim.gif",
        "note.mp4",
        "sticker.webp",
    ):
        (tmp_path / name).write_bytes(name.encode())
    assert cli("chat", "add", "me", "13342324").exit_code == 0
    assert cli("chat", "add", "team", "-1001").exit_code == 0
    return tmp_path


def test_photo_with_caption(cli, token, fake_tg, workdir):
    result = cli("sendphoto", "shot.png", "me", "Screenshot")
    assert result.exit_code == 0, result.stderr
    call = fake_tg.calls[0]
    assert call.method == "sendPhoto"
    assert call.params == {"chat_id": "13342324", "caption": "Screenshot"}
    assert call.files["photo"].filename == "shot.png"
    assert call.files["photo"].value == b"shot.png"


def test_photo_from_url(cli, token, fake_tg, workdir):
    assert cli("sendphoto", "https://example.com/a.png", "--to", "me").exit_code == 0
    call = fake_tg.calls[0]
    assert call.files == {}
    assert call.params == {"chat_id": 13342324, "photo": "https://example.com/a.png"}


def test_sticker_by_file_id(cli, token, fake_tg, workdir):
    assert cli("sendsticker", "CAACAgIAAxkB", "--to", "me").exit_code == 0
    assert fake_tg.calls[0].method == "sendSticker"
    assert fake_tg.calls[0].params == {"chat_id": 13342324, "sticker": "CAACAgIAAxkB"}


def test_missing_file_before_any_request(cli, token, fake_tg, workdir):
    result = cli("sendfile", "nope.pdf", "--to", "me")
    assert result.exit_code == 2
    assert "nope.pdf" in result.stderr
    assert fake_tg.calls == []


def test_oversized_upload(cli, token, fake_tg, workdir):
    with open(workdir / "big.bin", "wb") as fh:
        fh.truncate(MAX_UPLOAD_BYTES + 1)
    result = cli("sendfile", "big.bin", "--to", "me")
    assert result.exit_code == 2
    assert "50 MB" in result.stderr
    assert fake_tg.calls == []


def test_long_caption_rejected(cli, token, fake_tg, workdir):
    assert cli("sendphoto", "shot.png", "me", "x" * 1025).exit_code == 2
    assert fake_tg.calls == []


@pytest.mark.parametrize(
    ("command", "filename", "method", "field"),
    [
        ("sendfile", "a.pdf", "sendDocument", "document"),
        ("sendvideo", "clip.mp4", "sendVideo", "video"),
        ("sendaudio", "track.mp3", "sendAudio", "audio"),
        ("sendvoice", "voice.ogg", "sendVoice", "voice"),
        ("sendanimation", "anim.gif", "sendAnimation", "animation"),
        ("sendvideonote", "note.mp4", "sendVideoNote", "video_note"),
        ("sendsticker", "sticker.webp", "sendSticker", "sticker"),
    ],
)
def test_single_media_methods(cli, token, fake_tg, workdir, command, filename, method, field):
    result = cli(command, filename, "me", "--silent", "--json")
    assert result.exit_code == 0, result.stderr
    call = fake_tg.calls[0]
    assert call.method == method
    assert call.files[field].filename == filename
    assert call.params["disable_notification"] == "true"
    assert "caption" not in call.params
    assert result.json()["message_ids"] == [101]


def test_positional_files_target_caption(cli, token, fake_tg, workdir):
    result = cli("sendfile", "a.pdf", "b.pdf", "team", "Reports")
    assert result.exit_code == 0, result.stderr
    assert fake_tg.methods() == ["sendDocument", "sendDocument"]
    assert fake_tg.calls[0].params == {"chat_id": "-1001", "caption": "Reports"}
    assert "caption" not in fake_tg.calls[1].params


def test_extra_tokens(cli, token, fake_tg, workdir):
    result = cli("sendphoto", "shot.png", "me", "cap", "extra")
    assert result.exit_code == 2
    assert "extra" in result.stderr
    assert fake_tg.calls == []


def test_caption_parse_mode(cli, token, fake_tg, workdir):
    cli("sendphoto", "shot.png", "me", "<b>x</b>", "--parse-mode", "html")
    assert fake_tg.calls[0].params["parse_mode"] == "HTML"
