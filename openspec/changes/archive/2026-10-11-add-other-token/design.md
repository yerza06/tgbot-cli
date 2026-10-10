# Design

## Context

Мотивация — см. proposal.md («Why»), требования — `specs/bot-registry`, `specs/token-encryption`, `specs/user-config`.

Текущее устройство, на которое опирается решение:
- `config.Settings` (pydantic-settings) читает `TGBOT_*` из env и `<config_dir>/.env`; токен — `bot_token: SecretStr`, `require_token()` бросает `ConfigError` (exit 3), `save_token()` пишет `.env` через `_write_env` (слияние строк, права 0600). Поле `plain` уже читается из `TGBOT_PLAIN`.
- `db.py` — SQLite `<config_dir>/tgbot.db`, таблица `chats`, контекст-менеджер `open_db()` выполняет `SCHEMA` (`CREATE TABLE IF NOT EXISTS`) при каждом открытии; ошибки `ChatExistsError`/`ChatNotFoundError` наследуют `ConfigError`; dataclass `Chat` с `to_dict()`.
- `telegram.build_client(settings)` берёт токен из `settings.require_token()`, регистрирует его в `out.register_secret()` и создаёт `BotClient`; `BotClient._scrub` дополнительно маскирует токен в ошибках.
- `commands/send.py`: `_dispatch(target, sender)` — единая точка для всех send-команд; цель выбирают `pick_target(rest, to)` и `split_media_args(...)`, оба бросают `_no_target()` (`UsageError`), если цели нет.
- `console.py::_plain_requested` выбирает plain-режим по `--plain`/`NO_COLOR`/не-TTY; `cli.py` передаёт `plain or get_settings().plain`.
- `commands/chat.py::_resolve_username` использует `settings.has_token` для `getChat`.
- Тесты: фикстура `token` в `tests/conftest.py` выставляет `TGBOT_BOT_TOKEN`; `isolated_env` чистит все `TGBOT_*` и даёт отдельный `config_dir`.

## Goals / Non-Goals

**Goals:**
- Несколько ботов в той же БД, что и чаты, с тем же стилем команд и ошибок.
- Токены в БД нечитаемы без ключа; ключ создаётся одной явной командой и хранится отдельно от БД (env или `.env`).
- Один понятный файл предпочтений (`config.toml`), который можно править руками и из CLI без потери комментариев.
- Полностью неинтерактивная работа после однократной настройки (для AI-агентов).
- Минимальные изменения в send-командах: одна новая опция и fallback цели в одном месте.

**Non-Goals:**
- Привязка чатов к конкретному боту (чаты остаются глобальными).
- Ротация ключа с перешифровкой (`--force` только заменяет ключ) и импорт старого токена из `.env`.
- Хранение ключа в OS keyring, шифрование мастер-паролем, ключ в `config.toml`.
- Команда общего редактирования конфига (`tgbot config set …`) — только `bot default` и `chat default`.

## Decisions

### D1. Шифрование: `cryptography.fernet.Fernet`
Fernet — AES-128-CBC + HMAC-SHA256 со случайным IV: аутентифицированное шифрование «из коробки», ключ — 32 байта в urlsafe-base64 (`Fernet.generate_key()`), неверный ключ/повреждённый шифротекст дают `InvalidToken`. Библиотека зрелая, с колёсами для Python 3.13.
- Альтернатива: `AESGCM` из той же библиотеки — нужно вручную управлять nonce и форматом; выигрыша нет.
- Альтернатива: `PyNaCl` `SecretBox` — ещё одна нативная зависимость без преимуществ.

### D2. Модуль `src/tgbot_cli/crypto.py` и команда `tgbot key init`
`crypto.py` — единственное место, знающее о Fernet:
- `load_key(settings) -> Fernet`: только `settings.secret_key` (pydantic читает `TGBOT_SECRET_KEY` из env, затем из `.env`). Нет ключа → `ConfigError("Encryption key is not configured", hint="Run `tgbot key init` (or restore the old TGBOT_SECRET_KEY if bots are already saved)")`. Некорректный ключ (`ValueError`/`binascii.Error`) → `ConfigError` без вывода значения.
- `generate_key() -> str`, `encrypt(fernet, token) -> bytes`, `decrypt(fernet, blob, *, bot) -> str`; `InvalidToken` → `ConfigError("Cannot decrypt the token of bot '…' with the current key", …)`.

