"""Symmetric encryption of saved bot tokens (Fernet: AES-128-CBC + HMAC-SHA256).

The key comes only from ``TGBOT_SECRET_KEY`` (environment or ``<config_dir>/.env``) and is
created explicitly with ``tgbot key init`` — never implicitly, so a lost key is reported
instead of being silently replaced.
"""

from __future__ import annotations

import binascii

from cryptography.fernet import Fernet, InvalidToken

from .config import SECRET_KEY, Settings
from .errors import ConfigError


def generate_key() -> str:
    return Fernet.generate_key().decode()


def load_key(settings: Settings) -> Fernet:
    """Return the configured cipher or raise a ``ConfigError`` explaining how to fix it."""
    if settings.secret_key is None:
        raise ConfigError(
            "Encryption key is not configured.",
            hint=(
                f"Run `tgbot key init`, or restore the old {SECRET_KEY} if bots are already saved."
            ),
        )
    try:
        return Fernet(settings.secret_key.get_secret_value().strip())
    except (ValueError, binascii.Error):
        raise ConfigError(
            f"{SECRET_KEY} is not a valid key.",
            hint="It must be the 44-character value written by `tgbot key init`.",
        ) from None


def encrypt(fernet: Fernet, token: str) -> bytes:
    return fernet.encrypt(token.encode())


def decrypt(fernet: Fernet, blob: bytes, *, bot: str) -> str:
    try:
        return fernet.decrypt(blob).decode()
    except InvalidToken:
        raise ConfigError(
            f"Cannot decrypt the token of bot '{bot}' with the current key.",
            hint=f"Restore the {SECRET_KEY} it was saved with, or re-add the bot.",
        ) from None
