# tgbot — full reference

Read this when `SKILL.md` is not enough.

## Global options

| Option | Description |
|--------|-------------|
| `--plain` | Plain text output, with no colors or boxes (also `TGBOT_PLAIN=1`, `NO_COLOR`, or non-TTY stdout) |
| `--json` | JSON output; also accepted on every command |
| `--version`, `-V` | Print `tgbot X.Y.Z` |
| `--help` | Help for any command |

## Token and identity

| Command | Description |
|---------|-------------|
| `tgbot token set [TOKEN]` | Validate the token with `getMe`, then save it to `<config_dir>/.env` (0600). Prompts with hidden input when TOKEN is omitted. Exit 1 if Telegram rejects it; nothing is saved |
| `tgbot whoami` | The bot's ID, @username and name |
| `tgbot version` | Version, config dir, DB path, and whether a token is configured (never the token itself). Works offline |

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `TGBOT_BOT_TOKEN` | — | Overrides the token stored in `.env` |
| `TGBOT_CONFIG_DIR` | `~/.config/tgbot` | Location of `.env` and `tgbot.db`; use separate dirs for separate bots |
| `TGBOT_PLAIN` | `false` | Plain output |
| `TGBOT_TIMEOUT` | `30` | HTTP timeout (seconds) |
| `TGBOT_API_URL` | `https://api.telegram.org` | Bot API base URL |

Environment variables take precedence over `.env`.

## Chat management

| Command | Description |
|---------|-------------|
| `chat add NAME ID` | ID is a number or `@username`. `@username` is resolved via `getChat` when a token exists; `--no-resolve` stores it as is |
| `chat list` / `chat` | Sorted by name; with `--json`, an array of `{name, chat_id, title, created_at}` |
| `chat get-id NAME` | Bare ID on stdout |
| `chat replace-id NAME ID` | Change the ID |
| `chat rename OLD NEW` | Fails (exit 3) if NEW exists |
| `chat remove NAME` | Fails (exit 3) if missing |

Targets are resolved in this order: alias → integer chat ID → `@username`. Anything else exits 3
before any request is made.

## Sending — options

| Command | Positional form | Caption | Several items |
|---------|-----------------|:-------:|---------------|
| `send` | `TEXT [TARGET]` (`-` = stdin) | — | Split at 4096 chars |
| `sendphoto` | `FILES… [TARGET] [CAPTION]` | ✓ | Album; batches of 10 |
| `sendvideo` | same | ✓ | Album; batches of 10 |
| `sendfile` | same | ✓ | Separate messages; album with `--group`/`-G` |
| `sendaudio`, `sendvoice`, `sendanimation` | same | ✓ | Separate messages, caption on the first |
| `sendvideonote`, `sendsticker` | `FILES… [TARGET]` | — | Separate messages |
| `sendcontact` | `PHONE FIRST [LAST] [TARGET]` | — | `--phone --first-name --last-name` |
| `sendlocation` | `LAT LON [TARGET]` | — | lat ∈ [-90, 90], lon ∈ [-180, 180] |
| `sendpoll` | `QUESTION OPT… [TARGET]` | — | 2–10 options; `--multiple`, `--anonymous/--no-anonymous` (default anonymous) |
| `senddice` | `[TARGET]` | — | `--emoji` one of 🎲 🎯 🏀 ⚽ 🎳 🎰 |

Common options: `--to`, `--silent`, `--json`, `--parse-mode html|markdown` (on text and
captions).

### Positional parsing rules

1. Leading tokens that are existing files or `http(s)://` URLs are media.
2. The next token is the target, unless `--to` is given.
3. The next token is the caption, unless `--caption` is given (and only for commands with
   captions).
4. Leftover tokens give exit 2. A path-like token that does not exist gives "File not found".
5. When `--to` is set (plus `--caption` for captioned commands), **all** positionals are media.
   This is the only way to send a `file_id`.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Exit 3, "No bot token configured" | The user runs `tgbot token set` |
| Exit 3, "Unknown chat 'x'" | `tgbot chat add x ID`, or pass a numeric ID |
| Exit 1, 403 "bot can't initiate conversation" | The recipient must open the bot and press Start |
| Exit 1, 403 "bot was blocked by the user" | The user blocked the bot; they must unblock it |
| Exit 1, 400 "chat not found" | Wrong ID, or the bot is not in that group or channel |
| Exit 1, 400 "can't parse entities" | Bad HTML/Markdown; drop `--parse-mode` |
| Exit 2, "File not found" | Check the path; positional parsing stops at missing files |
| Exit 4 | Network down or `TGBOT_TIMEOUT` too low for a large upload |