`commands/key.py` → `tgbot key init [--force]`: если `settings.secret_key` уже задан (env или `.env`) и нет `--force` → `ConfigError` с подсказкой `--force`. Иначе `generate_key()` и `config._write_env(settings, {"TGBOT_SECRET_KEY": key})` (существующая функция: слияние строк, 0600). Если ключ был задан только в env, `--force` пишет в `.env`, но предупреждает, что env-переменная всё равно важнее. При `--force` и сохранённых ботах — предупреждение с их числом. Вывод: путь к `.env`, сам ключ не печатается.
- Альтернатива: печатать `export TGBOT_SECRET_KEY=…` — отвергнуто пользователем в пользу записи в `.env`.
- Альтернатива: автосоздание `secret.key` — отвергнуто: один явный источник ключа, никакой магии; удалённый ключ не подменяется новым молча.

### D3. Таблица `bots` в `db.py`
```sql
CREATE TABLE IF NOT EXISTS bots (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    token_enc BLOB NOT NULL,
    bot_id INTEGER NOT NULL,
    username TEXT,
    created_at TEXT NOT NULL
)
```
`SCHEMA` становится скриптом из двух `CREATE TABLE IF NOT EXISTS` (`executescript`), так что существующие БД получают таблицу автоматически. Функции по образцу чатов: `find_bot`, `get_bot`, `list_bots` (по `created_at, id`), `get_bot_token_enc`, `add_bot`, `remove_bot`, `rename_bot`. Ошибки `BotExistsError`, `BotNotFoundError`, `NoBotsError` наследуют `ConfigError`. Dataclass `Bot` без поля токена; `to_dict(default_name)` добавляет вычисляемый `is_default`. Флага default в БД нет — единственный источник правды `config.toml` (D5). `db.py` работает только с байтами шифротекста.

### D4. Конфигурация: `config.toml` + pydantic-settings
`Settings` получает поля `secret_key: SecretStr | None`, `default_bot: str | None`, `default_chat: str | None`, `color: bool = True` (плюс существующие `plain`, `api_url`, `timeout`) и свойство `config_file` (`<config_dir>/config.toml`). Через `settings_customise_sources` порядок источников: init → env → dotenv (`.env`) → `TomlConfigSettingsSource(config_file)` → defaults. Это даёт приоритет из `specs/user-config` без собственного кода слияния. `secret_key` исключается из TOML-источника (чтение ключа из `config.toml` запрещено спекой). Ошибки `tomllib.TOMLDecodeError`/`ValidationError` в `get_settings()` превращаются в `ConfigError` с путём к файлу.

Запись: `config.update_config(settings, **values)` (значение `None` удаляет ключ) на `tomlkit` — читает документ, меняет ключи, сохраняет комментарии и порядок, пишет атомарно (временный файл + `os.replace`), создаёт каталог при необходимости. Используется только `bot default/add/rename/remove` и `chat default`.
- Альтернатива: оставить всё в `.env` — отвергнуто пользователем; `.env` остаётся только для секретов.
- Альтернатива: `tomli-w` — теряет комментарии пользователя.

### D5. Бот по умолчанию в `config.toml`
`bot add`: если `settings.default_bot` не задан в `config.toml`, записать `default_bot = name`. `bot default NAME`: `get_bot` (проверка) → `update_config(default_bot=NAME)`. `bot rename`: если переименованный бот был `default_bot` в файле — обновить. `bot remove`: если удалён default — записать самого раннего оставшегося или удалить ключ. Значение из env (`TGBOT_DEFAULT_BOT`) никогда не переписывается командами — меняется только файл.

### D6. Выбор бота и создание клиента
`telegram.build_client(settings, bot: str | None = None)`:
1. имя = `bot` → `settings.default_bot` (env → `.env` → `config.toml`, уже разрешено pydantic);
2. пустой реестр → `NoBotsError` (hint `tgbot bot add NAME`); имя не найдено → `BotNotFoundError` (hint `tgbot bot list`; если имя пришло из конфигурации — hint `tgbot bot default`); имени нет, но боты есть → тот же hint `tgbot bot default`;
3. `crypto.load_key` → `decrypt` → `out.register_secret(token)` → `BotClient`.
Всё до любого сетевого запроса. `BotOpt` (`--bot NAME`) добавляется в `commands/options.py` и во все send-команды и `whoami`; `_dispatch(target, sender, bot)` вызывает `build_client` до резолва цели (вместо `settings.require_token()`).
- Альтернатива: глобальная опция `tgbot --bot X send …` — отвергнута: агентам привычнее опция рядом с `--to`.

