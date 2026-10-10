# Proposal

## Why

Сейчас tgbot знает ровно один токен бота (`TGBOT_BOT_TOKEN` в env или в `<config_dir>/.env`, в открытом виде), поэтому отправлять сообщения от разных ботов нельзя, а токен лежит на диске plaintext-ом. Нужно хранить несколько ботов под алиасами (как чаты) и выбирать, от какого отправлять, при этом токены в хранилище должны быть зашифрованы. Раз появляются «бот по умолчанию» и другие пользовательские предпочтения, им нужен понятный файл конфигурации вместо разрозненных переменных окружения.

## What Changes

- Новая группа команд `tgbot bot` (по аналогии с `tgbot chat`): `add NAME [TOKEN]`, `list`, `remove NAME`, `rename OLD NEW`, `default NAME`; `tgbot bot` без подкоманды показывает список.
- `bot add` проверяет токен через `getMe`, запоминает ID и `@username` бота и сохраняет токен в базе `tgbot.db` (рядом с чатами). Первый добавленный бот становится ботом по умолчанию.
- Токены хранятся в базе только в зашифрованном виде (симметричное аутентифицированное шифрование, Fernet из библиотеки `cryptography`). Ключ берётся только из `TGBOT_SECRET_KEY` (переменная окружения или `<config_dir>/.env`).
- Новая команда `tgbot key init`: генерирует ключ и записывает `TGBOT_SECRET_KEY` в `<config_dir>/.env` (0600); существующий ключ не перезаписывается без `--force`. Без ключа `bot add` и отправка завершаются ошибкой с подсказкой запустить `tgbot key init`.
- Новый файл конфигурации `<config_dir>/config.toml` (по умолчанию `~/.config/tgbot/config.toml`) с ключами `default_bot`, `default_chat`, `color`, `api_url`, `timeout`. Переменные окружения и `.env` важнее файла; `.env` остаётся местом для секретов.
- Все команды отправки и `tgbot whoami` получают опцию `--bot ALIAS`. Порядок выбора бота: `--bot` → `TGBOT_DEFAULT_BOT` → `default_bot` из `config.toml`. `tgbot bot default NAME` записывает `default_bot` в `config.toml`.
- Чат по умолчанию: если цель не указана, команды отправки используют `default_chat` (`TGBOT_DEFAULT_CHAT` / `config.toml`); новая команда `tgbot chat default NAME` записывает его в `config.toml`.
- `color = false` в `config.toml` выключает цветной вывод (как `--plain`, `TGBOT_PLAIN`, `NO_COLOR`).
- `tgbot version` показывает путь к `config.toml`, число сохранённых ботов, бота и чат по умолчанию вместо «token: configured».
- `tgbot chat add @channel` резолвит username через бота по умолчанию, если боты есть.
- **BREAKING**: удаляется переменная `TGBOT_BOT_TOKEN` и хранение токена в `<config_dir>/.env`. Старый токен не импортируется — его нужно добавить заново через `tgbot bot add`.
- **BREAKING**: удаляется группа `tgbot token` (`tgbot token set`); её заменяют `tgbot key init` и `tgbot bot add`.

## Capabilities

### New Capabilities
- `bot-registry`: управление сохранёнными ботами под алиасами (add/list/remove/rename/default), выбор бота для отправки (`--bot`, `TGBOT_DEFAULT_BOT`, `default_bot`), `whoami` для выбранного бота, ошибки «нет ботов»/«неизвестный бот».
- `token-encryption`: хранение токенов ботов только в зашифрованном виде, источник ключа (`TGBOT_SECRET_KEY`), команда `tgbot key init`, поведение при отсутствующем или неверном ключе, недопущение утечки токена в вывод.
- `user-config`: файл `<config_dir>/config.toml`, приоритет источников настроек, чат по умолчанию и `tgbot chat default`, отключение цветного вывода, ошибки некорректного файла.

### Modified Capabilities
<!-- В openspec/specs/ пока нет ни одной спецификации: дельты прошлого change
     `add-tgbot-cli` (включая `bot-credentials`) были заархивированы без синхронизации.
     Поэтому MODIFIED/REMOVED-дельту против `bot-credentials` применить не к чему.
     Требования `bot-credentials` о `tgbot token set`, `TGBOT_BOT_TOKEN` и хранении токена
     в `.env`, а также требование `message-sending` об обязательной цели, этим change
     заменяются требованиями `bot-registry`, `token-encryption` и `user-config`;
     если архивные спеки будут синхронизированы позже, их нужно поправить. -->
- Нет (см. комментарий выше).

## Impact

- Код: `src/tgbot_cli/config.py` (убрать `bot_token`, `save_token`, `require_token`; добавить `secret_key`, `default_bot`, `default_chat`, `color`, источник `config.toml` и запись в него; `_write_env` остаётся для `key init`), `db.py` (таблица `bots` и CRUD), новый `crypto.py`, `telegram.py` (`build_client` с выбором бота), `commands/token.py` → `commands/bot.py`, новый `commands/key.py`, `commands/send.py` (`--bot`, чат по умолчанию), `commands/chat.py` (`chat default`, резолв через бота), `commands/info.py`, `commands/options.py` (`BotOpt`), `console.py`/`cli.py` (`color`).
- Зависимости: новые runtime-зависимости `cryptography` и `tomlkit` (запись TOML с сохранением комментариев).
- Тесты: фикстура `token` в `tests/conftest.py`, `test_token.py` → `test_bot.py`, новые `test_key.py`, `test_crypto.py`, `test_user_config.py`; правки `test_config.py`, `test_info.py`, `test_send_parsing.py`, `test_chat.py`, `test_console.py`, `test_docs.py`.
- Документация: `README.md`, `.env.example`, пример `config.toml`, `skills/tgbot/SKILL.md`, `skills/tgbot/references/reference.md`.
- Пользователи: существующий токен из `.env`/env перестаёт работать; нужен однократный `tgbot key init` + `tgbot bot add`. Потеря `TGBOT_SECRET_KEY` означает, что сохранённые токены придётся добавить заново.
