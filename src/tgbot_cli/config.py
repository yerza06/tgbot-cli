"""Application configuration via pydantic-settings.

Sources (in priority order): environment variables prefixed with ``TGBOT_``, the
``<config_dir>/.env`` file (secrets) and ``<config_dir>/config.toml`` (preferences).
``config_dir`` defaults to ``~/.config/tgbot`` and can be moved with ``TGBOT_CONFIG_DIR``;
the database lives there too, so ``tgbot`` works from any directory.
"""

from __future__ import annotations

import os
import tempfile
import tomllib
from pathlib import Path
from typing import Any

import tomlkit
from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from .errors import ConfigError

ENV_PREFIX = "TGBOT_"
SECRET_KEY = f"{ENV_PREFIX}SECRET_KEY"
CONFIG_FILE = "config.toml"
# Keys read from config.toml; anything else there (secrets included) is ignored.
TOML_KEYS = frozenset({"default_bot", "default_chat", "color", "api_url", "timeout"})


def default_config_dir() -> Path:
    return Path.home() / ".config" / "tgbot"


class _ConfigToml(TomlConfigSettingsSource):
    """``config.toml`` restricted to the preference keys in ``TOML_KEYS``."""

    def _read_file(self, file_path: Any) -> dict[str, Any]:
        data = super()._read_file(file_path)
        return {key: value for key, value in data.items() if key in TOML_KEYS}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    secret_key: SecretStr | None = None
    default_bot: str | None = None
    default_chat: str | None = None
    config_dir: Path = Field(default_factory=default_config_dir)
    plain: bool = False
    color: bool = True
    api_url: str = "https://api.telegram.org"
    timeout: float = 30.0

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        config_dir = getattr(init_settings, "init_kwargs", {}).get("config_dir")
        toml_file = Path(config_dir or default_config_dir()) / CONFIG_FILE
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            _ConfigToml(settings_cls, toml_file=toml_file),
        )

    @field_validator("config_dir", mode="after")
    @classmethod
    def _expand(cls, value: Path) -> Path:
        return value.expanduser()

    @field_validator("secret_key", mode="after")
    @classmethod
    def _empty_secret_is_none(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and not value.get_secret_value().strip():
            return None
        return value

    @field_validator("default_bot", "default_chat", mode="after")
    @classmethod
    def _empty_name_is_none(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @property
    def env_file(self) -> Path:
        return self.config_dir / ".env"

    @property
    def config_file(self) -> Path:
        return self.config_dir / CONFIG_FILE

    @property
    def db_path(self) -> Path:
        return self.config_dir / "tgbot.db"


def get_settings() -> Settings:
    """Load settings, reading the ``.env`` file from the (possibly overridden) config dir."""
    raw_dir = os.environ.get(f"{ENV_PREFIX}CONFIG_DIR")
    config_dir = Path(raw_dir).expanduser() if raw_dir else default_config_dir()
    toml_file = config_dir / CONFIG_FILE
    try:
        return Settings(_env_file=config_dir / ".env", config_dir=config_dir)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(
            f"Invalid configuration file {toml_file}: {exc}",
            hint="Fix the TOML syntax or delete the file.",
        ) from None
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(map(str, err['loc']))} ({ENV_PREFIX}"
            f"{'.'.join(map(str, err['loc'])).upper()}): {err['msg']}"
            for err in exc.errors()
        )
        source = f" (environment, .env or {toml_file})" if toml_file.exists() else ""
        raise ConfigError(f"Invalid configuration{source}: {problems}") from None


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


def config_file_value(settings: Settings, key: str) -> Any:
    """A key as written in ``config.toml`` itself (ignoring env/.env overrides)."""
    path = settings.config_file
    if not path.exists():
        return None
    try:
        return tomllib.loads(path.read_text(encoding="utf-8")).get(key)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid configuration file {path}: {exc}") from None


def update_config(settings: Settings, **values: Any) -> None:
    """Set keys in ``config.toml`` (``None`` removes one), keeping comments and order."""
    path = settings.config_file
    try:
        doc = (
            tomlkit.parse(path.read_text(encoding="utf-8")) if path.exists() else tomlkit.document()
        )
    except tomlkit.exceptions.ParseError as exc:
        raise ConfigError(f"Invalid configuration file {path}: {exc}") from None
    for key, value in values.items():
        if value is None:
            doc.pop(key, None)
        else:
            doc[key] = value
        setattr(settings, key, value)

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".config.", suffix=".toml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(tomlkit.dumps(doc))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
