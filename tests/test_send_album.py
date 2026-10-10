import pytest


@pytest.fixture
def photos(tmp_path, monkeypatch, cli):
    monkeypatch.chdir(tmp_path)
    names = [f"p{i:02d}.jpg" for i in range(12)]
    for name in names:
        (tmp_path / name).write_bytes(name.encode())
    for name in ("a.pdf", "b.pdf", "v1.mp4", "v2.mp4"):
        (tmp_path / name).write_bytes(b"x")
    assert cli("chat", "add", "me", "1").exit_code == 0
    return names


def test_twelve_photos_two_albums(cli, token, fake_tg, photos):
    result = cli("sendphoto", *photos, "me", "Batch", "--json")
    assert result.exit_code == 0, result.stderr
    assert fake_tg.methods() == ["sendMediaGroup", "sendMediaGroup"]

    first, second = (call.params["media"] for call in fake_tg.calls)
    assert len(first) == 10
    assert len(second) == 2
    assert first[0]["caption"] == "Batch"
    assert all("caption" not in item for item in first[1:] + second)
    assert first[0] == {"type": "photo", "media": "attach://file0", "caption": "Batch"}
    assert set(fake_tg.calls[0].files) == {f"file{i}" for i in range(10)}
    assert fake_tg.calls[1].files["file1"].filename == "p11.jpg"
    assert len(result.json()["message_ids"]) == 12


def test_eleven_photos_single_tail_falls_back(cli, token, fake_tg, photos):
    cli("sendphoto", *photos[:11], "me")
    assert fake_tg.methods() == ["sendMediaGroup", "sendPhoto"]


def test_videos_album(cli, token, fake_tg, photos):
    cli("sendvideo", "v1.mp4", "v2.mp4", "me")
    assert fake_tg.methods() == ["sendMediaGroup"]
    assert [m["type"] for m in fake_tg.calls[0].params["media"]] == ["video", "video"]


def test_documents_without_group_are_separate(cli, token, fake_tg, photos):
    cli("sendfile", "a.pdf", "b.pdf", "--to", "me")
    assert fake_tg.methods() == ["sendDocument", "sendDocument"]


def test_documents_with_group(cli, token, fake_tg, photos):
    cli("sendfile", "a.pdf", "b.pdf", "--to", "me", "--group", "--silent")
    assert fake_tg.methods() == ["sendMediaGroup"]
    params = fake_tg.calls[0].params
    assert [m["type"] for m in params["media"]] == ["document", "document"]
    assert params["disable_notification"] == "true"


def test_album_of_urls_is_json_request(cli, token, fake_tg, photos):
    urls = ["https://e.com/1.jpg", "https://e.com/2.jpg"]
    cli("sendphoto", *urls, "--to", "me", "--caption", "c")
    call = fake_tg.calls[0]
    assert call.files == {}
    assert call.params["media"] == [
        {"type": "photo", "media": urls[0], "caption": "c"},
        {"type": "photo", "media": urls[1]},
    ]
