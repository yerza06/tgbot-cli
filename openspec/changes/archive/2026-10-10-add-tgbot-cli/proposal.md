# Proposal

## Why

AI agents (Claude Code, Codex CLI, Hermes-Agent, …) running unattended need a simple, scriptable way to notify the owner, or another person, about events through Telegram. The sibling project `tguser-cli` does this as a *user* account over MTProto. This change adds the *bot* variant over the Bot API. It needs only a token from @BotFather and no login session, and it is strictly **write-only**: the tool never reads incoming messages.

## What Changes

- New installable CLI `tgbot` (console script) built from the existing `tgbot-cli` scaffold.
- Bot token configuration: `tgbot token set` (the token is validated, then stored in the user config directory), `tgbot whoami`, `tgbot version`. Environment variables override the stored values.
- Named chat aliases stored locally in SQLite, managed like `git remote`: `tgbot chat add|list|get-id|replace-id|rename|remove`. `@public_channel` values can optionally be resolved to numeric IDs.
- Sending commands:
  - text: `send` (accepts stdin via `-`; long text is split automatically);
  - media: `sendphoto`, `sendfile`, `sendvideo`, `sendaudio`, `sendvoice`, `sendvideonote`, `sendanimation`, `sendsticker`;
  - other messages: `sendcontact`, `sendlocation`, `sendpoll`, `senddice`.

  Each command accepts both a flag syntax (`--to`, `--caption`) and a positional syntax. The target can be an alias, a numeric ID or a `@channel`. Media can be a local file, a URL or a Telegram `file_id`. Several photos, videos or documents are sent as an album.
- Agent-friendly output: Rich output that can be switched off (`--plain`, `TGBOT_PLAIN`, `NO_COLOR`, non-TTY), a machine-readable `--json` mode, and stable exit codes.
- Write-only guarantee: the tool calls only `getMe`, `getChat` and `send*` Bot API methods, and never `getUpdates` or webhooks.
- An Agent Skill (`skills/tgbot/SKILL.md`), so agents discover and use the tool on their own.
- The project Python version in `openspec/config.yaml` is aligned to 3.13.

## Capabilities

### New Capabilities

- `bot-credentials`: configuring, validating and inspecting the Telegram bot token and the config location.
- `chat-aliases`: local named aliases for chat IDs (add, list, look up, rename, change, remove) and how targets resolve.
- `message-sending`: sending text, media, contacts, locations, polls and dice to a target. Covers argument syntax, input sources, limits, and the write-only guarantee.
- `cli-output`: human, plain and JSON output modes, error reporting, and exit codes.

### Modified Capabilities

None. The project has no existing specs.

## Impact

- **Code**: new package modules under `src/tgbot_cli/` (CLI, config, console, Telegram client, DB, resolver, media helpers, command groups); new `tests/`.
- **Dependencies**: runtime `typer`, `rich`, `pydantic-settings`, `httpx`; dev `pytest`, `ruff`. SQLite comes from the standard library.
- **Packaging**: `pyproject.toml` gets the console script `tgbot`.
- **Files on the user's machine**: `~/.config/tgbot/.env` (token, mode 0600) and `~/.config/tgbot/tgbot.db`.
- **External**: Telegram Bot API (`api.telegram.org`), outbound only.
- **Docs**: `README.md`, `.env.example`, `skills/tgbot/`.
