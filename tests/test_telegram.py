import io

import httpx
import pytest

from tgbot_cli.errors import NetworkError, TelegramAPIError
from tgbot_cli.telegram import ALLOWED_METHODS, BotClient, MethodNotAllowedError

from .conftest import TOKEN, FakeTelegram


def make_client(fake: FakeTelegram, sleeps: list[float] | None = None) -> BotClient:
    return BotClient(
        TOKEN,
        transport=fake.transport,
        sleep=(sleeps.append if sleeps is not None else lambda _s: None),
    )


@pytest.mark.parametrize(
    "method", ["getUpdates", "setWebhook", "deleteWebhook", "getWebhookInfo", "forwardMessage"]
)
def test_reading_methods_are_refused_without_request(method):
    fake = FakeTelegram()
    with make_client(fake) as client, pytest.raises(MethodNotAllowedError):
        client.call(method)
    assert fake.calls == []


def test_allowlist_is_send_only():
    assert "getUpdates" not in ALLOWED_METHODS
    assert {m for m in ALLOWED_METHODS if not m.startswith("send")} == {"getMe", "getChat"}


def test_json_body_and_none_dropped():
    fake = FakeTelegram()
    with make_client(fake) as client:
        result = client.call("sendMessage", {"chat_id": 1, "text": "hi", "parse_mode": None})
    assert result["message_id"] > 0
    assert fake.calls[0].method == "sendMessage"
    assert fake.calls[0].params == {"chat_id": 1, "text": "hi"}


def test_multipart_upload():
    fake = FakeTelegram()
    with make_client(fake) as client:
        client.call(
            "sendPhoto",
            {"chat_id": 1, "caption": "cap", "disable_notification": True},
            {"photo": ("a.png", io.BytesIO(b"PNG"), "image/png")},
        )
    call = fake.calls[0]
    assert call.params == {"chat_id": "1", "caption": "cap", "disable_notification": "true"}
    assert call.files["photo"].filename == "a.png"
    assert call.files["photo"].value == b"PNG"


def test_rate_limit_is_retried_once():
    fake = FakeTelegram()
    fake.queue(
        "sendMessage",
        429,
        {
            "ok": False,
            "error_code": 429,
            "description": "Too Many Requests: retry after 1",
            "parameters": {"retry_after": 1},
        },
    )
    sleeps: list[float] = []
    with make_client(fake, sleeps) as client:
        result = client.call("sendMessage", {"chat_id": 1, "text": "hi"})
    assert "message_id" in result
    assert sleeps == [1]
    assert fake.methods() == ["sendMessage", "sendMessage"]


def test_rate_limit_twice_fails():
    fake = FakeTelegram()
    payload = {
        "ok": False,
        "error_code": 429,
        "description": "Too Many Requests",
        "parameters": {"retry_after": 1},
    }
    fake.queue("sendMessage", 429, payload)
    fake.queue("sendMessage", 429, payload)
    with make_client(fake) as client, pytest.raises(TelegramAPIError) as excinfo:
        client.call("sendMessage", {"chat_id": 1, "text": "hi"})
    assert excinfo.value.error_code == 429


def test_upload_is_rewound_on_retry():
    fake = FakeTelegram()
    fake.queue(
        "sendDocument",
        429,
        {"ok": False, "error_code": 429, "description": "slow", "parameters": {"retry_after": 1}},
    )
    with make_client(fake) as client:
        client.call("sendDocument", {"chat_id": 1}, {"document": ("a.txt", io.BytesIO(b"x"), None)})
    assert fake.calls[1].files["document"].value == b"x"


def test_403_has_start_hint():
    fake = FakeTelegram()
    fake.queue(
        "sendMessage",
        403,
        {
            "ok": False,
            "error_code": 403,
            "description": "Forbidden: bot can't initiate conversation with a user",
        },
    )
    with make_client(fake) as client, pytest.raises(TelegramAPIError) as excinfo:
        client.call("sendMessage", {"chat_id": 1, "text": "hi"})
    assert excinfo.value.exit_code == 1
    assert "/start" in excinfo.value.hint


