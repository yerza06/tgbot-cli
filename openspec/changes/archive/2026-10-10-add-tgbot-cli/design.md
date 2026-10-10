# Design

## Context

The repo is a bare `uv init` scaffold: `src/tgbot_cli/__init__.py`, empty `dependencies`, a `tgbot-cli` script, and `.python-version` 3.13. There is no code to integrate with yet. The reference implementation is the author's `yerza06/tguser-cli`. Its layout (`cli.py`, `config.py`, `console.py`, `resolver.py`, `db/`, `commands/{chat,send,info}`), command names, and two-syntax argument parser (`_split_media_args`) are adopted here, so both tools feel the same to people and agents. Requirements live in `specs/`; see proposal.md for the motivation.

## Goals / Non-Goals

**Goals:**
- Same mental model and command names as `tguser`, adapted to the Bot API.
- A synchronous, dependency-light core, so commands start fast. Agents call the tool per event.
- Make the write-only property hold in code, not only in documentation.

**Non-Goals:**
- Receiving messages, bot commands, webhooks, inline keyboards or callback handling.
- Multiple bot profiles. One token per config dir; separate bots use `TGBOT_CONFIG_DIR`.
- Editing or deleting sent messages, scheduling, retries beyond a single 429 retry.
- i18n (English only).

## Decisions

### Package layout
The package stays `src/tgbot_cli/` and only the console script changes to `tgbot = "tgbot_cli.cli:main"`. Renaming the package to `tgbot` was considered, but the extra churn gains nothing.

```
src/tgbot_cli/
  cli.py        root Typer app; registers command groups; main() maps exceptions -> exit codes
  config.py     Settings (pydantic-settings), save_token()
  console.py    Output facade (rich | plain | json)
  errors.py     TgbotError hierarchy with exit_code: UsageError(2), ConfigError(3), TelegramAPIError(1), NetworkError(4)
  telegram.py   BotClient
  db.py         sqlite3 repository
  resolver.py   target -> chat_id
  media.py      InputFile resolution, size checks, text chunking
  commands/     token.py (token set, whoami), info.py (version), chat.py, send.py
```

### Telegram client: thin sync httpx wrapper with an allowlist
`BotClient(token, api_url, timeout)` wraps a single `httpx.Client` and exposes `call(method, params=None, files=None) -> dict`.
- `ALLOWED_METHODS` is a frozenset of `getMe`, `getChat` and the exposed `send*` methods. Any other name raises before a request is built, which is how the write-only requirement is enforced.
- Requests are POSTed. When `files` is present the body is multipart, otherwise JSON.
- The result is parsed as `{"ok", "result" | "error_code", "description", "parameters.retry_after"}`. A 429 sleeps `retry_after` and retries once. `ok: false` raises `TelegramAPIError(code, description)`. A 403 gets the `/start` hint appended.
- `httpx.TransportError` is caught and re-raised as `NetworkError`, with a message built from the method name only. The URL contains the token, so the message never includes it.
- The class accepts an injectable `transport` for tests (`httpx.MockTransport`).

Alternatives: `python-telegram-bot` and `aiogram` are async-first, heavy, and built around update handling, which is exactly what we must not do. `requests` was excluded by the requested stack.

### Sync instead of async
tguser needed asyncio for Kurigram. A Bot API call is a single HTTPS request, so sync httpx plus stdlib `sqlite3` avoid an event loop and SQLAlchemy entirely, and keep startup fast.

### Media input resolution
`media.resolve_input(token: str, *, kind) -> InputValue`:
- an existing path becomes an upload tuple `(filename, open file, mime)`, after the size check: 50 MB in general, 10 MB for `photo`;
- `http(s)://` becomes a URL string;
- anything else is treated as a `file_id` string.

Albums use `sendMediaGroup`. Uploaded items are referenced as `attach://fileN` in the `media` JSON field, alongside the multipart parts. Batches hold at most 10 items, and a trailing batch with a single item falls back to the single-item method, since Telegram rejects one-item media groups.

