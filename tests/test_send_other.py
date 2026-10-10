import pytest


@pytest.fixture
def me(cli):
    assert cli("chat", "add", "me", "1").exit_code == 0


def test_contact_positional(cli, token, fake_tg, me):
    result = cli("sendcontact", "+77001234567", "Ivan", "Petrov", "me")
    assert result.exit_code == 0, result.stderr
    assert fake_tg.calls[0].method == "sendContact"
    assert fake_tg.calls[0].params == {
        "chat_id": 1,
        "phone_number": "+77001234567",
        "first_name": "Ivan",
        "last_name": "Petrov",
    }


def test_contact_without_last_name(cli, token, fake_tg, me):
    cli("sendcontact", "+77001234567", "Ivan", "me")
    assert "last_name" not in fake_tg.calls[0].params


def test_contact_flags(cli, token, fake_tg, me):
    result = cli(
        "sendcontact", "--phone", "+7700", "--first-name", "Ivan", "--last-name", "P", "--to", "me"
    )
    assert result.exit_code == 0
    assert fake_tg.calls[0].params["last_name"] == "P"


def test_contact_requires_phone_and_name(cli, token, fake_tg, me):
    assert cli("sendcontact", "--to", "me").exit_code == 2
    assert fake_tg.calls == []


def test_location(cli, token, fake_tg, me):
    assert cli("sendlocation", "43.238", "76.889", "me").exit_code == 0
    assert fake_tg.calls[0].params == {"chat_id": 1, "latitude": 43.238, "longitude": 76.889}


def test_location_negative_coordinates(cli, token, fake_tg, me):
    result = cli("sendlocation", "-33.8688", "-151.2093", "--to", "me")
    assert result.exit_code == 0, result.stderr
    assert fake_tg.calls[0].params["latitude"] == -33.8688
    assert fake_tg.calls[0].params["longitude"] == -151.2093


@pytest.mark.parametrize("args", [("95", "10", "me"), ("10", "181", "me"), ("x", "1", "me")])
def test_location_invalid(cli, token, fake_tg, me, args):
    assert cli("sendlocation", *args).exit_code == 2
    assert fake_tg.calls == []


def test_poll(cli, token, fake_tg, me):
    result = cli("sendpoll", "Deploy now?", "Yes", "No", "--to", "me")
    assert result.exit_code == 0, result.stderr
    assert fake_tg.calls[0].params == {
        "chat_id": 1,
        "question": "Deploy now?",
        "options": [{"text": "Yes"}, {"text": "No"}],
        "is_anonymous": True,
        "allows_multiple_answers": False,
    }


def test_poll_target_positional_and_flags(cli, token, fake_tg, me):
    cli("sendpoll", "Q?", "A", "B", "C", "me", "--multiple", "--no-anonymous")
    params = fake_tg.calls[0].params
    assert [o["text"] for o in params["options"]] == ["A", "B", "C"]
    assert params["is_anonymous"] is False
    assert params["allows_multiple_answers"] is True


def test_poll_too_few_options(cli, token, fake_tg, me):
    assert cli("sendpoll", "Q?", "Yes", "--to", "me").exit_code == 2
    assert fake_tg.calls == []


def test_poll_too_many_options(cli, token, fake_tg, me):
    options = [str(i) for i in range(11)]
    assert cli("sendpoll", "Q?", *options, "--to", "me").exit_code == 2


def test_dice_default(cli, token, fake_tg, me):
    assert cli("senddice", "me").exit_code == 0
    assert fake_tg.calls[0].params == {"chat_id": 1, "emoji": "🎲"}


def test_dice_emoji(cli, token, fake_tg, me):
    cli("senddice", "--to", "me", "--emoji", "🎯")
    assert fake_tg.calls[0].params["emoji"] == "🎯"


def test_dice_bad_emoji(cli, token, fake_tg, me):
    assert cli("senddice", "me", "--emoji", "🍕").exit_code == 2


def test_silent_contact(cli, token, fake_tg, me):
    cli("sendcontact", "+7700", "Ivan", "me", "--silent")
    assert fake_tg.calls[0].params["disable_notification"] is True
