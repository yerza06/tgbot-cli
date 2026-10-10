# Tasks

## 1. Project setup

- [x] 1.1 Add runtime deps (`typer`, `rich`, `pydantic-settings`, `httpx`) and a dev group (`pytest`, `ruff`) to `pyproject.toml`; change the script to `tgbot = "tgbot_cli.cli:main"`; add `[tool.ruff]` (line-length 100, target py313) and `[tool.pytest.ini_options]`. Verify that `uv sync` succeeds and `uv run tgbot --help` runs.
- [x] 1.2 Change the Python version in `openspec/config.yaml` context to 3.13. Verify with `grep 3.13 openspec/config.yaml`.
- [x] 1.3 Create `tests/conftest.py` with fixtures: a temporary `TGBOT_CONFIG_DIR`, a cleared `TGBOT_*`/`NO_COLOR` environment, a Typer `CliRunner`, and a fake Telegram transport (`httpx.MockTransport`) that records requests. Verify with a smoke pytest; `uv run ruff check .` must be clean.

## 2. Errors, config and output

- [x] 2.1 Implement `errors.py` (`TgbotError` plus `UsageError`=2, `ConfigError`=3, `TelegramAPIError`=1, `NetworkError`=4). Verify with pytest asserting the exit codes.
- [x] 2.2 Implement `config.py` (`Settings` with `TGBOT_` prefix, `<config_dir>/.env`, `TGBOT_CONFIG_DIR` override, `SecretStr` token, `db_path`, `save_token` merge plus chmod 0600). Verify with pytest: env overrides file, custom config dir, merge preserves other keys, file mode is 0600.
- [x] 2.3 Implement the `console.py` output facade (rich/plain/json; plain chosen by `--plain`, `TGBOT_PLAIN`, `NO_COLOR` or non-TTY; `emit_json` to stdout or stderr). Verify with pytest: plain output has no ANSI codes or box characters, and the JSON helpers write valid JSON to the right stream. Run `ruff check`.
- [x] 2.4 Implement the `cli.py` root app: global `--plain`/`--json`/`--version` callback, and `main()` mapping `TgbotError`, `KeyboardInterrupt` and unexpected exceptions to messages and exit codes without tracebacks. Verify with pytest that a raised `ConfigError` exits 3 and an unexpected exception prints one line and exits 1.

## 3. Telegram client

- [x] 3.1 Implement `telegram.py` `BotClient` (`ALLOWED_METHODS` allowlist, JSON vs multipart POST, `ok:false` -> `TelegramAPIError`, a single 429 retry using `retry_after`, the 403 `/start` hint, transport errors -> `NetworkError` without the token in the message, injectable transport). Verify with pytest using MockTransport: `getUpdates` is refused with no request made, 429 then success delivers, 403 includes the hint, a connect error exits 4, and the token never appears in error text. Run `ruff check`.

## 4. Bot credentials commands

- [x] 4.1 Implement `commands/token.py`: `token set [TOKEN]` (hidden prompt, validate with getMe, save, report the username; invalid token -> nothing written, exit 1) and `whoami`. Verify with CliRunner tests for a valid save, an invalid token, whoami output, and a missing token (exit 3 with a `tgbot token set` hint, no request).
- [x] 4.2 Implement `commands/info.py` `version` (version, config dir, DB path, token configured yes/no). Verify with a pytest that the token value is absent from the output. Run `ruff check`.

## 5. Chat aliases

- [x] 5.1 Implement the `db.py` sqlite3 repository (schema, `Chat` dataclass, add/list/get/find/remove/rename/replace_id, `ChatExistsError`/`ChatNotFoundError` as `ConfigError`). Verify with pytest on a temporary DB covering CRUD, uniqueness, rename clash and not-found.
- [x] 5.2 Implement `resolver.py` (alias, then int, then `@username`, otherwise an unknown-alias `ConfigError` suggesting `tgbot chat add`). Verify with pytest for each branch.
- [x] 5.3 Implement `commands/chat.py`: `add` (negative IDs, `@username` resolved via getChat unless `--no-resolve`, graceful fallback without a token), `list` / bare `chat` (table, plain or JSON array; friendly empty message), `get-id` (bare stdout), `replace-id`, `rename`, `remove`. Verify with CliRunner tests for every scenario in `specs/chat-aliases/spec.md`. Run `ruff check`.

## 6. Message sending

- [x] 6.1 Implement `media.py`: `resolve_input` (path upload / URL / file_id), size limits (50 MB, 10 MB for photo), caption ≤1024 check, `chunk_text` (4096, newline-preferred). Verify with pytest: limits raise `UsageError`, chunk order and content are preserved for a 9000-char text, and URL and file_id are classified correctly.
- [x] 6.2 Port the positional parsing (`_split_media_args`, `_pick_target_caption`) from tguser with the URL and flag-only content rules. Verify with pytest on the parsing edge cases: positional files/target/caption, the extra-token error, `--to`-only for sticker with a file_id, and negative IDs.
- [x] 6.3 Implement the shared send runner (settings -> token check -> resolve target -> `BotClient` -> collect `message_ids` -> success/JSON output) and `send` (text, `-` stdin, empty stdin error, chunking, `--parse-mode`, `--silent`). Verify with CliRunner and MockTransport tests asserting the `sendMessage` params, the JSON success shape `{"ok", "chat_id", "message_ids"}`, and the unknown-alias JSON error on stderr with code 3.
- [x] 6.4 Implement the single-media commands `sendfile`, `sendvideo`, `sendaudio`, `sendvoice`, `sendvideonote`, `sendanimation`, `sendsticker`, plus single-photo `sendphoto`. Verify with tests asserting the method name and the multipart field per command, the URL passthrough, and that a missing file is reported before any request.
- [x] 6.5 Implement albums: `sendphoto`/`sendvideo` with several items, and `sendfile --group`, via `sendMediaGroup` with `attach://`, batches of 10, caption on the first item, and the single-item fallback. Verify with a test that 12 photos give requests of 10 and 2 items and only the first item has the caption, and that `sendfile` without `--group` sends separate messages.
- [x] 6.6 Implement `sendcontact` (positional and flag forms), `sendlocation` (range validation, negative coordinates), `sendpoll` (2–10 options, `--multiple`, `--anonymous/--no-anonymous`, default anonymous) and `senddice` (`--emoji`). Verify with CliRunner tests for every scenario in `specs/message-sending/spec.md` covering these commands. Run `ruff check`.

## 7. Documentation and Agent Skill

- [x] 7.1 Write `README.md`: install with `uv tool install`, create a bot via @BotFather, `tgbot token set`, the `/start` requirement, finding your chat ID, the chat and send command reference, `--json`, exit codes, and the files under `~/.config/tgbot`. Add `.env.example`. Verify by running each README command example with `--help` (or against MockTransport in a pytest doc check).
- [x] 7.2 Write `skills/tgbot/SKILL.md` (frontmatter, usage, the `/start` caveat, the JSON and exit-code contract) and `skills/tgbot/references/reference.md` (full flag tables). Verify with a pytest that the frontmatter parses and every command named in the skill exists in `tgbot --help`.

## 8. Integration check

- [x] 8.1 Run `uv run ruff check . && uv run ruff format --check . && uv run pytest`; all must pass. Then do a manual smoke test with a real bot: `uv tool install -e .`, `tgbot token set`, `/start` the bot, `tgbot chat add me <id>`, `tgbot send "hi" me`, `tgbot sendphoto x.png me "cap"`, `echo test | tgbot send - me --json`.

## Workflow follow-up

- Archive the change with `/opsx:archive` once implemented and reviewed.
