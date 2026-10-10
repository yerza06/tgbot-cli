# Tasks

## 1. Dependencies

- [x] 1.1 Add `cryptography` and `tomlkit` to runtime dependencies with `uv add cryptography tomlkit`. Verify that `uv sync` succeeds and `uv run python -c "from cryptography.fernet import Fernet; import tomlkit; Fernet.generate_key()"` runs.

## 2. Settings and config.toml

- [x] 2.1 In `config.py` (design D4) add `secret_key: SecretStr | None` (empty -> `None`), `default_bot`, `default_chat`, `color: bool = True`, the `config_file` property, and `settings_customise_sources` with order init -> env -> `.env` -> `TomlConfigSettingsSource(config_file)` -> defaults, excluding `secret_key` from TOML. Map `TOMLDecodeError`/`ValidationError` in `get_settings()` to `ConfigError` naming the file. Verify with new `tests/test_user_config.py`: values from `config.toml`, missing file = defaults and no file created, env and `.env` override the file, `TGBOT_CONFIG_DIR` moves the file, broken TOML and `timeout = "soon"` exit 3 with the path/key in the message, `secret_key` in `config.toml` is ignored, unknown keys are ignored.
- [x] 2.2 Add `config.update_config(settings, **values)` on `tomlkit` (`None` removes a key; keeps comments and order; creates the directory; atomic write via temp file + `os.replace`). Verify with pytest in `tests/test_user_config.py`: create new file, update one key while a comment and another key survive, remove a key.
- [x] 2.3 Apply `color = false` in `cli._main` (`plain or settings.plain or not settings.color`, design D8). Verify with pytest in `tests/test_console.py`: `color = false` in `config.toml` gives output without ANSI codes or box characters, default keeps styled mode when stdout is a TTY, `--json` is unaffected. Run `uv run ruff check . && uv run ruff format --check .`.

## 3. Encryption key

- [x] 3.1 Create `src/tgbot_cli/crypto.py` (design D2): `load_key(settings)` (missing key -> `ConfigError` hinting `tgbot key init`; malformed key -> `ConfigError` without the value), `generate_key`, `encrypt`, `decrypt` (`InvalidToken` -> `ConfigError` naming the bot). Verify with new `tests/test_crypto.py`: round-trip, two encryptions of one token differ, env key beats `.env` key, missing/malformed/wrong key exit 3 and messages contain neither key nor token, no file is ever created by `load_key`.
- [x] 3.2 Create `commands/key.py` with `tgbot key init [--force] [--json]` and register it in `cli.py` (design D2). Verify with new `tests/test_key.py`: creates `TGBOT_SECRET_KEY` in `.env` with mode 0600 and other `.env` lines preserved, output names the file and does not contain the key, refuses (exit 3, mentions `--force`) when a key exists in `.env` or env and leaves the file unchanged, `--force` replaces the key and warns with the number of saved bots. Run ruff.

## 4. Bot storage

- [x] 4.1 Extend `db.py` (design D3): `bots` table via `executescript`, `Bot` dataclass (`to_dict(default_name)` with computed `is_default`, no token), `BotExistsError`/`BotNotFoundError`/`NoBotsError`, and `find_bot`, `get_bot`, `list_bots`, `get_bot_token_enc`, `add_bot`, `remove_bot`, `rename_bot`. Verify with pytest in `tests/test_db.py`: CRUD, duplicate and rename clash, not-found, ordering by creation, and an existing chats-only DB gains the `bots` table without losing chats. Run ruff.

## 5. Client selection

- [x] 5.1 Change `telegram.build_client(settings, bot=None)` (design D6): name from `bot` -> `settings.default_bot`; `NoBotsError`/`BotNotFoundError` with the hints from the spec (including a missing configured `default_bot` -> hint `tgbot bot default`); decrypt via `crypto`; `out.register_secret`. Verify with pytest in `tests/test_telegram.py` using a seeded DB: precedence `--bot` > `TGBOT_DEFAULT_BOT` > `config.toml`, unknown alias / empty registry / `default_bot = "gone"` exit 3 with no request recorded by `FakeTelegram`, and a network error message is scrubbed of the token.
- [x] 5.2 Rework the `token` fixture in `tests/conftest.py` (design D10): set `TGBOT_SECRET_KEY`, insert bot `test` with `TOKEN` via `db.add_bot` + `crypto.encrypt`, set `TGBOT_DEFAULT_BOT=test`; add `add_bot(name, token)` and `write_config(**values)` helpers. Verify that `uv run pytest tests/test_send_text.py tests/test_send_media.py` passes. Run ruff.

## 6. `tgbot bot` commands

- [x] 6.1 Add `BotOpt` to `commands/options.py`. Create `commands/bot.py` (design D5, D9): `add NAME [TOKEN]` (hidden prompt; empty -> exit 2; duplicate and missing key checked before any request; `getMe` validation; encrypt; save id/username; set `default_bot` in `config.toml` when unset), `list` / bare `bot` (table/plain/JSON, default marked, friendly empty message), `remove` (reassign or drop `default_bot`), `rename` (update `default_bot`), `default NAME` (writes `config.toml`), and top-level `whoami [--bot]` showing the alias. Register `bot` in `cli.py`; delete `commands/token.py`, its registration and `tests/test_token.py`. Verify with new `tests/test_bot.py` covering every `specs/bot-registry/spec.md` scenario for these commands, including `config.toml` contents after add/default/rename/remove, list JSON shape without a token field, the DB file not containing the plaintext token, `bot add` without a key exiting 3 with a `tgbot key init` hint, and `tgbot token set` exiting 2. Run ruff.

