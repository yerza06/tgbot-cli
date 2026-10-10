import pytest

from tgbot_cli.errors import (
    ConfigError,
    NetworkError,
    TelegramAPIError,
    TgbotError,
    UsageError,
)


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (TelegramAPIError("Bad Request", error_code=400), 1),
        (UsageError("bad"), 2),
        (ConfigError("missing"), 3),
        (NetworkError("down"), 4),
    ],
)
def test_exit_codes(error: TgbotError, code: int) -> None:
    assert isinstance(error, TgbotError)
    assert error.exit_code == code


def test_telegram_error_message_includes_code() -> None:
    error = TelegramAPIError("Bad Request: chat not found", error_code=400)
    assert error.message == "Telegram error 400: Bad Request: chat not found"
    assert error.description == "Bad Request: chat not found"


def test_hint_is_kept() -> None:
    assert ConfigError("x", hint="do y").hint == "do y"