def test_400_is_telegram_error():
    fake = FakeTelegram()
    fake.queue(
        "sendMessage",
        400,
        {"ok": False, "error_code": 400, "description": "Bad Request: chat not found"},
    )
    with make_client(fake) as client, pytest.raises(TelegramAPIError, match="chat not found"):
        client.call("sendMessage", {"chat_id": 1, "text": "hi"})


def test_non_json_response():
    transport = httpx.MockTransport(lambda request: httpx.Response(502, text="<html>"))
    with BotClient(TOKEN, transport=transport) as client, pytest.raises(TelegramAPIError):
        client.call("getMe")


def test_connect_error_is_network_error_without_token():
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot connect to {request.url}", request=request)

    client = BotClient(TOKEN, transport=httpx.MockTransport(fail))
    with client, pytest.raises(NetworkError) as excinfo:
        client.call("sendMessage", {"chat_id": 1, "text": "hi"})
    assert excinfo.value.exit_code == 4
    assert TOKEN not in excinfo.value.message
    assert "sendMessage" in excinfo.value.message


def test_timeout_is_network_error():
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = BotClient(TOKEN, transport=httpx.MockTransport(slow))
    with client, pytest.raises(NetworkError, match="Timed out"):
        client.call("getMe")


def test_network_error_through_cli_exits_4_and_hides_token(cli, token, monkeypatch):
    from tgbot_cli import telegram

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"boom {request.url}", request=request)

    monkeypatch.setattr(telegram, "TRANSPORT", httpx.MockTransport(fail))
    result = cli("send", "hi", "123")
    assert result.exit_code == 4
    assert token not in result.stderr + result.stdout


# --------------------------------------------------------------------------- bot selection
@pytest.fixture
def two_bots(add_bot, write_config):
    add_bot("news", "1:NEWS")
    add_bot("alerts", "2:ALERTS")
    write_config(default_bot="news")


def _token_for(bot=None):
    from tgbot_cli.config import get_settings
    from tgbot_cli.telegram import resolve_bot_token

    return resolve_bot_token(get_settings(), bot)


def test_bot_precedence(two_bots, monkeypatch):
    assert _token_for() == ("news", "1:NEWS")
    monkeypatch.setenv("TGBOT_DEFAULT_BOT", "alerts")
    assert _token_for() == ("alerts", "2:ALERTS")
    assert _token_for("news") == ("news", "1:NEWS")


def test_unknown_alias(two_bots):
    from tgbot_cli.db import BotNotFoundError

    with pytest.raises(BotNotFoundError) as excinfo:
        _token_for("missing")
    assert "tgbot bot list" in excinfo.value.hint


def test_configured_default_bot_missing(add_bot, write_config):
    from tgbot_cli.db import BotNotFoundError

    add_bot("news", "1:NEWS")
    write_config(default_bot="gone")
    with pytest.raises(BotNotFoundError) as excinfo:
        _token_for()
    assert "gone" in excinfo.value.message
    assert "tgbot bot default" in excinfo.value.hint


def test_empty_registry(secret_key):
    from tgbot_cli.db import NoBotsError

    with pytest.raises(NoBotsError) as excinfo:
        _token_for()
    assert "tgbot bot add" in excinfo.value.hint


def test_bots_but_no_default(add_bot):
    from tgbot_cli.errors import ConfigError

    add_bot("news", "1:NEWS")
    with pytest.raises(ConfigError, match="No default bot"):
        _token_for()


def test_selection_errors_make_no_request(cli, two_bots, fake_tg, write_config):
    assert cli("send", "hi", "1", "--bot", "missing").exit_code == 3
    write_config(default_bot="gone")
    assert cli("send", "hi", "1").exit_code == 3
    assert fake_tg.calls == []
