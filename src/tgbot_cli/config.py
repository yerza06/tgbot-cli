"""Application configuration via pydantic-settings.

Sources (in priority order): environment variables prefixed with ``TGBOT_`` and the
``<config_dir>/.env`` file. ``config_dir`` defaults to ``~/.config/tgbot`` and can be
moved with ``TGBOT_CONFIG_DIR``; the chat database lives there too, so ``tgbot`` works
from any directory.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .errors import ConfigError

ENV_PREFIX = "TGBOT_"
TOKEN_KEY = f"{ENV_PREFIX}BOT_TOKEN"


def default_config_dir() -> Path:
    return Path.home() / ".config" / "tgbot"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: SecretStr | None = None
    config_dir: Path = Field(default_factory=default_config_dir)
    plain: bool = False
    api_url: str = "https://api.telegram.org"
    timeout: float = 30.0

    @field_validator("config_dir", mode="after")
    @classmethod
    def _expand(cls, value: Path) -> Path:
        return value.expanduser()

    @field_validator("bot_token", mode="after")
    @classmethod
    def _empty_token_is_none(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value().strip():
            return None
        return value

    @property
    def env_file(self) -> Path:
        return self.config_dir / ".env"

    @property
    def db_path(self) -> Path:
        return self.config_dir / "tgbot.db"

    @property
    def has_token(self) -> bool:
        return self.bot_token is not None

    def require_token(self) -> str:
        """Return the token or raise a configuration error explaining how to set one."""
        if self.bot_token is None:
            raise ConfigError(
                "No bot token configured.",
                hint=f"Run `tgbot token set` or set the {TOKEN_KEY} environment variable.",
            )
        return self.bot_token.get_secret_value().strip()


def get_settings() -> Settings:
    """Load settings, reading the ``.env`` file from the (possibly overridden) config dir."""
    raw_dir = os.environ.get(f"{ENV_PREFIX}CONFIG_DIR")
    config_dir = Path(raw_dir).expanduser() if raw_dir else default_config_dir()
    try:
        return Settings(_env_file=config_dir / ".env", config_dir=config_dir)
    except ValidationError as exc:
        problems = "; ".join(
            f"{ENV_PREFIX}{'.'.join(map(str, err['loc'])).upper()}: {err['msg']}"
            for err in exc.errors()
        )
        raise ConfigError(f"Invalid configuration: {problems}") from None


def _write_env(settings: Settings, values: dict[str, str]) -> None:
    """Merge ``values`` into ``<config_dir>/.env`` (owner-only permissions)."""
    settings.config_dir.mkdir(parents=True, exist_ok=True)
    path = settings.env_file
    lines: dict[str, str] = {}
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, val = stripped.partition("=")
            lines[key.strip()] = val.strip()

    lines.update(values)
    content = "".join(f"{key}={value}\n" for key, value in lines.items())

    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    path.chmod(0o600)


def save_token(settings: Settings, token: str) -> None:
    """Store the bot token in ``<config_dir>/.env`` and update ``settings`` in place."""
    _write_env(settings, {TOKEN_KEY: token})
    settings.bot_token = SecretStr(token)
