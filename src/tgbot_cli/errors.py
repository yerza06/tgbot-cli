"""Error hierarchy. Every expected failure maps to a stable exit code."""

from __future__ import annotations


class TgbotError(Exception):
    """Base class for errors reported to the user without a traceback."""

    exit_code: int = 1

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class TelegramAPIError(TgbotError):
    """Telegram rejected the request (``ok: false``)."""

    exit_code = 1

    def __init__(
        self,
        description: str,
        *,
        error_code: int | None = None,
        retry_after: int | None = None,
        hint: str | None = None,
    ) -> None:
        prefix = f"Telegram error {error_code}: " if error_code else "Telegram error: "
        super().__init__(prefix + description, hint=hint)
        self.description = description
        self.error_code = error_code
        self.retry_after = retry_after


class UsageError(TgbotError):
    """Bad or missing arguments, invalid values, missing files, exceeded limits."""

    exit_code = 2


class ConfigError(TgbotError):
    """No token, unknown alias, alias already exists or not found."""

    exit_code = 3


class NetworkError(TgbotError):
    """Telegram API could not be reached (timeout, connection failure)."""

    exit_code = 4