### Positional parsing
`_split_media_args` and `_pick_target_caption` are ported from tguser `commands/send.py`. They are extended so that a token counts as content when it is an existing file or a URL. When `--to` is set, plus `--caption` for commands that have a caption, all positionals are content, which enables `file_id`. Every send command uses `context_settings={"ignore_unknown_options": True}` so that `-100…` IDs survive Click parsing, as in tguser.

### Text sending
`-` reads `sys.stdin.read()`. `media.chunk_text(text, 4096)` splits at the last newline before the limit, falling back to a hard cut. Parse mode defaults to none: agents emit arbitrary text, and MarkdownV2 rejects unescaped `.`, `-`, `(` and similar. `--parse-mode markdown` maps to `MarkdownV2`, and `html` maps to `HTML`.

### Config
`Settings(BaseSettings)`:
- `env_prefix="TGBOT_"`, `env_file=<config_dir>/.env`;
- fields `bot_token: SecretStr | None`, `config_dir: Path = ~/.config/tgbot`, `plain: bool = False`, `api_url = "https://api.telegram.org"`, `timeout: float = 30`;
- property `db_path = config_dir / "tgbot.db"`.

Because the env file location depends on `TGBOT_CONFIG_DIR`, `get_settings()` reads that variable first and passes `_env_file=` explicitly. `save_token()` ports tguser `_write_env`: it merges keys, rewrites the file and chmods it to 0600. The token is stored in the same directory as the DB, which mirrors tguser (`~/.config/tguser`) instead of splitting files across XDG config and data directories.

### SQLite repository
`db.connect(path)` creates the parent directory and runs `CREATE TABLE IF NOT EXISTS chats(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, chat_id TEXT NOT NULL, title TEXT, created_at TEXT NOT NULL)`. Functions `add_chat`, `list_chats`, `get_chat`, `find_chat`, `remove_chat`, `rename_chat` and `replace_chat_id` take a connection and return a `Chat` dataclass. `ChatExistsError` and `ChatNotFoundError` subclass `ConfigError` (exit 3). `chat_id` is stored as TEXT so that `@username` can be kept unresolved.

### Output facade
`console.py` holds a module-level `Output` configured once in the root callback: `mode in {rich, plain, json}`.
- Rich mode uses `Console()` and `Console(stderr=True)` with panels and tables, as in tguser.
- Plain mode uses `print` and `Console(no_color=True, force_terminal=False)`, without panels.
- JSON mode uses `emit_json(obj, err=False)`.

Commands call `out.success(...)`, `out.result(data)` and `out.table(...)`, and never print directly. Per-command `--json` simply sets the mode. `main()` catches `TgbotError`, prints it through the facade and exits with `exc.exit_code`. `KeyboardInterrupt` exits with 130, and any other exception prints a one-line error and exits with 1.

### Agent Skill
`skills/tgbot/SKILL.md` follows the tguser skill format: frontmatter with name and description, a short how-to, the `/start` caveat, and the `--json`/exit-code contract. Full flag tables go in `references/reference.md`.

## Risks / Trade-offs

- [The bot cannot message users who never pressed Start] -> Explicit 403 hint, plus README and Skill documentation.
- [Users must find their numeric chat ID without `getUpdates`] -> README points to @userinfobot or similar. `chat add @channel` resolves public channels through `getChat`.
- [Positional ambiguity: a `file_id` or a typo looks like a target] -> Content is only existing files or URLs unless the flags are used. Leftover tokens are a usage error, so mistakes fail loudly instead of sending to the wrong chat.
- [Token leakage in error messages: the URL holds the token] -> NetworkError messages are built without the URL. Tests assert the token never appears in output.
- [Large uploads time out on slow links] -> `TGBOT_TIMEOUT` is configurable. The 50 MB limit is enforced up front.
- [One-item media group rejected by Telegram] -> Fall back to the single-item method.