## 7. Sending: chosen bot and default chat

- [x] 7.1 In `commands/send.py` add `bot: BotOpt = None` to every send command and pass it through `_dispatch(target, sender, bot)` to `build_client`; remove the `settings.require_token()` call. Verify with pytest (new cases in `tests/test_send_text.py` and one media command in `tests/test_send_media.py`): `--bot alerts` and `TGBOT_DEFAULT_BOT=alerts` hit the `alerts` token URL, `config.toml` default is used otherwise, `--bot missing` exits 3 with no request, no bots saved exits 3 mentioning `tgbot bot add`, removed or wrong `TGBOT_SECRET_KEY` exits 3 with no request.
- [x] 7.2 Implement the default-chat fallback (design D7): `pick_target`/`split_media_args` return `None` when no target, `_dispatch` uses `settings.default_chat`, otherwise `_no_target()` hinting `tgbot chat default`. Verify with pytest in `tests/test_send_parsing.py` and `tests/test_send_text.py`: `tgbot send "hi"` and `tgbot sendphoto a.png --caption cap` go to `default_chat`, an explicit target wins, `TGBOT_DEFAULT_CHAT` beats the file, no default -> exit 2 with no request; existing parsing tests still pass. Run ruff.

## 8. Chat commands

- [x] 8.1 Add `tgbot chat default NAME` to `commands/chat.py` (`db.get_chat` then `update_config(default_chat=NAME)`). Verify with pytest in `tests/test_chat.py`: `config.toml` gets `default_chat` with other keys/comments kept, unknown alias exits 3 and leaves the file unchanged.
- [x] 8.2 Replace the `settings.has_token` check in `_resolve_username` with `build_client(settings)` and fall back on `ConfigError`. Verify with pytest in `tests/test_chat.py`: with a saved bot `@channel` is resolved via `getChat`; with no bots it is stored as given with a notice and no request. Run ruff.

## 9. Remove legacy token configuration and update version

- [x] 9.1 Remove `bot_token`, `_empty_token_is_none`, `has_token`, `require_token`, `TOKEN_KEY` and `save_token` from `config.py` (keep `_write_env`) and every remaining reference (`grep -rn "require_token\|has_token\|save_token\|TOKEN_KEY\|BOT_TOKEN" src tests` returns nothing). Update `tests/test_config.py` and `tests/test_console.py`. Verify with a pytest that `TGBOT_BOT_TOKEN` set with no saved bots still gives the "no bot" error with no request.
- [x] 9.2 Update `commands/info.py` `version` to show the `config.toml` path, number of saved bots, `default_bot` and `default_chat` (no decryption, no key read). Verify with pytest in `tests/test_info.py` for zero and two bots, asserting neither token nor key appears in plain and JSON output. Run ruff.

## 10. Documentation and Agent Skill

- [x] 10.1 Update `README.md`: setup flow `tgbot key init` -> `tgbot bot add` (replacing `tgbot token set`); `tgbot bot list/remove/rename/default`, `tgbot chat default`, `--bot`; an annotated `config.toml` example (`default_bot`, `default_chat`, `color`, `api_url`, `timeout`) and the precedence order; `.env` now holds only `TGBOT_SECRET_KEY` (back it up; losing it means re-adding bots); remove `TGBOT_BOT_TOKEN`; migration note; exit-code 3 wording and the files list. Update `.env.example` (only `TGBOT_SECRET_KEY` comment and env overrides `TGBOT_DEFAULT_BOT`/`TGBOT_DEFAULT_CHAT`). Change `SUBGROUPS` in `tests/test_docs.py` to `{"chat", "bot", "key"}`. Verify with `uv run pytest tests/test_docs.py`.
- [x] 10.2 Update `skills/tgbot/SKILL.md` and `skills/tgbot/references/reference.md`: on exit code 3 ask the user to run `tgbot key init` / `tgbot bot add NAME`; explain `--bot`, `tgbot bot list --json`, default chat (always pass an explicit target unless the user asked to use the default); never print or ask for tokens or the key; do not delete or edit `.env`. Verify with `uv run pytest tests/test_docs.py`.

## 11. Integration check

- [x] 11.1 Run `uv run ruff check . && uv run ruff format --check . && uv run pytest`; all must pass. Then smoke-test with two real bots: `tgbot key init`, `tgbot bot add main`, `tgbot bot add second`, `tgbot bot list`, `tgbot chat add me <id>`, `tgbot chat default me`, `tgbot send "hi"`, `tgbot send "hi" me --bot second`, `tgbot whoami --bot second`, set `color = false` in `~/.config/tgbot/config.toml` and check `tgbot bot list` is plain, and confirm `grep -c <token> ~/.config/tgbot/tgbot.db` finds no plaintext token.

## Workflow follow-up

- Archive the change with `/opsx:archive` once implemented and reviewed. Note: `openspec/specs/` is still empty because `add-tgbot-cli` was archived without syncing; if those specs are synced later, adjust the `bot-credentials` and `message-sending` requirements superseded by `bot-registry`, `token-encryption` and `user-config`.
