# tgbot

A **write-only** CLI for sending Telegram messages **as a bot** (Bot API). Built for AI agents
such as Claude Code, Codex CLI and Hermes-Agent, so they can notify you, or anyone else, about an
event.

`tgbot` only sends. It never calls `getUpdates` or webhooks and never reads anyone's messages:
the HTTP client refuses every Bot API method except `getMe`, `getChat` and `send*`.

Chat IDs can be saved under short names in a local SQLite database, much like `git remote`.

Sibling project: [tguser-cli](https://github.com/yerza06/tguser-cli) does the same as a *user*
account over MTProto.

## Stack

Python 3.13 · [uv](https://docs.astral.sh/uv/) · [Typer](https://typer.tiangolo.com/) +
[Rich](https://rich.readthedocs.io/) · Pydantic-Settings · [httpx](https://www.python-httpx.org/) ·
SQLite (stdlib `sqlite3`).

## Installation

From a clone:

```bash
git clone https://github.com/yerza06/tgbot-cli.git
cd tgbot-cli
uv tool install .
```

This puts `tgbot` in `~/.local/bin/`, and it then works **from any directory**, which matters
because an agent's working directory is not known in advance.

```bash
uv tool install . --force    # reinstall after changing the code
uv tool install -e .         # editable install
uv tool uninstall tgbot-cli  # remove
```

For development, `uv sync` then `uv run tgbot …` from the project root.

## Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) (`/newbot`) and copy its token.
2. Save the token. It is checked with Telegram first, then written to
   `~/.config/tgbot/.env` with mode 0600:

   ```bash
   tgbot token set          # prompts for the token (input hidden)
   tgbot whoami             # shows the bot's ID and @username
   ```

3. **Open your bot in Telegram and press Start.** A bot cannot start a conversation: every
   person it should message must send `/start` to it once. For groups and channels, add the bot
   as a member (as an admin, for channels).
4. Find your numeric chat ID, e.g. with [@userinfobot](https://t.me/userinfobot), and save it:

   ```bash
   tgbot chat add me 13342324
   ```

You can also configure everything through environment variables (see `.env.example`):

| Variable | Default | Meaning |
|---|---|---|
| `TGBOT_BOT_TOKEN` | — | Bot token; overrides the one in `.env` |
| `TGBOT_CONFIG_DIR` | `~/.config/tgbot` | Where `.env` and `tgbot.db` live |
| `TGBOT_PLAIN` | `false` | Disable Rich styling |
| `TGBOT_TIMEOUT` | `30` | HTTP timeout in seconds |
| `TGBOT_API_URL` | `https://api.telegram.org` | Bot API server (e.g. a local Bot API server) |

> Do not delete `~/.config/tgbot/tgbot.db`: it holds all your saved chat aliases.

## Chat aliases

```bash
tgbot chat add me 13342324              # save an alias
tgbot chat add team -1001234567890      # groups and channels have negative IDs
tgbot chat add news @mychannel          # public channel: resolved to its ID via getChat
tgbot chat list                         # table of saved chats (or just `tgbot chat`)
tgbot chat get-id team                  # print the bare ID
tgbot chat replace-id team -100999      # point the alias elsewhere
tgbot chat rename team devs             # rename
tgbot chat remove devs                  # delete
```

A target can be a **saved alias**, a **numeric chat ID** or a **`@channel` username**. Aliases are
checked first.

## Sending

Every command accepts two syntaxes: flags (`--to`, `--caption`) or positional arguments.

```bash
# Text (plain by default; long text is split into several messages)
tgbot send "Build failed" me
tgbot send "Build failed" --to me --silent
some_command 2>&1 | tgbot send - me                 # read the text from stdin
tgbot send "<b>Done</b>" me --parse-mode html       # or --parse-mode markdown (MarkdownV2)

# Photos (several -> album, batches of 10), from a file or a URL
tgbot sendphoto shot.png me "Screenshot"
tgbot sendphoto a.png b.png --to me --caption "Screens"
tgbot sendphoto https://example.com/chart.png --to me

# Documents (several -> separate messages, or one album with --group)
tgbot sendfile report.pdf --to me --caption "Report"
tgbot sendfile part1.pdf part2.pdf --to me --group

# Video / audio / voice / animation / video note / sticker
tgbot sendvideo clip.mp4 me "Clip"
tgbot sendaudio track.mp3 --to me
tgbot sendvoice voice.ogg --to me
tgbot sendanimation fun.gif --to me
tgbot sendvideonote note.mp4 --to me
tgbot sendsticker sticker.webp --to me
tgbot sendsticker CAACAgIAAxkBAAE... --to me        # by file_id: use the flag form

# Contact, location, poll, dice
tgbot sendcontact +77001234567 Ivan Petrov me
tgbot sendlocation 43.238 76.889 me
tgbot sendpoll "Deploy now?" Yes No --to me --no-anonymous
tgbot senddice me --emoji 🎯
```

How positional arguments are read: leading tokens that are existing files or URLs are the media.
The next token is the target, and the one after it is the caption. Leftover tokens are an error,
so a typo never sends to the wrong chat. A Telegram `file_id` is only recognised when you pass
`--to` (plus `--caption` for commands that have one).

Limits are checked before uploading: files up to 50 MB, photos up to 10 MB, captions up to
1024 characters.

## Output for agents

| Mode | How |
|---|---|
| Rich (panels, colors) | default in a terminal |
| Plain text | `tgbot --plain …`, `TGBOT_PLAIN=1`, `NO_COLOR=1`, or stdout not a TTY |
| JSON | `--json` (global or on any command) |

```console
$ tgbot send "hi" me --json
{"ok": true, "chat_id": 13342324, "message_ids": [42]}

$ tgbot send "hi" boss --json        # error JSON goes to stderr
{"ok": false, "error": "Unknown chat 'boss'.", "code": 3, "hint": "..."}
```

| Exit code | Meaning |
|---|---|
| `0` | Success |
| `1` | Telegram rejected the request (e.g. 403: the recipient has not pressed Start) |
| `2` | Usage error: bad arguments, missing file, limit exceeded |
| `3` | Configuration error: no token, unknown alias, alias exists or not found |
| `4` | Network error: Telegram unreachable or timed out |
| `130` | Interrupted |

The bot token never appears in any output.

## Agent Skill

[`skills/tgbot/`](skills/tgbot/SKILL.md) is an [Agent Skill](https://agentskills.io/specification)
that teaches agents how to use `tgbot`. Copy or symlink it into your agent's skills directory
(e.g. `~/.claude/skills/tgbot`).

## Development

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest
```

```
src/tgbot_cli/
├── cli.py         # root Typer app, exit-code mapping
├── config.py      # pydantic-settings (TGBOT_*, ~/.config/tgbot/.env)
├── console.py     # output facade: rich | plain | json
├── errors.py      # error hierarchy -> exit codes
├── telegram.py    # write-only Bot API client (allowlist)
├── db.py          # sqlite3 chat aliases
├── resolver.py    # alias -> chat_id
├── media.py       # file/URL/file_id inputs, limits, text chunking
└── commands/      # token, chat, send, info
```