### D7. Чат по умолчанию
Fallback живёт в одном месте: `pick_target` и `split_media_args` возвращают `None` вместо `_no_target()`, а `_dispatch` подставляет `settings.default_chat`; если и его нет — `_no_target()` с подсказкой `tgbot chat default NAME`. Позиционный разбор не меняется (токен на месте цели — всегда цель), поэтому существующие тесты парсинга остаются валидными; `sendcontact`/`sendpoll`/`sendlocation` с фиксированными позициями получают тот же fallback через `pick_target`. `tgbot chat default NAME` (`commands/chat.py`): `db.get_chat` → `update_config(default_chat=NAME)`.

### D8. Отключение цвета
`cli._main` передаёт `plain=plain or settings.plain or not settings.color`; `console._plain_requested` не меняется. JSON-режим по-прежнему важнее.

### D9. Команды `tgbot bot` и удаление legacy
`commands/bot.py` заменяет `commands/token.py`, структура как у `commands/chat.py`: callback → список; `add/list/remove/rename/default`; `whoami` переезжает туда как top-level команда с `--bot`. `add`: проверка дубликата и `crypto.load_key` **до** запроса `getMe`, затем encrypt → `db.add_bot` → при необходимости `default_bot`. `cli.py` регистрирует `bot` и `key`, группа `token` удаляется. Из `Settings` удаляются `bot_token`, `has_token`, `require_token`, из модуля — `TOKEN_KEY`, `save_token`; `_write_env` остаётся (D2). Оставшийся в `.env` `TGBOT_BOT_TOKEN` игнорируется (`extra="ignore"`). `chat.py::_resolve_username` пытается `build_client(settings)` и при `ConfigError` сохраняет `@username` как есть с уведомлением. `info.version` показывает путь к `config.toml`, число ботов, `default_bot`, `default_chat` (без расшифровки и без чтения ключа).

### D10. Тестовые фикстуры
Фикстура `token` в `conftest.py`: выставляет `TGBOT_SECRET_KEY` (фиксированный сгенерированный ключ), вставляет бота `test` с `TOKEN` через `db.add_bot` + `crypto.encrypt` (без сети) и выставляет `TGBOT_DEFAULT_BOT=test` (чтобы не писать `config.toml` в каждом тесте). Имя `token` сохраняется, чтобы тесты отправки не переписывать. Хелпер `add_bot(name, token)` и `write_config(**values)` — для новых тестов.

## Risks / Trade-offs

- [Ключ в `.env` лежит рядом с БД] → защищает от утечки одной БД (бэкап, отправка файла), но не от доступа к аккаунту. Для большей изоляции — держать `TGBOT_SECRET_KEY` в окружении/менеджере секретов, а не в `.env`; README это объясняет.
- [Потеря ключа или `key init --force` = потеря всех токенов] → `--force` обязателен и предупреждает о числе затронутых ботов; ошибка расшифровки подсказывает восстановить ключ или добавить ботов заново.
- [Два файла в `config_dir` (`.env` и `config.toml`)] → чёткое разделение «секреты / предпочтения», `version` показывает оба пути.
- [`default_bot` в `config.toml` указывает на удалённого бота (ручная правка)] → явная ошибка с подсказкой `tgbot bot default`.
- [Чат по умолчанию может отправить сообщение «не туда», если агент забыл цель] → поведение включается только явной настройкой `default_chat`; вывод успеха всегда показывает, куда отправлено.
- [Ломающее изменение для текущих пользователей] → ошибка «no bot configured» с hint, раздел миграции в README и SKILL.md.
- [Новые зависимости `cryptography`, `tomlkit`] → зрелые, с колёсами/чистым Python для py3.13.

## Migration Plan

1. Обновить tgbot; при первой отправке пользователь получает «No bot configured — run `tgbot bot add NAME`».
2. `tgbot key init` → `TGBOT_SECRET_KEY` в `~/.config/tgbot/.env`.
3. `tgbot bot add main` → бот сохранён, `default_bot = "main"` записан в `config.toml`.
4. По желанию: `tgbot chat default me`, `color = false` в `config.toml`.
5. Удалить строку `TGBOT_BOT_TOKEN` из `~/.config/tgbot/.env` (игнорируется, но остаётся plaintext на диске).
Откат: вернуть предыдущую версию; таблица `bots` и `config.toml` ей не мешают, токен снова задаётся через `tgbot token set`.
