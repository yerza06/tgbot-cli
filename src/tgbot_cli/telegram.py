"""Write-only Telegram Bot API client.

Only ``getMe``, ``getChat`` and the ``send*`` methods are allowed. Anything else, in
particular ``getUpdates`` and webhook management, is refused before a request is built:
this tool never reads anyone's messages.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from typing import IO, Any

import httpx

from . import crypto, db
from .config import Settings
from .console import out
from .errors import ConfigError, NetworkError, TelegramAPIError, TgbotError

SEND_METHODS = frozenset(
    {
        "sendMessage",
        "sendPhoto",
        "sendDocument",
        "sendVideo",
        "sendAudio",
        "sendVoice",
        "sendVideoNote",
        "sendAnimation",
        "sendSticker",
        "sendMediaGroup",
        "sendContact",
        "sendLocation",
        "sendPoll",
        "sendDice",
    }
)
ALLOWED_METHODS = SEND_METHODS | {"getMe", "getChat"}

# Longest rate-limit pause we are willing to wait out before giving up.
MAX_RETRY_AFTER = 60
START_HINT = (
    "The recipient must open the bot in Telegram and press Start (send /start) "
    "before the bot can message them; also check that the bot was not blocked "
    "and is a member of the group or channel."
)

# Replaced in tests with an ``httpx.MockTransport``.
TRANSPORT: httpx.BaseTransport | None = None

FileTuple = tuple[str, IO[bytes], str | None]


class MethodNotAllowedError(TgbotError):
    """A Bot API method outside the write-only allowlist was requested."""

    exit_code = 1


def _form_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


class BotClient:
    def __init__(
        self,
        token: str,
        *,
        api_url: str = "https://api.telegram.org",
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._token = token
        self._sleep = sleep
        self._http = httpx.Client(
            base_url=f"{api_url.rstrip('/')}/bot{token}/",
            timeout=timeout,
            transport=transport,
        )

    def __enter__(self) -> BotClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def _scrub(self, text: str) -> str:
        return text.replace(self._token, "***") if self._token else text

    def _post(
        self, method: str, params: Mapping[str, Any], files: Mapping[str, FileTuple] | None
    ) -> httpx.Response:
        clean = {key: value for key, value in params.items() if value is not None}
        if files:
            for _, handle, _ in files.values():
                handle.seek(0)
            data = {key: _form_value(value) for key, value in clean.items()}
            return self._http.post(method, data=data, files=dict(files))
        return self._http.post(method, json=clean)

    def call(
        self,
        method: str,
        params: Mapping[str, Any] | None = None,
        files: Mapping[str, FileTuple] | None = None,
    ) -> Any:
        """Call an allowed Bot API method and return its ``result``."""
        if method not in ALLOWED_METHODS:
            raise MethodNotAllowedError(
                f"Bot API method '{method}' is not allowed: tgbot is send-only."
            )
        params = params or {}

        for attempt in range(2):
            try:
                response = self._post(method, params, files)
            except httpx.TimeoutException:
                raise NetworkError(f"Timed out calling Telegram API ({method}).") from None
            except httpx.HTTPError as exc:
                raise NetworkError(
                    f"Could not reach Telegram API ({method}): "
                    f"{self._scrub(str(exc)) or type(exc).__name__}"
                ) from None

            try:
                payload = response.json()
            except ValueError:
                raise TelegramAPIError(
                    f"unexpected response from {method}",
                    error_code=response.status_code,
                ) from None

            if payload.get("ok"):
                return payload.get("result")

            code = payload.get("error_code", response.status_code)
            description = self._scrub(str(payload.get("description", "unknown error")))
            retry_after = (payload.get("parameters") or {}).get("retry_after")

            if code == 429 and attempt == 0 and retry_after and retry_after <= MAX_RETRY_AFTER:
                self._sleep(retry_after)
                continue

            raise TelegramAPIError(
                description,
                error_code=code,
                retry_after=retry_after,
                hint=START_HINT if code == 403 else None,
            )

        raise AssertionError("unreachable")  # pragma: no cover


def resolve_bot_token(settings: Settings, bot: str | None = None) -> tuple[str, str]:
    """Pick the bot (``bot`` -> ``default_bot`` setting) and decrypt its token.

    Raises ``ConfigError`` subclasses before any network call when no bot is saved, the
    alias is unknown, or the key is missing or wrong. Returns ``(name, token)``.
    """
    from_config = bot is None
    name = bot if bot is not None else settings.default_bot
    with db.open_db(settings.db_path) as conn:
        if not db.list_bots(conn):
            raise db.NoBotsError()
        if name is None:
            raise ConfigError(
                "No default bot configured.",
                hint="Pass --bot NAME or set one with `tgbot bot default NAME`.",
            )
        if db.find_bot(conn, name) is None:
            hint = (
                "The configured default bot does not exist; fix it with `tgbot bot default NAME`."
                if from_config
                else "See saved bots with `tgbot bot list`."
            )
            raise db.BotNotFoundError(name, hint=hint)
        blob = db.get_bot_token_enc(conn, name)
    token = crypto.decrypt(crypto.load_key(settings), blob, bot=name)
    return name, token


def client_for_token(settings: Settings, token: str) -> BotClient:
    """Create a client for ``token``; the token is masked in all output from now on."""
    out.register_secret(token)
    return BotClient(
        token,
        api_url=settings.api_url,
        timeout=settings.timeout,
        transport=TRANSPORT,
    )


def build_client(settings: Settings, bot: str | None = None) -> BotClient:
    """Create a client for the chosen saved bot (``--bot``, else the default bot)."""
    _, token = resolve_bot_token(settings, bot)
    return client_for_token(settings, token)
